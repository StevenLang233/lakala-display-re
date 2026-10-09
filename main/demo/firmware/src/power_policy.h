#ifndef QDISPLAY_POWER_POLICY_H
#define QDISPLAY_POWER_POLICY_H
#include <stdint.h>
#include <stdbool.h>
#define QD_HOST_TIMEOUT_MS 5000u
#define QD_DISCONNECT_SLEEP_MS 90000u
#define QD_KEY_HOLD_MS 2000u
#define QD_KEY_DEBOUNCE_MS 40u
#define QD_UI_AWAKE 1u
#define QD_UI_FRAME_VALID 2u
#define QD_UI_HOST_RECENT 4u
#define QD_UI_STATE_MAGIC 0x31534451u
#define QD_KEY_BRIGHTNESS 1u
#define QD_KEY_POWER 2u
typedef struct {
    bool awake, frame_valid, host_seen, latched, disconnect_sleep;
    uint8_t raw, stable, brightness;
    uint32_t last_host, edges[3], held_since[3], repeated[2], osd_since;
    bool osd;
} qd_power_state;
static inline void qd_power_touch(qd_power_state *p,uint32_t now)
{ p->host_seen=true;p->last_host=now;
  if(p->disconnect_sleep) {p->disconnect_sleep=false;p->awake=true;} }
static inline bool qd_power_idle(qd_power_state *p,uint32_t now)
{
    if(p->host_seen || p->disconnect_sleep || !p->awake ||
       (uint32_t)(now-p->last_host)<QD_DISCONNECT_SLEEP_MS) return false;
    p->awake=false;p->disconnect_sleep=true;p->osd=false;return true;
}
static inline void qd_power_set(qd_power_state *p,bool awake)
{ p->awake=awake;p->disconnect_sleep=false;p->osd=false; }
static inline bool qd_power_expire(qd_power_state *p,uint32_t now)
{
    if(!p->host_seen || (uint32_t)(now-p->last_host)<QD_HOST_TIMEOUT_MS) return false;
    p->host_seen=false;p->frame_valid=false;return true;
}
static inline unsigned qd_power_keys(qd_power_state *p,uint32_t now,uint8_t raw)
{
    unsigned events=0;raw&=7u;
    for(unsigned i=0;i<3;i++) {
        uint8_t bit=1u<<i;
        bool adjustment=false;
        if((p->raw^raw)&bit) p->edges[i]=now;
        if((p->stable^raw)&bit && (uint32_t)(now-p->edges[i])>=QD_KEY_DEBOUNCE_MS) {
            p->stable^=bit;
            if(raw&bit) {
                p->held_since[i]=now;
                if(i<2) {adjustment=true;p->repeated[i]=now;}
            }
        } else if(i<2 && (raw&p->stable&bit) &&
            (uint32_t)(now-p->held_since[i])>=400u && (uint32_t)(now-p->repeated[i])>=120u) {
            adjustment=true;p->repeated[i]=now;
        }
        if(adjustment) {
            events|=QD_KEY_BRIGHTNESS;
            if(i==0) p->brightness=p->brightness>=95?100:p->brightness+5;
            else p->brightness=p->brightness<=10?5:p->brightness-5;
        }
    }
    p->raw=raw;
    if(!(raw&4u) && !(p->stable&4u)) p->latched=false;
    if(!p->latched && (raw&p->stable&4u) &&
        (uint32_t)(now-p->held_since[2])>=QD_KEY_HOLD_MS) {
        p->latched=true;p->awake=!p->awake;events|=QD_KEY_POWER;
    }
    if(events&QD_KEY_BRIGHTNESS) {
        p->osd=true;p->osd_since=now;
        if(!p->awake) {p->awake=true;events|=QD_KEY_POWER;}
    }
    if(raw&3u) p->osd_since=now;
    else if(p->osd && (uint32_t)(now-p->osd_since)>=1800u) p->osd=false;
    return events;
}
static inline uint32_t qd_power_self_test(void)
{
    uint32_t passed=0;
    qd_power_state p={.awake=true,.brightness=100};
    qd_power_keys(&p,100,4);qd_power_keys(&p,140,4);
    if(!qd_power_keys(&p,2139,4) && (qd_power_keys(&p,2140,4)&QD_KEY_POWER) && !p.awake) passed|=1;
    if(!qd_power_keys(&p,8000,4) && !qd_power_keys(&p,15000,4)) passed|=2;
    qd_power_keys(&p,15001,0);qd_power_keys(&p,15041,0);
    qd_power_keys(&p,16000,1);
    if((qd_power_keys(&p,16040,1)&QD_KEY_BRIGHTNESS) && p.awake && p.brightness==100 && p.osd) passed|=4;
    p=(qd_power_state){.awake=true,.brightness=100};
    qd_power_keys(&p,0,2);qd_power_keys(&p,10,0);qd_power_keys(&p,20,2);qd_power_keys(&p,30,0);
    if(!qd_power_keys(&p,5000,0) && p.awake && p.brightness==100) passed|=8;
    p=(qd_power_state){.awake=true,.frame_valid=true};qd_power_touch(&p,0xfffffff0u);
    if(!qd_power_expire(&p,0xfffffff0u+4999u) && qd_power_expire(&p,0xfffffff0u+5000u) &&
       !p.frame_valid && p.awake) passed|=16;
    p=(qd_power_state){.awake=true,.brightness=100};
    qd_power_keys(&p,0xfffffff0u,2);qd_power_keys(&p,0xfffffff0u+40u,2);
    qd_power_keys(&p,0xfffffff0u+440u,2);
    if(p.awake && p.brightness==90 && p.osd) passed|=32;
    p=(qd_power_state){.awake=true,.brightness=5};
    qd_power_keys(&p,10,2);qd_power_keys(&p,50,2);qd_power_keys(&p,100,0);qd_power_keys(&p,140,0);
    qd_power_keys(&p,1849,0);bool before=p.osd;qd_power_keys(&p,1850,0);
    if(before && !p.osd && p.brightness==5) passed|=64;
    p=(qd_power_state){.awake=true};qd_power_touch(&p,0xfffffff0u);
    qd_power_expire(&p,0xfffffff0u+5000u);
    if(!qd_power_idle(&p,0xfffffff0u+89999u) && qd_power_idle(&p,0xfffffff0u+90000u) && !p.awake) {
        qd_power_touch(&p,123u);if(p.awake && !p.disconnect_sleep)passed|=128;
    }
    qd_power_set(&p,false);qd_power_touch(&p,124u);if(!p.awake)passed|=256;
    return passed;
}
#endif
