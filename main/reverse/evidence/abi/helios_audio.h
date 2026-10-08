/*
 * Copyright (c) Quectel Wireless Solution, Co., Ltd.All Rights Reserved.
 *  
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *  
 *     http://www.apache.org/licenses/LICENSE-2.0
 *  
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 @file	helios_audio.h
 @brief	Data type definition for Audio.
*/
/**************************************************************************
===========================================================================
Copyright (c) 2018 Quectel Wireless Solution, Co., Ltd.All Rights Reserved.
Quectel Wireless Solution Proprietary and Confidential.
===========================================================================

						EDIT HISTORY FOR FILE
This section contains comments describing changes made to the module.
Notice that changes are listed in reverse chronological order.

WHEN		WHO			WHAT,WHERE,WHY
----------  ---------   ---------------------------------------------------
2021/03/30  Felix.Ye	Create.
**************************************************************************/

#ifndef _HELIOS_AUDIO_H
#define _HELIOS_AUDIO_H

#ifdef __cplusplus
extern "C" {
#endif


typedef enum
{
    HELIOS_OUTPUT_RECEIVER = 0,  ///< receiver
    HELIOS_OUTPUT_HEADPHONE = 1, ///< headphone
    HELIOS_OUTPUT_SPEAKER = 2,   ///< speaker

	HELIOS_OUTPUT_MAX,
} Helios_AudOutputType;

// elian add
typedef enum
{
    HELIOS_INPUT_MAINMIC = 0, ///< main mic
    HELIOS_INPUT_AUXMIC  = 1,  ///< auxilary mic
    HELIOS_INPUT_DUALMIC = 2, ///< dual mic
    HELIOS_INPUT_HPMIC_L = 3, ///< headphone mic left
    HELIOS_INPUT_HPMIC_R = 4, ///< headphone mic right
} Helios_AudInputType;

/**
 * AUDIO PLAY TYPE
 */
typedef enum
{
    HELIOS_AUDIO_PLAY_TYPE_NONE = 0,
    HELIOS_AUDIO_PLAY_TYPE_LOCAL,
    HELIOS_AUDIO_PLAY_TYPE_VOICE,
    HELIOS_AUDIO_PLAY_TYPE_POC,
    HELIOS_AUDIO_PLAY_TYPE_MAX
}Helios_AudPlayerType;


/**
 * AUDIO PLAY SPEAK LEVEL
 */
typedef enum
{
    HELIOS_AUDIOHAL_SPK_MUTE         = 0,
    HELIOS_AUDIOHAL_SPK_VOL_1,	     
    HELIOS_AUDIOHAL_SPK_VOL_2,
    HELIOS_AUDIOHAL_SPK_VOL_3,
    HELIOS_AUDIOHAL_SPK_VOL_4,
    HELIOS_AUDIOHAL_SPK_VOL_5,
    HELIOS_AUDIOHAL_SPK_VOL_6,
    HELIOS_AUDIOHAL_SPK_VOL_7,
    HELIOS_AUDIOHAL_SPK_VOL_8,
    HELIOS_AUDIOHAL_SPK_VOL_9,
    HELIOS_AUDIOHAL_SPK_VOL_10,
    HELIOS_AUDIOHAL_SPK_VOL_11,	// 11
	HELIOS_AUDIOHAL_SPK_VOL_QTY	// 12
}Helios_AudHALSPKLevel;



typedef enum
{
	HELIOS_AUD_RECORD_ERROR = -1,
	HELIOS_AUD_RECORD_START = 0,   //audio recorder start record
	HELIOS_AUD_RECORD_DATA,		//record data comming
	HELIOS_AUD_RECORD_PAUSE,	    //record has been paused by call or pause api
	HELIOS_AUD_RECORD_CLOSE,		//record closed
	HELIOS_AUD_RECORD_FINISHED = HELIOS_AUD_RECORD_CLOSE,
	HELIOS_AUD_RECORD_RESUME,		//resume from pause
}Helios_EnumAudRecordState;

typedef enum
{
    HELIOS_REC_TYPE_NONE = 0,
    HELIOS_REC_TYPE_MIC,
    HELIOS_REC_TYPE_VOICE,
}Helios_AudRecordType;

typedef enum 
{
	HELIOS_RECORD_FILE = 0,
	HELIOS_RECORD_STREAM,
}Helios_AudRecordDirect;

typedef enum
{
	HELIOS_TWO_WAY,
	HELIOS_PHONE_TO_MODULE,
	HELIOS_MODULE_TO_PHONE,
}Helios_Mute_VoiceCall;



typedef enum
{
	HELIOS_AUD_PLAYER_ERROR = -1,
	HELIOS_AUD_PLAYER_START = 0,	//audio player start play
	HELIOS_AUD_PLAYER_PAUSE,		//audio player has been paused by call or pause api
	HELIOS_AUD_PLAYER_FINISHED,    //audio player finish current playing
	HELIOS_AUD_PLAYER_CLOSE,       //audio player closed
	HELIOS_AUD_PLAYER_RESUME,      //resume player from pause
	HELIOS_AUD_PLAYER_MOREDATA,
	HELIOS_AUD_PLAYER_NODATA_STRAT,
	HELIOS_AUD_PLAYER_DATA_RESUME,
	HELIOS_AUD_PLAYER_REQURST_CLOSE
}Helios_EnumAudPlayerState;

typedef enum
{
    HELIOS_AUDIO_FORMAT_UNKNOWN, ///< placeholder for unknown format
    HELIOS_AUDIO_FORMAT_PCM,     ///< raw PCM data
    HELIOS_AUDIO_FORMAT_WAVPCM,  ///< WAV, PCM inside
    HELIOS_AUDIO_FORMAT_MP3,     ///< MP3
    HELIOS_AUDIO_FORMAT_AMRNB,   ///< AMR-NB
    HELIOS_AUDIO_FORMAT_AMRWB,   ///< AMR_WB
    HELIOS_AUDIO_FORMAT_AAC,    ///< AAC
    HELIOS_AUDIO_FORMAT_M4A,    ///< M4A
    HELIOS_AUDIO_FORMAT_TS,     ///< TS
    HELIOS_AUDIO_FORMAT_FLV,
    HELIOS_AUDIO_FORMAT_RTMP,

	HELIOS_AUDIO_FORMAT_MAX
} Helios_AudStreamFormat;

typedef enum 
{
    HELIOS_TTS_EVT_INIT,
    HELIOS_TTS_EVT_DEINIT,
    HELIOS_TTS_EVT_PLAY_START,
    HELIOS_TTS_EVT_PLAY_STOP,
    HELIOS_TTS_EVT_PLAY_FINISH,
    HELIOS_TTS_EVT_PLAY_FAILED,
} Helios_TTSENvent;

#define HELIOS_WTTS_MOD_FLAG        (1 << 7)
#define HELIOS_WTTS_UL_FLAG         (1 << 6)
#define HELIOS_WTTS_DL_FLAG         (1 << 5)

#define HELIOS_WTTS_MOD_UL_DL(mode)    (mode | HELIOS_WTTS_MOD_FLAG | HELIOS_WTTS_UL_FLAG | HELIOS_WTTS_DL_FLAG)
#define HELIOS_WTTS_MOD_UL(mode)       (mode | HELIOS_WTTS_MOD_FLAG | HELIOS_WTTS_UL_FLAG)
#define HELIOS_WTTS_MOD_DL(mode)       (mode | HELIOS_WTTS_MOD_FLAG | HELIOS_WTTS_DL_FLAG)


/**
 * \brief AMR-WB modes
 */
typedef enum
{
	HELIOS_AMRWB_MODE_NONE = 0,
		
    HELIOS_AMRWB_MODE_660, 	///< 6.60 kbps
    HELIOS_AMRWB_MODE_885,     ///< 8.85 kbps
    HELIOS_AMRWB_MODE_1265,    ///< 12.65 kbps
    HELIOS_AMRWB_MODE_1425,    ///< 14.25 kbps
    HELIOS_AMRWB_MODE_1585,    ///< 15.85 kbps
    HELIOS_AMRWB_MODE_1825,    ///< 18.25 kbps
    HELIOS_AMRWB_MODE_1985,    ///< 19.85 kbps
    HELIOS_AMRWB_MODE_2305,    ///< 23.05 kbps
    HELIOS_AMRWB_MODE_2385,    ///< 23.85 kbps

	HELIOS_AMRWB_MODE_MAX,
} Helios_AmrwbMode;

typedef enum
{
	HELIOS_AMRNB_MODE_NONE = 0,

    HELIOS_AMRNB_MODE_475, 	///< 4.75 kbps
    HELIOS_AMRNB_MODE_515,     ///< 5.15 kbps
    HELIOS_AMRNB_MODE_590,     ///< 5.90 kbps
    HELIOS_AMRNB_MODE_670,     ///< 6.70 kbps
    HELIOS_AMRNB_MODE_740,     ///< 7.40 kbps
    HELIOS_AMRNB_MODE_795,     ///< 7.95 kbps
    HELIOS_AMRNB_MODE_1020,    ///< 10.2 kbps
    HELIOS_AMRNB_MODE_1220,    ///< 12.2 kbps

	HELIOS_AMRNB_MODE_MAX,
} Helios_AmrnbMode;



typedef enum
{
	HELIOS_JUMP_FORWARD = 0,

    HELIOS_JUMP_BACK, 

} Helios_Stream_Jump_Dir;

typedef enum
{
		HELIOS_VC_HANDSET = 0,	
		HELIOS_VC_HANDSFREE,
		HELIOS_VC_HEADSET,		//with mic
		HELIOS_VC_HEADPHONE,	//without mic
		HELIOS_VC_BT,
		HELIOS_VC_MAXCOUNT,
	
		HELIOS_AC_HANDSET = 64, 
		HELIOS_AC_HANDSFREE,
		HELIOS_AC_HEADSET,		//with mic
		HELIOS_AC_HEADPHONE,	//without mic
		HELIOS_AC_BT,
	
		HELIOS_AC_FM,
		HELIOS_AC_MAXCOUNT,
	
		QL_PROFILE_ID_ENUM_16_BIT = 0x7FFF //16bit enum compiling enforcement	 
} HELIOS_PROFILE_ID;


typedef enum
{
    Helios_CODEC_TYPE_INTERNAL,
    Helios_CODEC_TYPE_EXTERNAL,
}Helios_Codec_type;

typedef enum
{
	Helios_PCM_FS_32,
	Helios_PCM_FS_64,
	Helios_PCM_FS_128,
	Helios_PCM_FS_256,
	Helios_PCM_FS_512,
	Helios_PCM_FS_1024,
	Helios_PCM_FS_2048,
	Helios_PCM_FS_MAX,
}Helios_pcm_bclk;
typedef enum
{
	Helios_PCM_CODEC_SAMPLE_8000 = 8000,
	Helios_PCM_CODEC_SAMPLE_16000 = 16000,
	Helios_PCM_CODEC_SAMPLE_32000 = 32000,
	Helios_PCM_CODEC_SAMPLE_48000 = 48000,
}Helios_pcm_codec_sample;

typedef enum
{
	HELIOS_AUD_VOICECALL_NB	= 0,	//not volte mode
	HELIOS_AUD_VOICECALL_WB = 5		//volte mode
}Helios_AUD_CALLMODE_E;

typedef struct
{
	Helios_pcm_bclk pcmbclk;
	Helios_pcm_codec_sample sample;
    char is_i2s;
}Helios_ExternalCodecPcm_config;

typedef struct
{
	Helios_AmrwbMode amrwb_mode;
	int reserve[2];
}Helios_AmrwbParam;

typedef struct
{
	Helios_AmrnbMode amrnb_mode;
	int reserve[2];
}Helios_AmrnbParam;



typedef struct
{
	int channels;
	int samplerate;
	int len_size;

	Helios_AmrwbParam amrwb_param;
	Helios_AmrnbParam amrnb_param;
	
}Helios_AudRecordConfig;

/**
 * audio play callback function,different platforms need to implement this function according to platform characteristics
 */
typedef int(*helios_cb_on_player)(char *p_data, size_t len, Helios_EnumAudPlayerState state);


typedef int(*helios_cb_on_record)(char *p_data, size_t len, Helios_EnumAudRecordState state);

typedef void (*helios_tts_cb_type)(Helios_TTSENvent event);
typedef void (*helios_audio_cb_type)(Helios_TTSENvent event);
typedef void (*helios_audio_pa_cb_t)(unsigned int event);

// only for EC600U
// headset plug/button

typedef enum
{
    HELIOS_HEADSET_CBTYPE_NONE     = 0x00,

    HELIOS_HEADSET_CBTYPE_PLUG_IN  = 0x01,
    HELIOS_HEADSET_CBTYPE_PLUG_OUT = 0x02,

    HELIOS_HEADSET_CBTYPE_BTN_DOWN = 0x03,    // press headset button
    HELIOS_HEADSET_CBTYPE_BTN_UP   = 0x04,    // release headset button

    HELIOS_HEADSET_CBTYPE_MAX      = 0xFF,
}HELIOS_HEADSET_CBTYPE_E;


typedef enum
{
    HELIOS_HEADSET_PLUGSTATUS_OUT = 0,
    HELIOS_HEADSET_PLUGSTATUS_IN  = 1,
}HELIOS_HEADSET_PLUGSTATUS_E;

typedef enum
{
	HELIOS_AUD_SPKPA_TYPE_NONE = -1, //audio not init done

    HELIOS_AUD_SPKPA_TYPE_CLASSAB,
    HELIOS_AUD_SPKPA_TYPE_CLASSD,
    
    HELIOS_AUD_SPKPA_TYPE_MAX
} Helios_Audio_Speakerpa_Type;

typedef enum
{
	HELIOS_AUD_START_FIRST_DEC_THEN_PA = 0,   //open codec first and then pa 
    HELIOS_AUD_START_FIRST_PA_THEN_DEC = 1,   //open pa first and then codec
    HELIOS_AUD_START_MODE_MAX
} HELIOS_AUDIO_START_MODE_E;

typedef enum
{
	HELIOS_AUD_END_FIRST_DEC_THEN_PA = 0,   //close codec first and then pa 
    HELIOS_AUD_END_FIRST_PA_THEN_DEC = 1,   //close pa first and then codec
    HELIOS_AUD_END_MODE_MAX
} HELIOS_AUDIO_END_MODE_E;

typedef enum
{
	Helios_PCM_CODEC_AboutToOpen = 0,
	Helios_PCM_CODEC_Opened,
	Helios_PCM_CODEC_AboutToClose,
	Helios_PCM_CODEC_Closed,
}Helios_pcm_codec_event;



typedef void (*Helios_headset_callback)(HELIOS_HEADSET_CBTYPE_E cb_type, uint32_t param);
typedef void(*helios_pcm_codec_cb_t)(Helios_pcm_codec_event event);

// only for EC600U end


typedef struct {
	Helios_AudRecordConfig *record_para;
	Helios_AudStreamFormat format;
	Helios_AudRecordType type;
	helios_cb_on_record cb;	
}Helios_AUDRecordInitStruct;

typedef struct{
    /* data */
    long unsigned int bytenow;
    long unsigned int ofs;

}Helios_JumpInfoStruct;
/**
 * @brief:
 *      Audio init
 *
 * @param:
 * @return:
 *      audio init result, 0 for success,-1 for failure
 */
int Helios_Audio_Init(void);

/**
 * @brief:
 *      Audio deinit
 *
 * @param:
 * @return:
 *      audio deinit result, 0 for success,-1 for failure
 */
int Helios_Audio_Deinit(void);


/**
 * @brief:
 *      Audio record start
 *
 * @param:
 *      \name        	[in]    - Audio file name
 *      \record_para    [in]    - Audio parameter structure
 *      
 * @return:
 *      audio record start result, 0 for success,-1 for failure
 */
int Helios_Audio_FileRecordStart(char* name, Helios_AUDRecordInitStruct* record_para);

/**
 * @brief:
 *      Audio record stop
 *
 * @param:
 *      
 * @return:
 *      audio record stop result, 0 for success,-1 for failure
 */
int Helios_Audio_FileRecordStop();

/**
 * @brief:
 *      Audio record start
 *
 * @param:
 *      \record_para    [in]    - Audio parameter structure
 *      
 * @return:
 *      audio record start result, 0 for success,-1 for failure
 */
int Helios_Audio_StreamRecordStart(Helios_AUDRecordInitStruct* record_para);

/**
 * @brief:
 *      Audio record stop
 *
 * @param:
 *      
 * @return:
 *      audio record stop result, 0 for success,-1 for failure
 */
int Helios_Audio_StreamRecordStop();



/**
 * @brief:
 *      Start playing the audio file.
 *
 * @param:
 *      \file_name        [in]    - the name of the file to be played
 *      \type             [in]    - the audio play type 0-NONE,1-Local,2-Voice,3-POC,4-Max type
 *      \outputtype       [in]    - Audio channel 0:receiver 1:headphone 2:speaker
 *      \usr_cb           [in]    - play callback
 * @return:
 *      start play audio file result, 0 for success,-1 for failure
 */
int Helios_Audio_FilePlayStart(char *file_name, Helios_AudPlayerType type, helios_cb_on_player usr_cb);



/**
 * @brief:
 *      Stop playing the audio file.
 *
 * @param:
 *      NULL
 * @return:
 *      stop play audio file result, 0 for success,-1 for failure
 */
int Helios_Audio_FilePlayStop(void);

/**
 * @brief:
 *      Start playing the audio file.
 *
 * @param:
 *      \format        	[in]    - Audio format
 *      \buf            [in]    - audio buf
 *      \size           [in]    - buf size
 *      \type           [in]    - the audio play type 0-NONE,1-Local,2-Voice,3-POC,4-Max type
 *      \outputtype     [in]    - Audio channel 0:receiver 1:headphone 2:speaker
 *      \usr_cb         [in]    - play callback
 * @return:
 *      start play audio file result, 0 for success,-1 for failure
 */
int Helios_Audio_StreamPlayStart(Helios_AudStreamFormat format, const void *buf, size_t size, Helios_AudPlayerType type, Helios_AudOutputType outputtype, helios_cb_on_player usr_cb);


/**
 * @brief:
 *      Stop playing the audio file.
 *
 * @param:
 *      NULL
 * @return:
 *      stop play audio file result, 0 for success,-1 for failure
 */
int Helios_Audio_StreamPlayStop(void);

/**
 * @brief:
 *		amr record dtx enable.
 *
 * @param:
 *		on_off
 *       true: enabe
 *       false: disale
 * @return:
 *		0
 */
int Helios_Audio_AmrEnc_Dtx_Enable(int *on_off, int rd_flag);


/**
 * @brief:
 *      tts init
 *
 * @param:
 *
 *      \cb            [in]    - tts callback
 *
 * @return:
 *      audio init result, 0 for success,-1 for failure
 */
int Helios_TTS_Init(helios_tts_cb_type cb);

/**
 * @brief:
 *      tts deinit
 *
 * @param:
 * @return:
 *      audio deinit result, 0 for success,-1 for failure
 */
int Helios_TTS_Deinit(void);


/**
 * @brief:
 *      tts start
 *
 * @param:
 *      \textString           	[in]    - tts string
 *      \Len            		[in]    - string length
 *      \outputtype     		[in]    - Audio channel 0:receiver 1:headphone 2:speaker
 *
 * @return:
 *      audio start result, 0 for success,-1 for failure
 */
int Helios_TTS_Start(int new_mode, const char* textString, size_t str_Len);

/**
 * @brief:
 *      tts stop
 *
 * @param:
 *
 * @return:
 *      audio stop result, 0 for success,-1 for failure
 */
int Helios_TTS_Stop(void);

/**
 * @brief:
 *      tts SetSpeed
 *
 * @param:
 *      \value           	[in]    - tts speed
 *
 * @return:
 *      audio start result, 0 for success,-1 for failure
 */
int Helios_TTS_SetSpeed(int value);

/**
 * @brief:
 *      tts start
 *
 * @param:
 *      \value           	[in]    - tts speed
 *
 * @return:
 *      get tts status result, 0 for Not running,1 for running
 */
int Helios_TTS_GetStatus(void);



/**
 * @brief:
 *      set audio volume
 *
 * @param:
         \type    audio play type 0-NONE,1-Local,2-Voice,3-POC,4-Max type
 *       \vol     set volume  0-12
 * @return:
 *      set audio volume result,0 for success,-1 for failure
 */
int Helios_Audio_SetVolume(Helios_AudPlayerType type, Helios_AudHALSPKLevel vol);


/**
 * @brief:
 *      get audio volume
 * @param:
 *       \type    audio play type 0-NONE,1-Local,2-Voice,3-POC,4-Max type
 * @return:
 *      volume value  0-12
 */
int Helios_Audio_GetVolume(Helios_AudPlayerType type);


/**
 * @brief:
 *      set audio gain
 * @param:
 * @return:
 *      
 */
int Helios_Audio_GainSet(short int codec_gain, char dsp_gain);

/**
 * @brief:
 *      get audio gain
 * @param:
 * @return:
 *      
 */
int Helios_Audio_GainGet(short int *codec_gain, char *dsp_gain);

//stephen add
int Helios_Get_Audio_State(); 
int Helios_Audio_SetAudioChannle(Helios_AudOutputType outputtype);

//elian add
int Helios_Audio_SetOutputChannle(Helios_AudOutputType output_type);
int Helios_Audio_SetInputChannle(Helios_AudInputType input_type);

char* Helios_Audio_FileNameSet(char *filename);

int Helios_TTS_SetSpeed(int value);
int Helios_TTS_GetSpeed(void);
int Helios_TTS_SetVolume(int value);
int Helios_TTS_GetVolume(void);
#if defined (PLAT_Unisoc)
int Helios_TTS_SetDigits(int value);
int Helios_TTS_GetDigits(void);
#endif
int Helios_Audio_SetToneVolume(Helios_AudHALSPKLevel vol);
int Helios_Audio_SetPa(int gpio_num);
int Helios_Audio_SetPaCallback(Helios_AudOutputType type, helios_audio_pa_cb_t cb);
int Helios_Set_Audio_Pa_Type(Helios_Audio_Speakerpa_Type pa_type);
Helios_Audio_Speakerpa_Type Helios_Get_Audio_Pa_Type(void);


int Helios_Audio_SetDigGainTable(Helios_AudPlayerType type, signed short *gain);


int audio_channel_check(int channel);

#if defined (PLAT_Unisoc) || defined(PLAT_Unisoc_8910_R05) || defined(PLAT_Unisoc_8910_R06)

Helios_JumpInfoStruct Helios_Audio_Stream_Jump(int second,Helios_Stream_Jump_Dir drection);

int Helios_Audio_Stream_Pause(void);

int Helios_Audio_Stream_Continue(void);

long unsigned int Helios_Audio_Stream_Seek(uint32_t second);

int Helios_Audio_SetDSPGainTable(uint32_t profile_id, int16_t* gain);

int Helios_aud_set_calib_real_time(int real_time);
#endif

int Helios_Audio_SetDSPGainTable(uint32_t profile_id, int16_t* gain);
int Helios_Audio_SetCodecGainTable(uint32_t profile_id, int32_t level, uint32_t* data);
uint32_t Helios_get_current_profileID();


#if defined(BOARD_EC600MCN_LA) || defined(BOARD_EC600MCN_LA_POC_XBND)|| defined(BOARD_EC600MCN_LA_POC_QS) \
    || defined(BOARD_EC600MCN_LA_VOLTE) || defined(BOARD_EC600MCN_LA_HJT) || defined(BOARD_EC600MCN_LC) \
    || defined(BOARD_EC600MCN_LE) || defined(BOARD_EC600MCN_LF) || defined(BOARD_EC600MCN_LE_POC_XBND) \
	|| defined(BOARD_EC600MCN_LA_POC_ZZD) || defined(BOARD_EC600MCN_LE_POC_ZZD) || defined(BOARD_EC600MCN_LF_SPISD)\
	|| defined(BOARD_EC600MCN_LE_POC_QS) || defined(BOARD_EC600MCN_CC) || defined(BOARD_EC600MCN_LE_VOLTE) \
	|| defined(BOARD_EC600MCN_CC_EXT)|| defined(BOARD_EC600MCN_LF_SLPOC) || defined(BOARD_EC600MCN_CC_EXT_TTS) \
    || defined(BOARD_EC800MCN_CC_TTS) || defined(BOARD_EC800KCN_CC_TTS) || defined(BOARD_EC600KCN_CC_TTS) \
	|| defined(BOARD_EC600MEU_LA_POC_XBND) || defined(BOARD_EC600MLA_LA_POC_XBND)

int Helios_Audio_Play_Tone(int f1, int f2);
#else
int Helios_Audio_Play_Tone(int tone, uint32_t duration);
#endif

int Helios_Audio_Stop_Tone(void);
int Helios_Audio_Play_DTMF(int dtmf, uint32_t duration);
int Helios_Audio_Stop_DTMF(void);

void Helios_pcm_play_stop_skip_pa(void);

/**
 * @brief:
 *      switch codec type
 * @param:
        type
        config
 * @return:
 *      
 */
void Helios_Audio_Codec_Switch(Helios_Codec_type type, Helios_ExternalCodecPcm_config *config);

#if defined (PLAT_Unisoc) || defined(PLAT_Unisoc_8910_R05) || defined(PLAT_Unisoc_8910_R06)
void Helios_Audio_PCM_para_set(int samplerate, int channels);

#endif

#if defined (PLAT_Unisoc) || defined (PLAT_ASR) || defined(PLAT_Unisoc_8910_R05) || defined(PLAT_Unisoc_8910_R06)
int helios_audio_getInitState(void);
#endif

#if defined (PLAT_ASR) || defined(PLAT_ASR_1606) || defined(PLAT_ASR_1609) || defined(PLAT_ASR_1602)
int Helios_mp3_Clear_Cache();

int Helios_mp3_get_cache_size();


#endif
void Helios_mp3_stream_close_flag(unsigned char value);

typedef struct {
	unsigned int channels; //������
	unsigned int samplerate; //������
	unsigned int periodcnt; // ��λÿ20ms�ϲ㻺���buff��С, value:2~8
} Helios_PCM_CONFIG_T;


#if CONFIG_AUDIO
void *Helios_PCM_Open(unsigned int channels, unsigned int samplerate, unsigned int flags);
#else
void *Helios_PCM_Open(Helios_PCM_CONFIG_T *pcm_para, unsigned int flags);
#endif
int Helios_PCM_Close(void* handle);
int Helios_PCM_Write(void* handle, void* data, unsigned int count);
int Helios_PCM_Read(void* handle, void* data, unsigned int count);
int Helios_set_mic_channel(int channel);

void Helios_aud_data_done(void);

void *Helios_Aud_PWM_Open(int pwm_n, unsigned int channels, unsigned int samplerate, unsigned int flags);
int Helios_Aud_PWM_Close(void* handle);
int Helios_Aud_PWM_Write(void* handle, void* data, unsigned int count);


#if (defined(BOARD_EC600UCN_LB_TTS)	\
	|| defined(BOARD_EC600UCN_LB)	\
	|| defined(BOARD_EC600UCN_LC)	\
	|| defined(BOARD_EC600UEU_AB)	\
	|| defined(BOARD_EC600UEU_AB_POC)	\
	|| defined(BOARD_EC600UCN_LB_VOLTE)	\
	|| defined(BOARD_EC600UEU_AB_VOLTE)	\
	|| defined(BOARD_EC600UCN_LB_AP)	\
	|| defined(BOARD_EC600UCN_LB_ICC)	\
	|| defined(BOARD_EC600UCN_LB_EXTFS4M)	\
	|| defined(BOARD_EC600UCN_LB_EXTFS8M)	\
	|| defined(BOARD_EC600UCN_LB_BT))
