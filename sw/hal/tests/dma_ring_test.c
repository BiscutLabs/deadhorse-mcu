#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t registers[64];
static void write_reg(unsigned off,uint32_t v) {
    if(off==12) registers[3]&=~v;
    else if(off==0) {
        for(unsigned c=0;c<4;c++) if(v&(1u<<c)) {
            registers[2]|=1u<<c;registers[0x60/4+c]=registers[0x20/4+c];
        }
    } else if(off==4) registers[2]&=~v;
    else registers[off/4]=v;
}
#define DH_RING_READ(offset) registers[(offset)/4]
#define DH_RING_WRITE(offset,value) write_reg(offset,value)
#include "dma_ring.h"
int main(void) {
    dh_dma_ring r;uint32_t n;
    assert(!dh_dma_ring_start(&r,4,0,0x20000000,8));
    assert(!dh_dma_ring_start(&r,0,3,0x20000000,8));
    assert(!dh_dma_ring_start(&r,0,0,0x20000000,1));
    assert(!dh_dma_ring_start(&r,0,0,0x20003fff,2));
    for(unsigned c=0;c<4;c++) for(unsigned uart=0;uart<3;uart++) {
        memset(registers,0,sizeof registers);
        assert(dh_dma_ring_start(&r,c,uart,0x20000103,5));
        assert(registers[0x40/4+c]==(33+2*uart));
        assert(!dh_dma_ring_start(&r,c,uart,r.base,r.length));
        assert(dh_dma_ring_available(&r,&n) && n==0);
        unsigned produced=0,consumed=0;
        for(unsigned step=0;step<30;step++) {
            produced++;registers[0x60/4+c]=r.base+(produced%5);
            assert(dh_dma_ring_available(&r,&n) && n==produced-consumed);
            assert(!dh_dma_ring_advance(&r,n+1));
            if(step%3==2) {assert(dh_dma_ring_advance(&r,n));consumed+=n;}
        }
        registers[3]=1u<<(4+c);assert(!dh_dma_ring_available(&r,&n));registers[3]=0;
        dh_dma_ring_abort(&r);assert(!dh_dma_ring_available(&r,&n));
        assert(dh_dma_ring_start(&r,c,uart,0x20000200,8));
    }
    return 0;
}
