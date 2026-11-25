/* Host-only port adapter. ROM policy/recovery C is compiled unchanged. */
#ifndef DH_BOOT_HOST_OVERRIDES_H
#define DH_BOOT_HOST_OVERRIDES_H
#define DH_PLATFORM_H
#include "boot.h"
volatile uint32_t *host_mmio(uint32_t);
#define MMIO(base,offset) (*host_mmio((uint32_t)(base)+(offset)))
uint32_t cycles(void);
static inline uint32_t misa(void){return UINT32_C(0x40101124);}
static inline void fence(void){}
int dh_uart_read(void);int dh_uart_errors(void);int dh_uart_write(uint8_t);
void dh_uart_initialize(void);
#endif
