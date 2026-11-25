#ifndef DH_DMA_RING_H
#define DH_DMA_RING_H
#include <stdint.h>
#include <stdbool.h>
#include "dma_regs.h"
#include "soc.h"

/* Performance-only. Caller owns this channel/UART and consumes before a lap
 * can be overwritten. Hooks let the native test use an independent MMIO model. */
#ifndef DH_RING_READ
#define DH_RING_READ(offset) (*(volatile uint32_t *)(uintptr_t)(DH_SOC_DMA_BASE+(offset)))
#define DH_RING_WRITE(offset,value) (*(volatile uint32_t *)(uintptr_t)(DH_SOC_DMA_BASE+(offset))=(value))
#endif
static inline void dh_ring_acquire(void) {
#ifdef __riscv
    __asm__ volatile("fence ir,r" ::: "memory");
#else
    __asm__ volatile("" ::: "memory");
#endif
}
typedef struct { uint32_t base, length, read; unsigned channel; } dh_dma_ring;

static inline bool dh_dma_ring_start(dh_dma_ring *r,unsigned channel,unsigned uart,
                                      uintptr_t buffer,uint32_t length) {
    static const unsigned rx[3]={1,3,5};
    if(!r || channel>=4 || uart>=3 || length<2 || length>65535 ||
       buffer<DH_SOC_PERFORMANCE_SRAM_BASE ||
       buffer>=DH_SOC_PERFORMANCE_SRAM_BASE+DH_SOC_PERFORMANCE_SRAM_SIZE ||
       length>DH_SOC_PERFORMANCE_SRAM_BASE+DH_SOC_PERFORMANCE_SRAM_SIZE-buffer)
        return false;
    uint32_t bit=1u<<channel;
    if(DH_RING_READ(DH_DMA_BUSY_OFFSET)&bit) return false;
    DH_RING_WRITE(DH_DMA_EVENTS_OFFSET,bit*0x111111u);
    DH_RING_WRITE(DH_DMA_ADDRESS0_OFFSET+4*channel,(uint32_t)buffer);
    DH_RING_WRITE(DH_DMA_COUNT0_OFFSET+4*channel,length);
    DH_RING_WRITE(DH_DMA_ENDPOINT0_OFFSET+4*channel,rx[uart]|DH_DMA_ENDPOINT0_CIRCULAR_MASK);
    DH_RING_WRITE(DH_DMA_START_OFFSET,bit);
    if(!(DH_RING_READ(DH_DMA_BUSY_OFFSET)&bit) || (DH_RING_READ(DH_DMA_EVENTS_OFFSET)&(bit<<8))) return false;
    *r=(dh_dma_ring){(uint32_t)buffer,length,0,channel};
    return true;
}
/* Returns false on stopped/faulted/config-error channels; does not report
 * overwritten laps. SRAM bytes below this published snapshot are committed. */
static inline bool dh_dma_ring_available(const dh_dma_ring *r,uint32_t *available) {
    if(!r || !available || r->channel>=4 || r->length<2 || r->read>=r->length) return false;
    uint32_t bit=1u<<r->channel;
    if(!(DH_RING_READ(DH_DMA_BUSY_OFFSET)&bit)) return false;
    uint32_t current=DH_RING_READ(DH_DMA_CURRENT0_OFFSET+4*r->channel);
    uint32_t events=DH_RING_READ(DH_DMA_EVENTS_OFFSET);
    if(!(DH_RING_READ(DH_DMA_BUSY_OFFSET)&bit) || (events&(bit*0x1110u)) ||
       current<r->base || current-r->base>=r->length) return false;
    dh_ring_acquire();
    uint32_t write=current-r->base;
    *available=write>=r->read ? write-r->read : r->length-r->read+write;
    return true;
}
static inline bool dh_dma_ring_advance(dh_dma_ring *r,uint32_t count) {
    uint32_t available;
    if(!dh_dma_ring_available(r,&available) || count>available) return false;
    r->read+=count;
    if(r->read>=r->length) r->read-=r->length;
    return true;
}
static inline void dh_dma_ring_abort(const dh_dma_ring *r) {
    DH_RING_WRITE(DH_DMA_ABORT_OFFSET,1u<<r->channel);
    /* Drain is asynchronous: poll busy before reusing storage/descriptors. */
}
#endif