int Helios_headset_init(Helios_headset_callback callback);
int Helios_headset_deinit();
HELIOS_HEADSET_PLUGSTATUS_E Helios_headset_plug_status_get();

#endif

int Helios_Aud_PWM_Set_Volume(int vol);
int Helios_Aud_PWM_Get_Volume();
int Helios_Aud_PWM_Set_Gain_Value(float min, float max);

#ifdef BOARD_EC600UCN_LB_YDWL
typedef enum {
    YDWL_TTS_EVT_INIT         = 0,
    YDWL_TTS_EVT_DEINIT,
    YDWL_TTS_EVT_PLAY_START,
    YDWL_TTS_EVT_COMPOSITE_OVER,      //语音合成完成，但播放未完�?
    YDWL_TTS_EVT_PLAY_STOP,           //not used
    YDWL_TTS_EVT_PLAY_FINISH,         //TTS语音播放完成
    YDWL_TTS_EVT_PLAY_FAILED,         //not used
    YDWL_TTS_EVT_PLAY_INTERRUPT,

}YDWL_TTS_ENVENT_E;

typedef void (*ydwl_tts_cb_type)(int id, YDWL_TTS_ENVENT_E status);

void Helios_ydwl_tts_init(ydwl_tts_cb_type usr_cb);
void Helios_ydwl_tts_play(const char* string, unsigned int len);
#endif

