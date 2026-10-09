/* QDisplay native application for the verified EC600UCNLB R03A04M08 core.
 * USB receives in one task; frame assembly and MIPI submission in another.
 * No per-frame allocation, interpreter, image decoder, or cellular data use.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "helios_os.h"
#include "helios_uart.h"
#include "helios_gpio.h"
#include "helios_usb.h"
#include "helios_lcd.h"
#include "osi_api.h"
#include "native_protocol.h"
#include "panel_init.h"
#include "core_guard.h"
#include "waiting_page.h"
#include "brightness_osd.h"
#include "power_policy.h"
#include "lz4.h"
#define XXH_INLINE_ALL
#define XXH_NO_XXH3
#include "xxhash.h"

typedef struct {
    qd_header h;
    uint32_t received_us;
    uint32_t status;
    uint8_t data[QD_BLOCK_BYTES] __attribute__((aligned(32)));
} slot_t;
static slot_t slots[QD_SLOTS];
static Helios_MsgQ_t free_slots, ready_slots;
static Helios_Sem_t receive_event;
static uint8_t *frame;
static uint8_t *decode_storage, *decode_pixels;
static uint32_t frame_offset;
static bool assembling, panel_ready;
static bool committed_valid;
static uint32_t committed_hash;
static uint32_t panel_stage;
static bool core_checked, core_matches;
static void *usb_channel;
static int (*usb_read)(void *,void *,unsigned);
static uint32_t frame_rx_us, frame_decode_us;
static qd_power_state power_state={.awake=true,.brightness=100};
static uint8_t keys_available;
static bool waiting_drawn;
static const Helios_UARTNum data_port=HELIOS_UART3;
/* R03 maps UART3 to USB VCOM channel 5. Helios_UART_Write adds a 1 KB,
 * timer-driven Python-console buffer; use the exported immediate writer. */
extern int ql_uart_write(int port, const void *data, unsigned length);
/* The R03 export reads three BYTE fields, unlike the SDK's R01 enum fields.
 * Keep the exact-core guard and pass the layout observed in the R03 binary. */
typedef struct { uint8_t dir, pull, value; } r03_gpio_config;
extern int r03_gpio_init(Helios_GPIONum pin, const r03_gpio_config *config)
    __asm__("Helios_GPIO_Init");

