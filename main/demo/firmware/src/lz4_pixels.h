/* Bounded LZ4 block decode into RGB565 scanout. Unlike LZ4's wild-copy fast
 * loop, every store stays inside final decoded output. Never publish a lone
 * byte of a pixel: retain it until the next token supplies its second byte.
 * This avoids both transient match-expansion pixels and a second full-frame
 * RAM copy. The existing staged decoder handles an active brightness OSD.
 */
static uint8_t qd_history(const uint8_t *out,uint32_t index,uint32_t position,uint8_t carry)
{ return (position&1u) && index==position-1u?carry:out[index]; }
static inline uint32_t qd_pixel_word(const void *source)
{
    /* need_frame verifies SCTLR.A=0. These are bounded normal-RAM loads,
     * never MMIO; LDR supports byte-aligned addresses on this Cortex-A5. */
    uint32_t word;
    __asm__ volatile("ldr %0, [%1]" : "=r"(word) : "r"(source) : "memory");
    return word;
}
static inline void qd_pixel_copy16(uint8_t *out,const uint8_t *in)
{
    /* Source may be unaligned; destination is aligned and receives complete
     * RGB565 pairs. Exactly 16 bytes are read and stored, no wild-copy tail.
     * Four scratch registers leave the token parser's live values in GPRs. */
    __asm__ volatile(
        "ldr r3, [%1, #0]\n" "ldr r4, [%1, #4]\n"
        "ldr r5, [%1, #8]\n" "ldr r6, [%1, #12]\n"
        "stmia %0, {r3-r6}\n"
        : : "r"(out),"r"(in) : "r3","r4","r5","r6","memory");
}
static __attribute__((noinline)) int qd_lz4_pixels(const uint8_t *in,uint32_t size,uint8_t *out,uint32_t capacity)
{
    uint32_t at=0,position=0;uint8_t carry=0;
    if(capacity&1u) return -1;
    while(at<size) {
        uint32_t token=in[at++],literal=token>>4;
        if(literal==15u) {uint32_t add;do {
            if(at>=size) return -1;
            add=in[at++];
            if(literal>capacity || add>capacity-literal) return -1;
            literal+=add;
        } while(add==255u);}
        if(literal>size-at || literal>capacity-position) return -1;
        if((position&1u) && literal) {
            *(volatile uint16_t*)(out+position-1u)=(uint16_t)(carry|((uint16_t)in[at++]<<8));++position;--literal;
        }
        if((position&2u) && literal>=2u) {
            *(volatile uint16_t*)(out+position)=(uint16_t)(in[at]|((uint16_t)in[at+1u]<<8));at+=2u;position+=2u;literal-=2u;
        }
        while(literal>=16u) {
            qd_pixel_copy16(out+position,in+at);at+=16u;position+=16u;literal-=16u;
        }
        while(literal>=4u){*(volatile uint32_t*)(out+position)=qd_pixel_word(in+at);at+=4u;position+=4u;literal-=4u;}
        while(literal>=2u) {
            *(volatile uint16_t*)(out+position)=(uint16_t)(in[at]|((uint16_t)in[at+1u]<<8));at+=2u;position+=2u;literal-=2u;
        }
        if(literal) {carry=in[at++];++position;}
        if(at==size) return position==capacity?(int)position:-1;
        if(size-at<2u) return -1;
        uint32_t offset=in[at]|((uint32_t)in[at+1u]<<8);at+=2u;
        if(!offset || offset>position) return -1;
        uint32_t match=(token&15u)+4u;
        if((token&15u)==15u) {uint32_t add;do {
            if(at>=size) return -1;
            add=in[at++];
            if(match>capacity || add>capacity-match) return -1;
            match+=add;
        } while(add==255u);}
        if(match>capacity-position) return -1;
        if(position&1u) {
            uint8_t high=qd_history(out,position-offset,position,carry);
            *(volatile uint16_t*)(out+position-1u)=(uint16_t)(carry|((uint16_t)high<<8));++position;--match;
        }
        if(offset<=2u && match>=2u) {
            uint16_t word=offset==1u?(uint16_t)(out[position-1u]*0x0101u):
                (uint16_t)(out[position-2u]|((uint16_t)out[position-1u]<<8));
            if((position&2u)&&match>=2u){*(volatile uint16_t*)(out+position)=word;position+=2u;match-=2u;}
            uint32_t pair=(uint32_t)word|((uint32_t)word<<16);
            while(match>=16u){volatile uint32_t *dest=(volatile uint32_t*)(out+position);dest[0]=pair;dest[1]=pair;dest[2]=pair;dest[3]=pair;position+=16u;match-=16u;}
            while(match>=2u){*(volatile uint16_t*)(out+position)=word;position+=2u;match-=2u;}
        }
        if((position&2u)&&match>=2u){uint8_t low=out[position-offset],high=offset==1u?low:out[position+1u-offset];
            *(volatile uint16_t*)(out+position)=(uint16_t)(low|((uint16_t)high<<8));position+=2u;match-=2u;}
        while(offset>=16u && match>=16u) {
            qd_pixel_copy16(out+position,out+position-offset);position+=16u;match-=16u;
        }
        while(offset>=4u&&match>=4u){const uint8_t *source=out+position-offset;
            uint32_t word=qd_pixel_word(source);
            *(volatile uint32_t*)(out+position)=word;position+=4u;match-=4u;}
        while(match>=2u) {
            uint8_t low=out[position-offset];
            uint8_t high=offset==1u?low:out[position+1u-offset];
            *(volatile uint16_t*)(out+position)=(uint16_t)(low|((uint16_t)high<<8));position+=2u;match-=2u;
        }
        if(match){carry=out[position-offset];++position;}
    }
    return -1;
}
