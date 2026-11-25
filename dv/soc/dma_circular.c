#include "dma_ring.h"
static volatile uint32_t *const gpio=(volatile uint32_t *)DH_SOC_GPIO_PINMUX_BASE;
static volatile uint32_t *const uart=(volatile uint32_t *)DH_SOC_UART0_BASE;
static void stop(unsigned signature) {
    gpio[0]=signature;
    for(;;) __asm__ volatile("j .");
}
int main(void) {
    volatile uint32_t *mux=(volatile uint32_t *)0x40012200;
    for(unsigned i=0;i<3;i++) mux[i]=1;
    gpio[1]=7;gpio[0]=1;
    volatile uint8_t *tx=(volatile uint8_t *)0x20000200;
    volatile uint8_t *rx=(volatile uint8_t *)0x20000101;
    for(unsigned i=0;i<24;i++) tx[i]=(uint8_t)(71+29*i);
    for(unsigned i=0;i<8;i++) rx[i]=0;
    uart[0]=3;uart[1]=4096;uart[2]=1;
    if(uart[8]!=((4096u<<16)|3)) stop(7);
    dh_dma_ring ring;
    if(!dh_dma_ring_start(&ring,0,0,(uintptr_t)rx,8)) stop(7);
    DH_RING_WRITE(DH_DMA_ADDRESS1_OFFSET,(uint32_t)(uintptr_t)tx);
    DH_RING_WRITE(DH_DMA_COUNT1_OFFSET,24);
    DH_RING_WRITE(DH_DMA_ENDPOINT1_OFFSET,0);
    DH_RING_WRITE(DH_DMA_START_OFFSET,2);
    unsigned consumed=0;volatile unsigned work=0;
    while(consumed<24) {
        /* Real CPU work competes with DMA for SRAM and instruction service. */
        for(unsigned i=0;i<8;i++) work=(work<<1)^i;
        uint32_t available;
        if(!dh_dma_ring_available(&ring,&available)) stop(7);
        for(unsigned i=0;i<available;i++) {
            unsigned index=ring.read+i;if(index>=ring.length) index-=ring.length;
            if(consumed>=24 || rx[index]!=(uint8_t)(71+29*consumed)) stop(7);
            consumed++;
        }
        if(!dh_dma_ring_advance(&ring,available)) stop(7);
    }
    dh_dma_ring_abort(&ring);
    while(DH_RING_READ(DH_DMA_BUSY_OFFSET)&1) {}
    if((uart[6]&31) || (DH_RING_READ(DH_DMA_EVENTS_OFFSET)&0xff1)) stop(7);
    stop(5);
    return 0;
}
