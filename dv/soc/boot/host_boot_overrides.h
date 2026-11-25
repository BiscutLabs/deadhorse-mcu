/* Native adapters for the unchanged production boot_main and policy C. */
#ifndef DH_BOOT_HOST_MAIN_H
#define DH_BOOT_HOST_MAIN_H
#define DH_PLATFORM_H
#include "boot.h"
volatile uint32_t *host_boot_mmio(uint32_t);
#define MMIO(base,offset) (*host_boot_mmio((uint32_t)(base)+(offset)))
static inline uint32_t misa(void){return UINT32_C(0x40101124);}
static inline void fence(void){}
void dh_enter(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t) __attribute__((noreturn));
void dh_run_recovery(const dh_directory *,int) __attribute__((noreturn));
#endif
