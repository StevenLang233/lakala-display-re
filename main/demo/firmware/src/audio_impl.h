/* Fixed application file only. Playback uses R03's existing decoder and the
 * product's original loudspeaker GPIO and bounded local-play gain profile. */
#include "helios_audio.h"
#include "helios_fs.h"
#include "audio_volume.h"
extern int Helios_frename(const char*,const char*);
extern int ql_aud_get_play_state(void);
extern int ql_aud_get_output_type(void);
extern int ql_aud_get_pa_type(void);
extern int ql_aud_get_icvolume_level_gain(int mode,int output,int level,
                                        uint16_t *dac,uint16_t *algorithm);
extern int ql_aud_set_icvolume_level_gain(int mode,int output,int level,
                                        uint16_t dac,uint16_t algorithm);
extern int ql_pin_set_func(int pin,int function);
extern int ql_gpio_deinit(int gpio);
extern int ql_gpio_init(int gpio,int direction,int pull,int level);
extern int ql_gpio_set_level(int gpio,int level);
/* Helios C file APIs pass through ql_fopen: use its UFS: namespace.
 * U:/ is the Python-facing alias, not this low-level filesystem ABI. */
#define QD_AUDIO_PATH "UFS:qdisplay_audio.mp3"
#define QD_AUDIO_TEMP "UFS:qdisplay_audio.part"
#define QD_AUDIO_MAX (4u*1024u*1024u)
static HeliosFILE *audio_upload;
static uint32_t audio_size,audio_offset,audio_hash;
static XXH32_state_t audio_digest;
static bool audio_initialized,audio_file_valid;
static bool audio_pa_initialized;
static volatile bool audio_pa_enabled;
static volatile bool audio_pa_requested;
static bool audio_gain_ready;
static uint32_t audio_volume_changes,audio_volume_failures,audio_profile_writes;
static bool audio_profiles_ready;
static Helios_AudOutputType audio_profiles_output;
static uint32_t audio_volume=10;
static Helios_AudOutputType audio_output=HELIOS_OUTPUT_SPEAKER;
static volatile int audio_event=HELIOS_AUD_PLAYER_CLOSE;
static bool audio_streaming,audio_stream_header;
static uint32_t audio_last_pcm;
/* This product's original R05 APP, verified from its full-flash snapshot:
 * 602a43e4: ql_pin_set_func(15,4), ql_gpio_deinit(22),
 *            ql_gpio_init(22,1,255,0).
 * 602a4324: ql_gpio_set_level(22,event!=0), called for playback power.
 * These are QL hardware indices, not QuecPython public GPIO numbers.
 * The generic EVB's GPIO11 PA example is not used on this product. */
static void audio_pa(unsigned int event)
{
    /* The decoder callback can race a gain recalibration. Only latch its
     * request here; the render task exclusively owns the physical PA GPIO. */
    audio_pa_requested=event!=0;
}
static bool audio_pa_sync(void)
{
    bool enabled=audio_pa_requested && audio_gain_ready && audio_volume!=0 &&
                 audio_output==HELIOS_OUTPUT_SPEAKER;
    if(audio_pa_initialized && enabled!=audio_pa_enabled) {
        if(ql_gpio_set_level(22,enabled?1:0)) return false;
        audio_pa_enabled=enabled;
    }
    return true;
}
static bool audio_pa_init(void)
{
    if(audio_pa_initialized) return true;
    if(ql_pin_set_func(15,4) || ql_gpio_deinit(22) ||
       ql_gpio_init(22,1,255,0)) return false;
    audio_pa_initialized=true;audio_pa_enabled=false;audio_pa_requested=false;
    /* R03's supported callback registration stores RAM function pointers only
     * (601e2748), without changing PA type, audio calibration, or NV. */
    if(Helios_Audio_SetPaCallback(HELIOS_OUTPUT_SPEAKER,audio_pa)) {
        audio_pa_initialized=false;return false;
    }
    return true;
}
/* R03's PCM parameter setter is a no-op (601e3084 is bx lr). Use a WAV
 * header for an explicit sample rate instead. The audited wrapper would send
 * EOS after every write unless this exact-core-guarded export is enabled. */