static uint32_t micros(void) { return (uint32_t)osiUpTimeUS(); }
static uint32_t millis(void) { return (uint32_t)(osiUpTimeUS()/1000u); }
#include "backlight.h"
#include "brightness_osd_impl.h"
#include "audio_impl.h"
static void uart_event(uint64_t kind, Helios_UARTNum port, uint64_t count)
{
    (void)kind; (void)port; (void)count;
    if (receive_event) Helios_Semaphore_Release(receive_event);
}
static bool read_exact(void *out, size_t size, uint32_t timeout_ms)
{
    uint8_t *p=out;
    uint32_t last=micros();
    while(size) {
        unsigned count=size>16384?16384:size;
        int n;
        if(usb_read) {
            if(((int (*)(int))0x6020b4b5)(5)==0) {
                n=usb_read(usb_channel,p,count);
                ((void (*)(int))0x6020b519)(5);
            } else n=-1;
        } else n=Helios_UART_Read(data_port,p,count);
        if(n>0 && (size_t)n<=size) {p+=n;size-=n;last=micros();continue;}
        if((uint32_t)(micros()-last)>=timeout_ms*1000u) return false;
        /* Callback wakeup prevents a polling sleep on every USB fragment. */
        Helios_Semaphore_Acquire(receive_event,10);
    }
    return true;
}
static bool write_all(const void *data,size_t length)
{
    const uint8_t *p=data;
    uint32_t start=micros();
    while(length) {
        int n=ql_uart_write(5,p,length);
        if(n>0 && (size_t)n<=length) {p+=n;length-=n;continue;}
        if((uint32_t)(micros()-start)>3000000u) return false;
        Helios_msleep(1);
    }
    return true;
}
static void reply(uint32_t seq, uint32_t status, uint32_t rx, uint32_t decode,
                  uint32_t draw, uint32_t detail)
{
    struct {qd_header h;qd_reply r;} msg={0};
    msg.r=(qd_reply){status,rx,decode,draw,Helios_GetAvailableMemorySize(),detail};
    msg.h.magic=QD_MAGIC;msg.h.version=QD_VERSION;msg.h.type=QD_ACK;
    msg.h.seq=seq;msg.h.length=sizeof(msg.r);msg.h.raw_length=sizeof(msg.r);
    msg.h.payload_hash=XXH32(&msg.r,sizeof(msg.r),0);
    msg.h.header_hash=XXH32(&msg.h,28,0);
    write_all(&msg,sizeof(msg));
}
static int panel_start(void)
{
    if(panel_ready) return 0;
    if(!core_checked) {
        core_matches=XXH32((const void*)0x60010000,R03_CORE_SIZE,0)==R03_CORE_XXH32;
        core_checked=true;
    }
    if(!core_matches) {panel_stage=10;return -1;}
    r03_gpio_config gpio={HELIOS_GPIO_OUTPUT,HELIOS_PULL_NONE,HELIOS_LVL_LOW};
    panel_stage=1;
    if(r03_gpio_init(HELIOS_GPIO27,&gpio)) return -1;
    panel_stage=2;
    if(r03_gpio_init(HELIOS_GPIO8,&gpio)) return -1;
    Helios_MIPIInitStruct p={0};
    p.init_data=(void*)panel_init;p.init_data_len=sizeof(panel_init);
    p.width=QD_WIDTH;p.hight=QD_HEIGHT;p.bpp=16;
    /* R03's hardware interface enum is not Helios_LCDType from the R01 SDK.
     * Its panel-start gate accepts 2; QuecPython's MIPI caller defaults to 2.
     * Passing HELIOS_LCD_TYPE_MIPI (3) allocates a buffer but skips hardware. */
    p.lcd_interface=2;
    p.data_lane=2;p.trans_mode=2;p.bllp_enable=true;
    p.h_sync_active=20;p.h_back_porch=40;p.h_front_porch=40;
    p.v_sync_active=3;p.v_back_porch=11;p.v_front_porch=16;
    p.frame_rate=60;p.rst_Polarity=1;p.dsi_pclk_rate=100;
    panel_stage=3;
    if(Helios_LCD_MIPIInit(&p)) return -1;
    panel_stage=4;
    panel_ready=true;
    return 0;
}
static int publish_frame(void)
{
    if(panel_start()) return -1;
    /* The frame is already in the LCD-owned buffer. R03's full-frame writer
     * DMA-copies its argument INTO that buffer; using identical source and
     * destination corrupts RAM after the first submission (hardware tested).
     * Mirror its cache-clean and LCD transfer trigger without the self-copy.
     * These addresses are guarded by the exact R03 AP fingerprint above.
     * Completion is still NOT a vblank/tear-free ACK. */
    volatile uint32_t *transfer=(volatile uint32_t*)0x08807038;
    *transfer|=1u;
    __asm__ volatile("dsb sy" ::: "memory");
    if(!bl_apply(power_state.awake,power_state.brightness)) {
        panel_stage=6;return -1;
    }
    return 0;
}
static int submit_frame(void)
{
    if(panel_start()) return -1;
    ((void (*)(const void*,uint32_t))0x60137213)(frame,QD_FRAME_BYTES);
    return publish_frame();
}
static bool need_frame(void)
{
    uint32_t control;
    __asm__ volatile("mrc p15, 0, %0, c1, c0, 0" : "=r"(control));
    /* The optimized decoder requires ordinary RAM unaligned loads. Fail
     * before invoking it if a different boot configuration enables faults. */
    if(control&2u) {panel_stage=11;return false;}
    if(!frame) {
        if(panel_start()) return false;
        /* The R03 heap cannot fit TWO 2 MB buffers. Assemble directly in its
         * allocated scanout instead of allocating a duplicate staging frame. */
        uintptr_t address=*(volatile uint32_t*)0x809dd390;
        volatile uint32_t *dimensions=(volatile uint32_t*)0x809dd37c;
        if(dimensions[0]!=QD_WIDTH || dimensions[1]!=QD_HEIGHT ||
           address<0x809e0000 || address>0x80f00000-QD_FRAME_BYTES || (address&3)) return false;
        frame=(uint8_t*)address;
    }
    /* A bounded block staging area fits the remaining core heap. Do not let
     * LCD scanout observe LZ4's temporary match-expansion/wild-copy bytes.
     * It is allocated once, never per frame; no second 2 MB framebuffer. */
    if(!decode_pixels) {
        decode_storage=malloc(QD_BLOCK_BYTES+31u);
        if(!decode_storage) {panel_stage=12;return false;}
        decode_pixels=(uint8_t*)(((uintptr_t)decode_storage+31u)&~(uintptr_t)31u);
    }
    return frame!=NULL;
}
static bool copy_span(uint8_t *destination,const void *source,uint32_t length)
{
    if(((uintptr_t)source|(uintptr_t)destination)&3u) {
        memcpy(destination,source,length);
        return true;
    }
    /* Normal RAM, 4-byte aligned. Use paired ARM burst loads/stores instead
     * of the core memcpy's eight individual instructions per 16 bytes.
     * Each store publishes complete pairs of RGB565 pixels. Only GPRs are
     * used: no assumptions about RTOS NEON/FPU context preservation. */
    uint32_t blocks=length/32u;
    uint32_t tail=length%32u;
    if(blocks) {
        __asm__ volatile(
            "1: ldmia %1!, {r3-r10}\n"
            "stmia %0!, {r3-r10}\n"
            "subs %2, %2, #1\n"
            "bne 1b\n"
            : "+r"(destination), "+r"(source), "+r"(blocks)
            : : "r3","r4","r5","r6","r7","r8","r9","r10","cc","memory");
    }
    if(tail) memcpy(destination,source,tail);
    return true;
}
static bool copy_pixels(const void *source,uint32_t length)
{
    if(!osd_drawn) return copy_span(frame+frame_offset,source,length);
    uint32_t end=frame_offset+length,position=frame_offset;
    const uint8_t *input=source;
    for(unsigned y=0;y<QD_OSD_HEIGHT && position<end;y++) {
        uint32_t first=((QD_OSD_Y+y)*QD_WIDTH+QD_OSD_X)*2u;
        uint32_t last=first+QD_OSD_WIDTH*2u;
        if(last<=position || first>=end) continue;
        if(position<first) {
            copy_span(frame+position,input+position-frame_offset,first-position);position=first;
        }
        uint32_t stop=end<last?end:last;
        memcpy(osd_backup+y*QD_OSD_WIDTH*2u+position-first,input+position-frame_offset,stop-position);
        position=stop;
    }
    if(position<end) copy_span(frame+position,input+position-frame_offset,end-position);
    return true;
}
#include "lz4_pixels.h"
/* Validate the entire staged tile list before any visible write. Only a
 * matching acknowledged frame can be used as its base. No extra frame RAM. */