int Helios_mute_voicecall(Helios_Mute_VoiceCall direction, unsigned char mute, unsigned char time);

void Helios_set_audio_read_delay(int time);

int Helios_aud_set_icmic_gain(Helios_AUD_CALLMODE_E mode, Helios_AudOutputType type, int ana_gain, int adc_gain);


int Helios_PCM_Codec_Event_Callback_Register(helios_pcm_codec_cb_t cb);

int Helios_Audio_Iic_Write(unsigned char dev_addr, unsigned short reg_addr, unsigned char size, unsigned short val);

int Helios_Audio_Iic_Read(unsigned char dev_addr, unsigned short reg_addr, unsigned char size, void *p_val);

typedef enum
{
	HELIOS_PCM_NONE = 0,
	HELIOS_PCM_LOCAL,
	HELIOS_PCM_VOICE_CALL,
	HELIOS_PCM_POC,

	HELIOS_PCM_MAX,
}Heliso_PCM_Path;

typedef enum
{
	HELIOS_POC_TYPE_MIN = -1,

	HELIOS_POC_TYPE_HALF_DUPLEX,
	HELIOS_POC_TYPE_FULL_DUPLEX,

	HELIOS_POC_TYPE_MAX,
}Helios_PCM_POC_Type;


#if defined(PLAT_Unisoc) || defined(PLAT_Unisoc_8910_R05)
int Helios_set_pcm_type(char type, char poc_mode);
int Helios_start_poc_mode(int mode);
int Helios_stop_poc_mode(void);
#endif


#if defined (PLAT_ASR_1606)
 /* QDAI config structure */
typedef struct {
	char io;
	char mode;
	char fsync;
    char clock;
	char format;
	char sample;
	char num_slots;
	char slot_mapping;
}Helios_QdaiStruct;
int Helios_customer_set_qdai_cfg(Helios_QdaiStruct qdai);

int Helios_Audio_Set_Denoise(unsigned char set);

int Helios_Audio_Get_Denoise(unsigned char *flag);

int Helios_Audio_Check_Denoise_Licenses_Verify(unsigned char *flag);

int Helios_Audio_Get_Denoise_Lib_Version(unsigned char *version);

int Helios_PCM_Get_Write_Frame_Count(void* handle);

int Helios_PCM_Reset_Write_Buffer(void* handle);
#endif

#ifdef __cplusplus
} /*"C" */
#endif

#endif