static void audio_stream_flag(bool keep_open)
{ ((void (*)(int))0x6013cd19)(keep_open?1:0); }
static void audio_stop(void)
{
    if(audio_initialized) {
        if(audio_streaming) Helios_Audio_StreamPlayStop();
        else Helios_Audio_FilePlayStop();
    }
    audio_streaming=false;
    audio_pa(0);
    audio_pa_sync();
    if(core_matches) audio_stream_flag(false);
    audio_event=HELIOS_AUD_PLAYER_CLOSE;
}
static void audio_poll(void)
{
    if(audio_streaming && (uint32_t)(millis()-audio_last_pcm)>2000u) audio_stop();
    audio_pa_sync();
}
static int audio_callback(char *data,size_t length,Helios_EnumAudPlayerState state)
{ (void)data;(void)length;audio_event=state;return 0; }
static bool audio_apply_volume(void)
{
    if(!audio_initialized) return true;
    if(!audio_profiles_ready || audio_profiles_output!=audio_output) return false;
    int target=(int)audio_volume_level(audio_volume);
    /* The only live write is the supported factory volume selection. No
     * calibration writes, intermediate mute, PA off/on, delay or restart. */
    if(Helios_Audio_GetVolume(HELIOS_AUDIO_PLAY_TYPE_LOCAL)!=target) {
        if(Helios_Audio_SetVolume(HELIOS_AUDIO_PLAY_TYPE_LOCAL,target) ||
           Helios_Audio_GetVolume(HELIOS_AUDIO_PLAY_TYPE_LOCAL)!=target) {
            ++audio_volume_failures;return false;
        }
        ++audio_volume_changes;
    }
    if(!audio_pa_sync()) {++audio_volume_failures;return false;}
    return true;
}
static bool audio_prepare_profiles(void)
{
    if(audio_profiles_ready && audio_profiles_output==audio_output) return true;
    /* Initialization is invoked only after audio_stop(). Never calibrate a
     * live decoder, even if this function is accidentally called again. */
    if(audio_pa_requested || audio_pa_enabled || ql_aud_get_play_state()==1)
        return false;
    audio_gain_ready=false;audio_profiles_ready=false;
    for(unsigned int level=1;level<=9;level++) {
        uint16_t dac,algorithm,actual_dac=0,actual_algorithm=0;
        audio_volume_gain(audio_level_percent[level],&dac,&algorithm);
        if(ql_aud_get_icvolume_level_gain(HELIOS_AUDIO_PLAY_TYPE_LOCAL,audio_output,
                                         (int)level,&actual_dac,&actual_algorithm) ||
           actual_dac!=dac || actual_algorithm!=algorithm) {
            if(ql_aud_set_icvolume_level_gain(HELIOS_AUDIO_PLAY_TYPE_LOCAL,audio_output,
                                             (int)level,dac,algorithm)) return false;
            ++audio_profile_writes;
            if(ql_aud_get_icvolume_level_gain(HELIOS_AUDIO_PLAY_TYPE_LOCAL,audio_output,
                                             (int)level,&actual_dac,&actual_algorithm) ||
               actual_dac!=dac || actual_algorithm!=algorithm) return false;
        }
    }
    audio_profiles_output=audio_output;audio_profiles_ready=true;audio_gain_ready=true;
    return true;
}
static bool audio_init(void)
{
    if(!core_matches) return false;
    if(!audio_initialized) {
        if(Helios_Audio_Init()) return false;
        audio_initialized=true;
    }
    if(!audio_pa_init()) return false;
    return !Helios_Audio_SetAudioChannle(audio_output) &&
           audio_prepare_profiles() && audio_apply_volume();
}
static void audio_abort_upload(void)
{
    if(audio_upload) {Helios_fclose(audio_upload);audio_upload=NULL;}
    audio_size=audio_offset=0;
}
static uint32_t audio_control(const qd_header *h,uint32_t *rx,uint32_t *decode,
                              uint32_t *draw,uint32_t *detail)
{
    if(!core_matches) return QD_BAD_STATE;
    switch(h->flags) {
    case 0: /* State query is quiet and does not initialize the amplifier. */
        *rx=audio_volume;*decode=audio_initialized?ql_aud_get_play_state():0;
        *draw=(uint32_t)audio_event;*detail=0x31445541u;return QD_OK;
    case 1:
        audio_abort_upload();
        audio_stop();return QD_OK;
    case 2:
        if(h->offset>100) return QD_BAD_LENGTH;
        audio_volume=h->offset;
        if(!audio_apply_volume())
            return QD_BAD_STATE;
        *detail=audio_volume;return QD_OK;
    case 3: /* Begin upload: length in offset, final XXH32 in raw_length. */
        if(!h->offset || h->offset>QD_AUDIO_MAX) return QD_BAD_LENGTH;
        audio_stop();
        audio_abort_upload();audio_file_valid=false;
        if(Helios_fs_free_size('U')<(int)(h->offset+65536u)) return QD_NO_MEMORY;
        audio_upload=Helios_fopen(QD_AUDIO_TEMP,"w");
        if(!audio_upload) return QD_BAD_STATE;
        audio_size=h->offset;audio_hash=h->raw_length;XXH32_reset(&audio_digest,0);
        *detail=audio_size;return QD_OK;
    case 4: /* Commit only a complete, verified upload. */
        if(!audio_upload || audio_offset!=audio_size) return QD_BAD_STATE;
        if(XXH32_digest(&audio_digest)!=audio_hash) {audio_abort_upload();return QD_BAD_HASH;}
        if(Helios_fclose(audio_upload)) {audio_upload=NULL;return QD_BAD_STATE;}
        audio_upload=NULL;
        /* Remove only this app's own previous track, never arbitrary files. */
        Helios_remove(QD_AUDIO_PATH);
        if(Helios_frename(QD_AUDIO_TEMP,QD_AUDIO_PATH)) return QD_BAD_STATE;
        audio_file_valid=true;*detail=audio_hash;return QD_OK;
    case 5:
        if(audio_upload) return QD_BAD_STATE;
        audio_stop();
        if(!audio_init()) return QD_BAD_STATE;
        {
            HeliosFILE *file=Helios_fopen(QD_AUDIO_PATH,"r");
            if(!file) return QD_BAD_STATE;
            int size=Helios_fsize(file);Helios_fclose(file);
            if(size<=0 || size>(int)QD_AUDIO_MAX) return QD_BAD_LENGTH;
            audio_file_valid=true;audio_event=HELIOS_AUD_PLAYER_START;
            if(Helios_Audio_FilePlayStart(QD_AUDIO_PATH,HELIOS_AUDIO_PLAY_TYPE_LOCAL,audio_callback))
                return QD_BAD_STATE;
            *rx=audio_volume;*decode=Helios_Audio_GetVolume(HELIOS_AUDIO_PLAY_TYPE_LOCAL);
            *draw=ql_aud_get_output_type();*detail=size;return QD_OK;
        }
    case 6: /* Read-back: hash the actual persisted track, with bounded RAM. */
        {
            HeliosFILE *file=Helios_fopen(QD_AUDIO_PATH,"r");
            if(!file) return QD_BAD_STATE;
            uint8_t buffer[1024];int count;uint32_t bytes=0;
            XXH32_state_t hash;XXH32_reset(&hash,0);
            while((count=Helios_fread(buffer,1,sizeof(buffer),file))>0) {
                bytes+=count;if(bytes>QD_AUDIO_MAX) {Helios_fclose(file);return QD_BAD_LENGTH;}
                XXH32_update(&hash,buffer,count);
            }
            Helios_fclose(file);*rx=bytes;*detail=XXH32_digest(&hash);return QD_OK;
        }
    case 7: /* Host loopback: signed little-endian 16-bit mono PCM, 16 kHz. */
        if(h->offset!=16000u || h->raw_length!=1u || audio_upload) return QD_BAD_LENGTH;
        audio_stop();if(!audio_init()) return QD_BAD_STATE;
        audio_stream_flag(true);audio_streaming=true;audio_stream_header=true;
        audio_last_pcm=millis();*rx=audio_volume;*decode=16000;*draw=1;return QD_OK;
    case 8: /* Read-only route/volume/PA diagnostic. No GPIO or NV writes. */
        *rx=audio_initialized?(uint32_t)ql_aud_get_output_type():0xffffffffu;
        *decode=audio_initialized?Helios_Audio_GetVolume(HELIOS_AUDIO_PLAY_TYPE_LOCAL):0;
        *draw=audio_initialized?(uint32_t)ql_aud_get_pa_type():0xffffffffu;
        *detail=(audio_streaming?1u:0u)|(audio_initialized?2u:0u)|
                (audio_pa_initialized?4u:0u)|(audio_pa_enabled?8u:0u)|
                (audio_gain_ready?16u:0u)|((uint32_t)(audio_event+1)<<8);
        if(audio_initialized) {
            uint16_t dac=0,algorithm=0;
            int level=Helios_Audio_GetVolume(HELIOS_AUDIO_PLAY_TYPE_LOCAL);
            if(level>=0 && level<=11 &&
               !ql_aud_get_icvolume_level_gain(HELIOS_AUDIO_PLAY_TYPE_LOCAL,audio_output,
                                               level,&dac,&algorithm))
                *detail|=0x80000000u|((uint32_t)dac<<16)|((uint32_t)algorithm<<24);
        }
        return QD_OK;
    case 9: /* Bounded output-route diagnostic; never guess a PA GPIO. */
        if(h->offset>2u || h->raw_length || h->length) return QD_BAD_LENGTH;
        audio_stop();audio_output=(Helios_AudOutputType)h->offset;
        if(!audio_init()) return QD_BAD_STATE;
        *detail=ql_aud_get_output_type();return QD_OK;
    case 10: /* Read-only change/calibration counters; no playback changes. */
        *rx=audio_volume_changes;*decode=audio_profile_writes;*draw=audio_volume_failures;
        *detail=(audio_gain_ready?1u:0u)|(audio_pa_requested?2u:0u)|
                (audio_pa_enabled?4u:0u);return QD_OK;
    default:return QD_BAD_HEADER;
    }
}
static uint32_t audio_pcm(const qd_header *h,uint8_t *data,uint32_t *detail)
{
    if(!audio_streaming) return QD_BAD_STATE;
    if(h->flags || h->offset || !h->length || h->length>16384u ||
       h->raw_length!=h->length || (h->length&1u)) return QD_BAD_LENGTH;
    uint8_t *buffer=data;uint32_t size=h->length;
    if(audio_stream_header) {
        static const uint8_t wave[44]={
            'R','I','F','F',0xff,0xff,0xff,0x7f,'W','A','V','E',
            'f','m','t',' ',16,0,0,0,1,0,1,0,0x80,0x3e,0,0,
            0x00,0x7d,0,0,2,0,16,0,'d','a','t','a',0xdb,0xff,0xff,0x7f};
        buffer=malloc(size+44u);if(!buffer) return QD_NO_MEMORY;
        memcpy(buffer,wave,44);memcpy(buffer+44,data,size);size+=44;
    }
    int result=Helios_Audio_StreamPlayStart(HELIOS_AUDIO_FORMAT_WAVPCM,buffer,size,
                    HELIOS_AUDIO_PLAY_TYPE_LOCAL,audio_output,audio_callback);
    if(buffer!=data) free(buffer);
    if(result) {audio_stop();*detail=(uint32_t)result;return QD_BAD_STATE;}
    audio_stream_header=false;audio_last_pcm=millis();*detail=h->length;return QD_OK;
}
static uint32_t audio_data(const qd_header *h,uint8_t *data,uint32_t *detail)
{
    if(!audio_upload || h->offset!=audio_offset) return QD_BAD_STATE;
    if(!h->length || h->length>16384u || h->raw_length!=h->length ||
       h->length>audio_size-audio_offset || h->flags) return QD_BAD_LENGTH;
    int written=Helios_fwrite(data,1,h->length,audio_upload);
    if(written!=(int)h->length) {*detail=(uint32_t)written;audio_abort_upload();return QD_BAD_STATE;}
    XXH32_update(&audio_digest,data,h->length);audio_offset+=h->length;
    *detail=audio_offset;return QD_OK;
}
