/* Independent binary32 oracle using pinned Berkeley SoftFloat RISCV. */
#include <stdint.h>
#include <stdio.h>
#include <inttypes.h>
#include "softfloat.h"

static int nan(uint32_t x) { return (x & 0x7fffffff) > 0x7f800000; }
static int snan(uint32_t x) { return nan(x) && !(x & 0x400000); }
static uint32_t classify(uint32_t x) {
    unsigned e=(x>>23)&255, f=x&0x7fffff, s=x>>31;
    unsigned bit=e==255 ? (f ? (snan(x)?8:9) : (s?0:7)) :
                 e==0 ? (f ? (s?2:5) : (s?3:4)) : (s?1:6);
    return 1u<<bit;
}
int main(void) {
    unsigned op,rm; uint32_t a,b,c;
    while (scanf("%u %u %"SCNx32" %"SCNx32" %"SCNx32, &op,&rm,&a,&b,&c)==5) {
        float32_t x={a},y={b},z={c}; uint32_t r=0;
        softfloat_roundingMode=rm;
        softfloat_detectTininess=softfloat_tininess_afterRounding;
        softfloat_exceptionFlags=0;
        switch(op) {
        case 0: r=f32_add(x,y).v; break;
        case 1: r=f32_sub(x,y).v; break;
        case 2: r=f32_mul(x,y).v; break;
        case 3: r=f32_mulAdd(x,y,z).v; break;
        case 4: z.v^=0x80000000; r=f32_mulAdd(x,y,z).v; break;
        case 5: x.v^=0x80000000; r=f32_mulAdd(x,y,z).v; break;
        case 6: x.v^=0x80000000; z.v^=0x80000000; r=f32_mulAdd(x,y,z).v; break;
        case 7: r=f32_div(x,y).v; break;
        case 8: r=f32_sqrt(x).v; break;
        case 9: case 10:
            if (nan(a)&&nan(b)) r=0x7fc00000;
            else if(nan(a)) r=b;
            else if(nan(b)) r=a;
            else if((a&0x7fffffff)==0 && (b&0x7fffffff)==0) r=op==9?(a|b):(a&b);
            else r=(f32_lt_quiet(x,y) == (op==9)) ? a:b;
            softfloat_exceptionFlags=(snan(a)||snan(b))?16:0;
            break;
        case 11: r=f32_eq(x,y); break;
        case 12: r=f32_lt(x,y); break;
        case 13: r=f32_le(x,y); break;
        case 14: r=(a&0x7fffffff)|(b&0x80000000); break;
        case 15: r=(a&0x7fffffff)|((~b)&0x80000000); break;
        case 16: r=a^(b&0x80000000); break;
        case 17: r=classify(a); break;
        case 18: case 19: r=a; break;
        case 20: r=(uint32_t)f32_to_i32(x,rm,true); break;
        case 21: r=(uint32_t)f32_to_ui32(x,rm,true); break;
        case 22: r=i32_to_f32((int32_t)a).v; break;
        case 23: r=ui32_to_f32(a).v; break;
        default: return 2;
        }
        printf("%08"PRIx32" %02x\n",r,(unsigned)softfloat_exceptionFlags);
    }
    return ferror(stdin)?3:0;
}
