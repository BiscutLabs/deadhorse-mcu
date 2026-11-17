#include <stdint.h>
void hex(uint32_t); void line(void);
/* Concrete loader/wake subset only. Capacities are fixture assumptions. */
uint8_t loader_chunk[128], wake_queue[32], calibration[64];
struct { uint32_t sequence, crc, wake_count; } retained;
__attribute__((noinline)) static uint32_t crc32(uint32_t crc, uint8_t byte) {
    crc ^= byte;
    for (unsigned b = 0; b < 8; ++b) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1)));
    return crc;
}
__attribute__((noinline)) void lite_iteration(unsigned frame) {
    uint32_t crc = 0xffffffff;
    for (unsigned i = 0; i < sizeof loader_chunk; ++i) {
        loader_chunk[i] = (uint8_t)(frame + i);
        crc = crc32(crc, loader_chunk[i]);
    }
    wake_queue[frame & 31] = 1;
    calibration[frame & 63] = (uint8_t)crc;
    retained.sequence = frame; retained.crc = ~crc; ++retained.wake_count;
#ifdef BAD_LITE_CRC
    retained.crc ^= 1; /* Actual firmware checksum fault, observed by Python. */
#endif
    hex(0x50); hex(frame); hex(retained.crc); hex(retained.wake_count); line();
}
__attribute__((noinline)) void lite_hot_loop(void) {
    for (unsigned frame = 0; frame < 4; ++frame) lite_iteration(frame);
}
int main(void) {
    lite_hot_loop();
    return 0;
}
