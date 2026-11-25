#include "dma_ring.h"
/* An illustrative length-prefixed byte stream, unrelated to radio/GPS formats.
 * Call once per application loop, before one whole ring can pass unseen.
 * A zero/oversize length drops the partial frame; overflow is not detected. */
struct frame_reader { uint8_t bytes[32]; unsigned needed,used; };
bool dma_ring_poll_frame(dh_dma_ring *ring,struct frame_reader *frame,
                         void (*received)(const uint8_t *,unsigned)) {
    uint32_t count;
    if(!dh_dma_ring_available(ring,&count)) return false;
    const volatile uint8_t *buffer=(const volatile uint8_t *)(uintptr_t)ring->base;
    for(uint32_t n=0;n<count;n++) {
        uint32_t index=ring->read+n;
        if(index>=ring->length) index-=ring->length;
        uint8_t byte=buffer[index];
        if(!frame->needed) {
            frame->needed=byte<=sizeof frame->bytes ? byte : 0;
            frame->used=0;
        } else {
            frame->bytes[frame->used++]=byte;
            if(frame->used==frame->needed) {
                received(frame->bytes,frame->used);frame->needed=0;
            }
        }
    }
    return dh_dma_ring_advance(ring,count);
}
