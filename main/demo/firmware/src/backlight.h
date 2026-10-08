/* GPIO8 = module pin118 = hardware GPIO7, verified backlight enable.
 * EC600U hardware PWM0 is pin70, not wired to this backlight. A 1 kHz
 * OSI ISR timer switches ONLY the verified enable pin. No pixel darkening,
 * busy loop, frame work, allocation or GPIO driver locks in the callback.
 * Internal timer addresses and atomic GPIO registers require exact R03.
 */
static osiTimer_t *bl_timer;
static volatile unsigned bl_duty=100, bl_edges;
static volatile bool bl_awake=true, bl_high=true, bl_running;
static bool bl_applied;
static inline void bl_pin(bool high)
{
    *(volatile uint32_t*)(high?0x50107010:0x50107014)=1u<<7;
    __asm__ volatile("dsb sy" ::: "memory");
}
static bool bl_arm(unsigned us)
{ return ((bool (*)(osiTimer_t*,uint32_t))0x601c621f)(bl_timer,us); }
static void bl_callback(void *unused)
{
    (void)unused;
    if(!bl_running) return;
    bl_high=!bl_high;bl_pin(bl_high);++bl_edges;
    unsigned delay=bl_high?bl_duty*10u:(100u-bl_duty)*10u;
    if(!bl_arm(delay)) {bl_running=false;bl_pin(bl_awake);}
}
static bool bl_apply(bool awake,unsigned duty)
{
    if(bl_applied && awake==bl_awake && duty==bl_duty && (bl_running || !awake || duty==100)) return true;
    uint32_t critical=Helios_Critical_Enter();
    bl_running=false;
    if(bl_timer) ((bool (*)(osiTimer_t*))0x601c62e5)(bl_timer);
    bl_awake=awake;bl_duty=duty;bl_high=awake;
    bl_applied=true;
    bl_pin(awake);
    bool ok=true;
    if(awake && duty<100) {
        if(!bl_timer) bl_timer=osiTimerCreate(OSI_TIMER_IN_ISR,bl_callback,NULL);
        bl_running=bl_timer!=NULL;
        ok=bl_running && bl_arm(duty*10u);
        if(!ok) {bl_running=false;bl_pin(awake);}
    }
    Helios_Critical_Exit(critical);
    return ok;
}