static uint32_t patch_frame(const qd_header *h,const uint8_t *payload,
                            uint32_t *decode,uint32_t *draw,uint32_t *detail)
{
    if(assembling || !power_state.frame_valid || !committed_valid ||
       h->offset!=committed_hash) return QD_BAD_STATE;
    if(h->flags!=1 || h->raw_length<1040u || h->raw_length>QD_BLOCK_BYTES)
        return QD_BAD_LENGTH;
    uint32_t started=micros();
    int n=LZ4_decompress_safe((const char*)payload,(char*)decode_pixels,h->length,h->raw_length);
    if(n!=(int)h->raw_length) return QD_DECODE_ERROR;
    uint32_t target=*(const uint32_t*)decode_pixels,count=*(const uint32_t*)(decode_pixels+4);
    if(!count || count>(QD_BLOCK_BYTES-8u)/1032u || h->raw_length!=8u+count*1032u)
        return QD_BAD_LENGTH;
    for(uint32_t i=0;i<count;i++) {
        const uint16_t *rect=(const uint16_t*)(decode_pixels+8u+i*1032u);
        if(rect[0]>=QD_WIDTH || rect[1]>=QD_HEIGHT || (rect[0]&31u) ||
           (rect[1]&15u) || rect[2]!=32u || rect[3]!=16u) return QD_BAD_LENGTH;
    }
    committed_valid=false;
    for(uint32_t i=0;i<count;i++) {
        const uint8_t *tile=decode_pixels+8u+i*1032u;
        const uint16_t *rect=(const uint16_t*)tile;
        for(uint32_t row=0;row<16u;row++) {
            frame_offset=((rect[1]+row)*QD_WIDTH+rect[0])*2u;
            if(!copy_pixels(tile+8u+row*64u,64u)) return QD_DISPLAY_ERROR;
        }
    }
    *decode=micros()-started;started=micros();
    if(submit_frame()) return QD_DISPLAY_ERROR;
    *draw=micros()-started;*detail=committed_hash=target;committed_valid=true;
    return QD_OK;
}
/* Read-only scan diagnostics for this exact R03 core. Each address is used
 * by its audited MIPI setup/status routines; callers cannot supply an address.
 * No panel commands, clock changes, IRQ clears, or new frame submissions. */
