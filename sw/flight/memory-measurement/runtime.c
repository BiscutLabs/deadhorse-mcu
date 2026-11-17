#include <stddef.h>
#include <stdint.h>

void *memcpy(void *dst, const void *src, size_t n) {
    unsigned char *d = dst; const unsigned char *s = src;
    while (n--) *d++ = *s++;
    return dst;
}
void *memset(void *dst, int c, size_t n) {
    unsigned char *d = dst;
    while (n--) *d++ = (unsigned char)c;
    return dst;
}
void hex(uint32_t value) {
    volatile unsigned char *uart = (void *)0x10000000;
    for (int n = 28; n >= 0; n -= 4) {
        unsigned digit = (value >> n) & 15;
        *uart = digit < 10 ? '0' + digit : 'a' + digit - 10;
    }
    *uart = ' ';
}
void line(void) { *(volatile unsigned char *)0x10000000 = '\n'; }
__attribute__((noreturn)) void finish(unsigned code) {
    *(volatile uint32_t *)0x100000 = code ? (code << 16) | 0x3333 : 0x5555;
    for (;;) __asm__ volatile("wfi");
}
