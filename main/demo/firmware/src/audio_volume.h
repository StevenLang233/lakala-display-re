/* Application volume relative to the verified factory maximum:
 * factory 6027be58 clamps to level 9; 602a4380 sets DAC 75 / algorithm 7.
 * Table is ceil(-80*log10(percent/100)) in half-dB units, amplitude p^2.
 * No floating-point work or per-sample multiplication on the board. */
static const unsigned char audio_attenuation[101]={
    255,160,136,122,112,105,98,93,88,84,80,77,74,71,69,66,64,62,60,58,
    56,55,53,52,50,49,47,46,45,44,42,41,40,39,38,37,36,35,34,33,
    32,31,31,30,29,28,27,27,26,25,25,24,23,23,22,21,21,20,19,19,
    18,18,17,17,16,15,15,14,14,13,13,12,12,11,11,10,10,10,9,9,
    8,8,7,7,7,6,6,5,5,5,4,4,3,3,3,2,2,2,1,1,0
};
/* Prepare nine bounded profiles while the decoder is stopped. Playback
 * changes only the existing hardware level, as the original product does.
 * Floor to the next quieter anchor; never turn a requested small percentage
 * into a louder step. Level 9 retains the original product's maximum gain. */
static const unsigned char audio_level_percent[10]={0,1,3,6,10,20,35,50,75,100};
static unsigned int audio_volume_level(unsigned int percent)
{
    if(!percent) return 0;
    unsigned int level=1;
    while(level<9 && percent>=audio_level_percent[level+1]) ++level;
    return level;
}
static void audio_volume_gain(unsigned int percent,unsigned short *dac,
                              unsigned short *algorithm)
{
    unsigned int atten=audio_attenuation[percent>100?100:percent];
    unsigned int steps=atten/6;
    if(steps>6) steps=6;
    unsigned int remaining=atten>steps*6?atten-steps*6:0;
    *algorithm=(unsigned short)(7-steps);
    *dac=(unsigned short)(remaining<75?75-remaining:0);
}
