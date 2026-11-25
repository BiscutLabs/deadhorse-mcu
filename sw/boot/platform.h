/* SPDX-License-Identifier: Apache-2.0 */
#ifndef DH_PLATFORM_H
#define DH_PLATFORM_H
#include "boot.h"
#include "soc.h"
#include "qspi_regs.h"
#include "uart_regs.h"
#include "boot_control_regs.h"
#include "dma_regs.h"
#define MMIO(base,offset) (*(volatile uint32_t *)((uintptr_t)(base)+(offset)))
static inline uint32_t cycles(void) {uint32_t n;__asm__ volatile("csrr %0, mcycle":"=r"(n));return n;}
static inline uint32_t misa(void) {uint32_t n;__asm__ volatile("csrr %0, misa":"=r"(n));return n;}
static inline void fence(void) {__asm__ volatile("fence rw,rw":::"memory");}
int dh_uart_read(void);
int dh_uart_errors(void);
int dh_uart_write(uint8_t value);
void dh_uart_initialize(void);
void dh_run_recovery(const dh_directory *directory,int directory_valid) __attribute__((noreturn));
#endif
