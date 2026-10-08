/* Called only by the render owner. Keep the overlay in scanout during DATA;
 * route incoming covered pixels into its backup. Never erase/repaint per frame.
 */
static uint8_t *osd_backup,*osd_tile;
static bool osd_drawn,osd_dirty;
static unsigned osd_level;
/* Old GCC's constant propagation warns on XXH32's unreachable unsigned
 * overflow branch for a 960-byte row. Keep the checked streaming update
 * generic; its internal 16-byte staging buffer is never used for a full row. */
static __attribute__((noinline,noclone)) void osd_hash_update(XXH32_state_t *state,const void *pixels,size_t length)
{ XXH32_update(state,pixels,length); }
static void osd_restore(void)
{
    if(!osd_drawn) return;
    for(unsigned y=0;y<QD_OSD_HEIGHT;y++)
        memcpy(frame+((QD_OSD_Y+y)*QD_WIDTH+QD_OSD_X)*2u,
               osd_backup+y*QD_OSD_WIDTH*2u,QD_OSD_WIDTH*2u);
    osd_drawn=false;
}
static bool osd_paint(void)
{
    if(!osd_backup) osd_backup=malloc(QD_OSD_BYTES);
    if(!osd_tile) osd_tile=malloc(QD_OSD_BYTES);
    if(!osd_backup || !osd_tile) return false;
    if(osd_drawn && osd_level==power_state.brightness) {
        osd_dirty=false;return false;
    }
    unsigned index=power_state.brightness/5u-1u;
    if(osd_level!=power_state.brightness) {
        int n=LZ4_decompress_safe((const char*)brightness_osds[index],(char*)osd_tile,
                                brightness_osd_sizes[index],QD_OSD_BYTES);
        if(n!=(int)QD_OSD_BYTES) return false;
        osd_level=power_state.brightness;
    }
    for(unsigned y=0;y<QD_OSD_HEIGHT;y++) {
        uint8_t *row=frame+((QD_OSD_Y+y)*QD_WIDTH+QD_OSD_X)*2u;
        if(!osd_drawn) memcpy(osd_backup+y*QD_OSD_WIDTH*2u,row,QD_OSD_WIDTH*2u);
        memcpy(row,osd_tile+y*QD_OSD_WIDTH*2u,QD_OSD_WIDTH*2u);
    }
    osd_drawn=true;osd_dirty=false;return true;
}
static uint32_t clean_frame_hash(uint32_t offset,uint32_t length)
{
    if(!osd_drawn) return XXH32(frame+offset,length,0);
    XXH32_state_t state;XXH32_reset(&state,0);
    uint32_t end=offset+length,position=offset;
    for(unsigned y=0;y<QD_OSD_HEIGHT && position<end;y++) {
        uint32_t first=((QD_OSD_Y+y)*QD_WIDTH+QD_OSD_X)*2u;
        uint32_t last=first+QD_OSD_WIDTH*2u;
        if(last<=position || first>=end) continue;
        if(position<first) {
            XXH32_update(&state,frame+position,first-position);position=first;
        }
        uint32_t stop=end<last?end:last;
        XXH32_update(&state,osd_backup+y*QD_OSD_WIDTH*2u+position-first,stop-position);
        position=stop;
    }
    if(position<end) XXH32_update(&state,frame+position,end-position);
    return XXH32_digest(&state);
}
static uint32_t visible_osd_hash(void)
{
    XXH32_state_t state;XXH32_reset(&state,0);
    for(unsigned y=0;y<QD_OSD_HEIGHT;y++)
        osd_hash_update(&state,frame+((QD_OSD_Y+y)*QD_WIDTH+QD_OSD_X)*2u,QD_OSD_WIDTH*2u);
    return XXH32_digest(&state);
}