static const uintptr_t scan_pages[][4]={
    {0x8098e838,0x8098e83c,0x8098e850,0x8098e854},
    {0x8098e858,0x8098e85c,0x8098e860,0x8098e870},
    {0x8098e864,0x8098e868,0x8098e86c,0x8098e874},
    {0x0880702c,0x08807030,0x08807038,0x0880704c},
    {0x08807034,0x08807040,0x08807044,0x08807050},
    {0x08807404,0x08807414,0x08807408,0x08807410},
    {0x08807420,0x08807424,0x08807428,0x0880742c},
    {0x08807430,0x08807434,0x08807438,0x0880743c},
    {0x08807454,0x08807560,0x50109144,0x08807008},
};
static void controls_start(void)
{
    /* Public R03 pin table verified: 47 -> module pin 99, 46 -> 13,
     * 44 -> 14. R/query is unverified and must not use an invented GPIO. */
    static const Helios_GPIONum keys[]={47,46,44};
    r03_gpio_config input={HELIOS_GPIO_INPUT,HELIOS_PULL_UP,HELIOS_LVL_HIGH};
    if(!core_matches) return;
    for(unsigned i=0;i<3;i++) if(!r03_gpio_init(keys[i],&input)) keys_available|=1u<<i;
}
static void waiting_countdown(uint32_t now)
{
    static unsigned previous=~0u;
    if(power_state.host_seen || power_state.frame_valid || !power_state.awake || assembling || osd_drawn) {previous=~0u;return;}
    unsigned elapsed=(uint32_t)(now-power_state.last_host)/1000u;
    unsigned seconds=elapsed>=90u?0u:90u-elapsed;
    if(seconds==previous)return;
    previous=seconds;
    static const uint8_t segments[10]={0x3f,0x06,0x5b,0x4f,0x66,0x6d,0x7d,0x07,0x7f,0x6f};
    static const uint8_t rects[7][4]={{7,0,30,6},{37,6,6,28},{37,40,6,28},{7,68,30,6},{1,40,6,28},{1,6,6,28},{7,34,30,6}};
    uint16_t *pixels=(uint16_t*)frame;
    for(unsigned y=1050;y<1150;y++)for(unsigned x=330;x<470;x++)pixels[y*QD_WIDTH+x]=0x1084;
    for(unsigned digit=0;digit<2;digit++) {
        uint8_t mask=segments[digit?seconds%10:seconds/10];
        for(unsigned part=0;part<7;part++)if(mask&(1u<<part)) {
            const uint8_t *r=rects[part];unsigned left=347+digit*58+r[0],top=1062+r[1];
            for(unsigned y=top;y<top+r[3];y++)for(unsigned x=left;x<left+r[2];x++)pixels[y*QD_WIDTH+x]=0xffff;
        }
    }
    submit_frame();
}
static void controls_poll(void)
{
    static const Helios_GPIONum keys[]={47,46,44};
    uint8_t pressed=0;
    for(unsigned i=0;i<3;i++)
        if((keys_available&(1u<<i)) && Helios_GPIO_GetLevel(keys[i])==0) pressed|=1u<<i;
    uint32_t now=millis();
    bool was_osd=power_state.osd;
    unsigned events=qd_power_keys(&power_state,now,pressed);
    if(events&QD_KEY_BRIGHTNESS) osd_dirty=true;
    if(qd_power_expire(&power_state,now)) {
        osd_restore();assembling=false;frame_offset=0;
    }
    if(qd_power_idle(&power_state,now)) events|=QD_KEY_POWER;
    if(events && panel_ready) bl_apply(power_state.awake,power_state.brightness);
    if(!frame) return;
    if(!power_state.frame_valid && !assembling && !waiting_drawn) {
        int n=LZ4_decompress_safe((const char*)waiting_page_lz4,(char*)frame,
                                 sizeof(waiting_page_lz4),QD_FRAME_BYTES);
        if(n==(int)QD_FRAME_BYTES && !submit_frame()) waiting_drawn=true;
        osd_dirty=power_state.osd;
    }
    if(!assembling && power_state.awake) {
        if(power_state.osd && (osd_dirty || !osd_drawn)) {
            if(osd_paint()) submit_frame();
        } else if(was_osd && !power_state.osd && osd_drawn) {
            osd_restore();submit_frame();
        } else if((events&QD_KEY_POWER) && power_state.awake) submit_frame();
    }
    if(waiting_drawn)waiting_countdown(now);
}
static void render_task(void *arg)
{
    (void)arg;
    if(need_frame()) {controls_start();controls_poll();}
    for(;;) {
        controls_poll();
        audio_poll();
        unsigned index;
        if(Helios_MsgQ_Get(ready_slots,&index,sizeof(index),20)) continue;
        slot_t *s=&slots[index];qd_header *h=&s->h;
        uint32_t status=s->status, decode=0,draw=0,detail=0;
        uint32_t rx=s->received_us;
        if(!status && XXH32(s->data,h->length,0)!=h->payload_hash) status=QD_BAD_HASH;
        if(!status && !(h->type==QD_HELLO && (h->flags==7 || (h->flags==18 && h->offset==2u)))) {
            bool was_awake=power_state.awake;qd_power_touch(&power_state,millis());
            if(was_awake!=power_state.awake && panel_ready) bl_apply(power_state.awake,power_state.brightness);
        }
        if(!status) switch(h->type) {
        case QD_HELLO:
            detail=QD_BLOCK_BYTES;
            if(h->flags==18) {
                if(h->offset>2u || h->length || h->raw_length) {status=QD_BAD_LENGTH;break;}
                if(h->offset<2u) {
                    qd_power_set(&power_state,h->offset!=0);osd_restore();
                    if(panel_ready && !bl_apply(power_state.awake,power_state.brightness))status=QD_DISPLAY_ERROR;
                }
                rx=power_state.awake?1u:0u;detail=QD_UI_STATE_MAGIC;break;
            }
            if(h->flags==2) detail=QD_FEATURE_DEFER_ACK;
            if(h->flags==15) {
                /* Exact-core diagnostic: these status/W1C and mask registers
                 * are used by R03's audited MIPI command wait. Never clear a
                 * bit enabled in the driver's interrupt mask. No clocks or
                 * display enable registers are changed by this probe. */
                if(!core_matches || !panel_ready) {status=QD_BAD_STATE;break;}
                volatile uint32_t *events=(volatile uint32_t*)0x08807008;
                uint32_t mask=*(volatile uint32_t*)0x0880700c;
                if(!h->offset) {rx=*events;decode=mask;draw=0;detail=0;break;}
                uint32_t bit=h->offset;
                if((bit!=4u && bit!=8u) || !h->raw_length || h->raw_length>16u) {status=QD_BAD_LENGTH;break;}
                if(mask&bit) {status=QD_BAD_STATE;detail=mask;break;}
                rx=0;decode=0xffffffffu;draw=0;detail=0;
                for(uint32_t sample=0;sample<h->raw_length;sample++) {
                    *events=bit;__asm__ volatile("dsb sy" ::: "memory");
                    uint32_t start=micros();
                    while(!(*events&bit) && (uint32_t)(micros()-start)<40000u) {}
                    uint32_t elapsed=micros()-start;
                    if(!(*events&bit)) break;
                    rx+=elapsed;if(elapsed<decode)decode=elapsed;if(elapsed>draw)draw=elapsed;detail++;
                }
            }
            if(h->flags==1) {
                __asm__ volatile("mrc p15, 0, %0, c1, c0, 0" : "=r"(rx));
                decode=(uint32_t)usb_read;
            }
            if(h->flags==3) {
                rx=panel_stage;
                decode=Helios_GPIO_GetLevel(HELIOS_GPIO8);
                draw=Helios_GPIO_GetDirection(HELIOS_GPIO8);
                detail=(uint32_t)frame;
            }
            if(h->flags==4 || h->flags==5) {
                if(!core_matches || !panel_ready) {status=QD_BAD_STATE;break;}
                if(h->flags==4) {
                    if(h->offset>=sizeof(scan_pages)/sizeof(scan_pages[0])) {
                        status=QD_BAD_LENGTH;break;
                    }
                    const uintptr_t *page=scan_pages[h->offset];
                    rx=*(volatile uint32_t*)page[0];
                    decode=*(volatile uint32_t*)page[1];
                    draw=*(volatile uint32_t*)page[2];
                    detail=*(volatile uint32_t*)page[3];
                } else {
                    /* Discover which status bits actually change. Neither
                     * register is read-to-clear in the audited core. This
                     * is NOT a vblank counter or an optical FPS measurement. */
                    if(!h->raw_length || h->raw_length>200000u) {
                        status=QD_BAD_LENGTH;break;
                    }
                    uint32_t lcd0=*(volatile uint32_t*)0x08807008;
                    uint32_t dsi0=*(volatile uint32_t*)0x08807454;
                    uint32_t started=micros(), count=0, lcd_changes=0,dsi_changes=0;
                    do {
                        lcd_changes|=*(volatile uint32_t*)0x08807008^lcd0;
                        dsi_changes|=*(volatile uint32_t*)0x08807454^dsi0;
                        ++count;
                    } while((uint32_t)(micros()-started)<h->raw_length);
                    rx=micros()-started;decode=lcd_changes;draw=dsi_changes;detail=count;
                }
            }
            if(h->flags==7) {
                rx=(power_state.awake?QD_UI_AWAKE:0u) |
                   (power_state.frame_valid?QD_UI_FRAME_VALID:0u) |
                   (power_state.host_seen?QD_UI_HOST_RECENT:0u);
                decode=power_state.raw|((uint32_t)keys_available<<16);
                draw=millis()-power_state.last_host;detail=QD_UI_STATE_MAGIC;
            }
            if(h->flags==8) detail=QD_WAITING_HASH;
            if(h->flags==9) detail=qd_power_self_test();
            if(h->flags==10) {
                rx=power_state.brightness;decode=bl_running?1u:0u;draw=bl_edges;
                detail=(power_state.awake?1u:0u)|(osd_drawn?2u:0u)|(power_state.osd?4u:0u);
            }
            if(h->flags==11) {
                // Explicit bounded diagnostic: drive the same dimmer as +/-.
                if(h->offset<5 || h->offset>100 || h->offset%5) {status=QD_BAD_LENGTH;break;}
                power_state.brightness=h->offset;power_state.osd=true;power_state.osd_since=millis();
                osd_dirty=true;
                if(!bl_apply(power_state.awake,power_state.brightness)) status=QD_DISPLAY_ERROR;
                detail=power_state.brightness;
            }
            if(h->flags==12) {
                if(!h->raw_length || h->raw_length>100000u) {status=QD_BAD_LENGTH;break;}
                uint32_t start=micros(),high=0,samples=0,edges=bl_edges;
                do {high+=Helios_GPIO_GetLevel(HELIOS_GPIO8)==1;++samples;}
                while((uint32_t)(micros()-start)<h->raw_length);
                rx=micros()-start;decode=high;draw=samples;detail=bl_edges-edges;
            }
            if(h->flags==14) {
                rx=osd_backup?XXH32(osd_backup,QD_OSD_BYTES,0):0;
                decode=frame?visible_osd_hash():0;draw=osd_drawn?1u:0u;detail=osd_level;
            }
            break;
        case QD_AUDIO:
            status=audio_control(h,&rx,&decode,&draw,&detail);break;
        case QD_AUDIO_DATA:
            status=audio_data(h,s->data,&detail);break;
        case QD_AUDIO_PCM:
            status=audio_pcm(h,s->data,&detail);break;
        case QD_BEGIN:
            osd_dirty=power_state.osd;
            assembling=false;committed_valid=false;frame_offset=0;
            frame_rx_us=frame_decode_us=0;
            if(h->raw_length!=QD_FRAME_BYTES) status=QD_BAD_LENGTH;
            else if(!need_frame()) status=QD_NO_MEMORY;
            else {assembling=true;detail=osd_drawn?1u:0u;}
            break;
        case QD_DATA:
            if(!assembling || h->offset!=frame_offset) {status=QD_BAD_STATE;break;}
            bool whole=h->offset==0 && h->raw_length==QD_FRAME_BYTES && (h->flags&~QD_DATA_DEFER_ACK)==1;
            if(!h->raw_length || (h->raw_length>QD_BLOCK_BYTES && !whole) ||
               h->raw_length>QD_FRAME_BYTES-frame_offset) {status=QD_BAD_LENGTH;break;}
            if(whole && osd_drawn) {status=QD_BAD_STATE;break;}
            {
                uint32_t start=micros();
                uint16_t codec=h->flags & ~QD_DATA_DEFER_ACK;
                if(codec==0 && h->length==h->raw_length) {
                    if(!copy_pixels(s->data,h->length)) status=QD_DISPLAY_ERROR;
                }
                else if(codec==1) {
                    int n=osd_drawn?LZ4_decompress_safe((const char*)s->data,(char*)decode_pixels,h->length,h->raw_length):
                        qd_lz4_pixels(s->data,h->length,frame+frame_offset,h->raw_length);
                    if(n!=(int)h->raw_length) status=QD_DECODE_ERROR;
                    else if(osd_drawn && !copy_pixels(decode_pixels,h->raw_length)) status=QD_DISPLAY_ERROR;
                } else status=QD_BAD_LENGTH;
                decode=micros()-start;
            }
            if(!status) frame_offset+=h->raw_length;
            frame_rx_us+=rx;frame_decode_us+=decode;
            detail=frame_offset;
            break;
        case QD_COMMIT:
            if(!assembling || frame_offset!=QD_FRAME_BYTES) {status=QD_BAD_STATE;break;}
            {
                uint32_t start=micros();
                if(power_state.osd && power_state.awake) osd_paint();
                else osd_restore();
                if(submit_frame()) status=QD_DISPLAY_ERROR;
                draw=micros()-start;
            }
            if(!status) {power_state.frame_valid=true;waiting_drawn=false;committed_hash=h->offset;committed_valid=h->flags==1;}
            assembling=false;rx=frame_rx_us;decode=frame_decode_us;
            detail=QD_FRAME_BYTES;
            break;
        case QD_PATCH:
            status=patch_frame(h,s->data,&decode,&draw,&detail);
            break;
        case QD_BENCH:
            /* Local full-frame benchmark; no host input or unchanged-region shortcut. */
            assembling=false;committed_valid=false;
            if(h->raw_length<1 || h->raw_length>120) {status=QD_BAD_LENGTH;break;}
            if(panel_start()) {status=QD_DISPLAY_ERROR;detail=panel_stage;break;}
            if(!need_frame()) {status=QD_NO_MEMORY;break;}
            {
                uint32_t start=micros();
                for(unsigned k=0;k<h->raw_length;k++) {
                    memset(frame,k&1?0xff:0,QD_FRAME_BYTES);
                    if(submit_frame()) {status=QD_DISPLAY_ERROR;break;}
                }
                draw=micros()-start;detail=h->raw_length;
            }
            break;
        case QD_VERIFY:
            if(!frame || (assembling && h->flags!=1)) status=QD_BAD_STATE;
            else if(h->flags==1) {
                if(h->offset>QD_FRAME_BYTES || h->raw_length>QD_FRAME_BYTES-h->offset)
                    status=QD_BAD_LENGTH;
                else detail=clean_frame_hash(h->offset,h->raw_length);
            }
            else detail=clean_frame_hash(0,QD_FRAME_BYTES);
            break;
        default:status=QD_BAD_HEADER;break;
        }
        if(status) assembling=false;
        /* Like the ESP upstream's stream, successful data blocks need no
         * application round-trip. The host bounds groups to the slot count, asking
         * for an ACK on each group end; this core's RX can drop on overflow.
         * COMMIT confirms the frame; errors still get a reply. */
        if(status || h->type!=QD_DATA || !(h->flags&QD_DATA_DEFER_ACK))
            reply(h->seq,status,rx,decode,draw,detail);
        Helios_MsgQ_Put(free_slots,&index,sizeof(index),HELIOS_WAIT_FOREVER);
    }
}
static bool valid_header(const qd_header *h)
{
    if(h->magic!=QD_MAGIC || h->version!=QD_VERSION || h->type<QD_HELLO || h->type>QD_PATCH ||
       h->length>QD_BLOCK_BYTES || h->header_hash!=XXH32(h,28,0)) return false;
    return h->type==QD_DATA || h->type==QD_PATCH || ((h->type==QD_AUDIO_DATA || h->type==QD_AUDIO_PCM) && h->length<=16384u) || h->length==0;
}
static void receiver_task(void *arg)
{
    (void)arg;
    Helios_msleep(1500);
    free_slots=Helios_MsgQ_Create(QD_SLOTS,sizeof(unsigned));
    ready_slots=Helios_MsgQ_Create(QD_SLOTS,sizeof(unsigned));
    receive_event=Helios_Semaphore_Create(32,0);
    if(!free_slots || !ready_slots || !receive_event) {Helios_Thread_Exit();return;}
    for(unsigned i=0;i<QD_SLOTS;i++) Helios_MsgQ_Put(free_slots,&i,sizeof(i),0);
    Helios_UARTConfig cfg={HELIOS_UART_BAUD_115200,HELIOS_UART_DATABIT_8,
                          HELIOS_UART_STOP_1,HELIOS_UART_PARITY_NONE,HELIOS_UART_FC_NONE};
    Helios_UARTInitStruct uart={&cfg,uart_event};
    if(Helios_UART_Init(data_port,&uart)) {Helios_Thread_Exit();return;}
    core_matches=XXH32((const void*)0x60010000,R03_CORE_SIZE,0)==R03_CORE_XXH32;
    core_checked=true;
    if(core_matches) {
        /* The R03 ql_uart_read wrapper clears the entire requested buffer,
         * even when no bytes are pending. Its stream's read operation already
         * supplies the received length. Keep the channel's TX/RX lock. This app
         * is the sole reader and never closes the channel while tasks run. */
        void *channel=((void *(*)(int))0x6020bca1)(5);
        uintptr_t address=(uintptr_t)channel;
        if(address>=0x80980000 && address<0x81000000-64) {
            uintptr_t reader=((uint32_t*)channel)[4];
            if((reader&1) && reader>=0x60010000 && reader<0x60260000) {
                usb_channel=channel;
                usb_read=(int (*)(void*,void*,unsigned))reader;
            }
        }
    }
    Helios_ThreadAttr render={"qd-render",8192,100,render_task,NULL};
    if(!Helios_Thread_Create(&render)) {Helios_Thread_Exit();return;}
    for(;;) {
        unsigned index;
        if(Helios_MsgQ_Get(free_slots,&index,sizeof(index),HELIOS_WAIT_FOREVER)) continue;
        slot_t *s=&slots[index];uint8_t *hdr=(uint8_t*)&s->h;
        /* Byte-sliding header resynchronization also recovers a truncated body. */
        size_t have=0;
        while(have<sizeof(qd_header)) {
            if(!read_exact(hdr+have,sizeof(qd_header)-have,3000)) {have=0;continue;}
            if(valid_header(&s->h)) break;
            memmove(hdr,hdr+1,sizeof(qd_header)-1);have=sizeof(qd_header)-1;
        }
        uint32_t start=micros();
        s->status=read_exact(s->data,s->h.length,3000)?QD_OK:QD_TIMEOUT;
        s->received_us=micros()-start;
        Helios_MsgQ_Put(ready_slots,&index,sizeof(index),HELIOS_WAIT_FOREVER);
    }
}
int appimg_enter(void *arg)
{
    (void)arg;
    Helios_ThreadAttr receiver={"qd-usb",8192,105,receiver_task,NULL};
    return Helios_Thread_Create(&receiver)?0:-1;
}
void appimg_exit(void) {}
