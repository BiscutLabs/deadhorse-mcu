/* SPDX-License-Identifier: Apache-2.0 */
#include "platform.h"
static uint32_t swap(uint32_t w) {
 return (w<<24)|((w&0xff00u)<<8)|((w>>8)&0xff00u)|(w>>24);
}
static int qcommand(unsigned opcode,uint32_t address,unsigned address_bytes,
                    unsigned data_bytes,int read,uint32_t tx,uint32_t *rx) {
 /* A completed command can bypass the busy-loop poll entirely. Keep one
  * bounded receive service point between commands during recovery. */
 dh_recovery_poll();
 uint32_t begin=cycles();
 if(MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_STATUS_OFFSET)&1)return 0;
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_EVENTS_OFFSET)=3;
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_CONFIGURATION_OFFSET)=(address_bytes<<1)|(data_bytes<<4)|(read?128:0);
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_OPCODE_OFFSET)=opcode;
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_ADDRESS_OFFSET)=address;
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_TX_DATA_OFFSET)=tx;
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_LAUNCH_OFFSET)=UINT32_C(0x51535049);
 for(unsigned n=0;n<65536;n++) {
  uint32_t event=MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_EVENTS_OFFSET);
  if(event&2)return 0;
  if(event&1){if(rx)*rx=MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_RX_DATA_OFFSET);return 1;}
  if(cycles()-begin>=2*DH_CYCLES_PER_SECOND)return 0;
  dh_recovery_poll();
 }
 return 0;
}
int dh_flash_initialize(void) {
 if((MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_STATUS_OFFSET)&15)!=2)return 0;
 /* Surviving XIP must be disabled before chip0 commands; ROM executes locally. */
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_XIP_CONFIGURATION_OFFSET)=UINT32_C(0x306);
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_XIP_TIMING_OFFSET)=4;
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_XIP_APPLY_OFFSET)=UINT32_C(0x58495021);
 MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_TIMING_OFFSET)=4;
 return !(MMIO(DH_SOC_QSPI_CONTROL_BASE,DH_QSPI_XIP_STATUS_OFFSET)&3);
}
int dh_flash_ready(void) {
 uint32_t begin=cycles();
 for(unsigned n=0;n<65536;n++) {
  uint32_t status;if(!qcommand(5,0,0,1,1,0,&status))return 0;
  if(!(status&1))return 1;
  if(cycles()-begin>=2*DH_CYCLES_PER_SECOND)return 0;
  dh_recovery_poll();
 }
 return 0;
}
int dh_flash_read(uint32_t address,uint32_t *word) {
 uint32_t result;
 if(address>DH_FLASH_MAX-4||(address&3)||!qcommand(3,address,3,4,1,0,&result))return 0;
 *word=swap(result);return 1;
}
int dh_flash_program(uint32_t address,uint32_t word) {
 uint32_t check;
 if(address>DH_FLASH_MAX-4||(address&3)||!qcommand(6,0,0,0,0,0,0)||
    !qcommand(2,address,3,4,0,swap(word),0)||!dh_flash_ready())return 0;
 return dh_flash_read(address,&check)&&check==word;
}
int dh_flash_erase(uint32_t address) {
 if(address>DH_FLASH_MAX-4096||(address&4095)||!qcommand(6,0,0,0,0,0,0)||
    !qcommand(0x20,address,3,0,0,0,0)||!dh_flash_ready())return 0;
 for(unsigned n=0;n<4096;n+=4) {
  uint32_t word;if(!dh_flash_read(address+n,&word)||word!=UINT32_MAX)return 0;
 }
 return 1;
}
void dh_uart_initialize(void) {
 MMIO(DH_SOC_UART0_BASE,DH_UART_CONFIGURATION_OFFSET)=0;
 MMIO(DH_SOC_UART0_BASE,DH_UART_COMMAND_OFFSET)=1;
 MMIO(DH_SOC_UART0_BASE,DH_UART_COMMAND_OFFSET)=12;
 MMIO(DH_SOC_UART0_BASE,DH_UART_BAUD_OFFSET)=944;
 MMIO(DH_SOC_UART0_BASE,DH_UART_CONFIGURATION_OFFSET)=3;
 MMIO(DH_SOC_UART0_BASE,DH_UART_COMMAND_OFFSET)=1;
 MMIO(DH_SOC_UART0_BASE,DH_UART_EVENTS_OFFSET)=63;
}
int dh_uart_read(void) {
 if(!(MMIO(DH_SOC_UART0_BASE,DH_UART_STATUS_OFFSET)&2))return -1;
 uint32_t b=MMIO(DH_SOC_UART0_BASE,DH_UART_RX_DATA_OFFSET);
 MMIO(DH_SOC_UART0_BASE,DH_UART_COMMAND_OFFSET)=2;return b&255;
}
int dh_uart_errors(void) {
 uint32_t e=MMIO(DH_SOC_UART0_BASE,DH_UART_EVENTS_OFFSET)&10;
 if(e)MMIO(DH_SOC_UART0_BASE,DH_UART_EVENTS_OFFSET)=e;
 return e!=0;
}
int dh_uart_write(uint8_t value) {
 uint32_t begin=cycles();
 for(unsigned n=0;n<65536;n++) {
  if(MMIO(DH_SOC_UART0_BASE,DH_UART_STATUS_OFFSET)&1) {
   MMIO(DH_SOC_UART0_BASE,DH_UART_TX_DATA_OFFSET)=value;return 1;
  }
  if(cycles()-begin>=DH_CYCLES_PER_SECOND/10)return 0;
 }
 return 0;
}
void *memcpy(void *dst,const void *src,size_t n) {
 uint8_t *d=dst;const uint8_t *s=src;while(n--)*d++=*s++;return dst;
}
void dh_enter(uint32_t entry,uint32_t config,uint32_t bytes,uint32_t generation,uint32_t causes) {
 void (*application)(uint32_t,uint32_t,uint32_t,uint32_t)=(void *)(uintptr_t)entry;
 __asm__ volatile("fence.i":::"memory");
 application(config,bytes,generation,causes);
 dh_fail();
}
void *memset(void *dst,int value,size_t n) {
 uint8_t *d=dst;while(n--)*d++=(uint8_t)value;return dst;
}
