/* SPDX-License-Identifier: Apache-2.0 */
#include "platform.h"
#define BOOT UINT32_C(0x40000300)
static dh_directory directory;
dh_header dh_selected;
#define selected dh_selected
static uint32_t selected_slot;
static int read_directory(void) {
 uint32_t words[8];
 for(unsigned n=0;n<8;n++)if(!dh_flash_read(4*n,&words[n]))return 0;
 return dh_directory_decode(words,&directory);
}
static uint32_t memory_crc(uint32_t to,uint32_t bytes) {
 /* All accepted image lengths/destinations are word aligned. Read each AON
  * program word once, then fold its four bytes in the same little-endian order
  * as dh_crc; byte loads would repeat the slow bridge transaction four times. */
 fence();uint32_t actual=UINT32_MAX;
 for(uint32_t n=0;n<bytes;n+=4) {
  uint32_t word=MMIO(to,n);
  for(unsigned lane=0;lane<4;lane++){actual=dh_crc_byte(actual,word&255);word>>=8;}
 }
 return ~actual;
}
static int copy_verify(uint32_t from,uint32_t to,uint32_t bytes,uint32_t crc) {
 for(uint32_t n=0;n<bytes;n+=4) {
  uint32_t word;if(!dh_flash_read(from+n,&word))return 0;
  MMIO(to,n)=word;
 }
 return memory_crc(to,bytes)==crc;
}
static void release_lite(void) {
 if(selected.w[H_FLAGS]&1) {
  MMIO(BOOT,4)=UINT32_C(0x50455246);
  if(!(MMIO(BOOT,0)&2))dh_fail();
 }
}
static void enter(void) __attribute__((noreturn));
static void enter(void) {
 const uint32_t causes=(MMIO(UINT32_C(0x40000500),0)&63)|((MMIO(BOOT,0)&8)?0:64);
 dh_enter(DH_PERF_BASE+selected.w[H_PERF_ENTRY],DH_CONFIG_BASE,selected.w[H_CONFIG_BYTES],selected.w[H_GENERATION],causes);
}
void boot_main(void) {
 const uint32_t status=MMIO(BOOT,0);
 volatile dh_context *ctx=(volatile dh_context *)(uintptr_t)DH_CONTEXT_BASE;
 if(!dh_flash_initialize()||!dh_flash_ready()) {
  if(status&8)dh_fail();
  ctx->magic=0;fence();dh_run_recovery(&directory,0);
 }
 if(status&8) {
  /* Context must have been committed in this hardware reset epoch. */
  if(!(status&16)||ctx->magic!=DH_CONTEXT_MAGIC||ctx->version!=1||ctx->reserved[0]||ctx->reserved[1]||
     ctx->crc!=dh_crc((const void *)(uintptr_t)(DH_CONTEXT_BASE+4),112))dh_fail();
  directory.stride=ctx->stride;directory.capacity=ctx->capacity;
  if(!directory.stride||(directory.stride&4095)||(directory.capacity&4095)||
     directory.capacity>DH_FLASH_MAX||directory.capacity<4096||
     directory.stride>(directory.capacity-4096)/3)dh_fail();
  selected_slot=ctx->slot;
  if(selected_slot!=dh_slot(&directory,0)&&selected_slot!=dh_slot(&directory,1)&&selected_slot!=dh_slot(&directory,2))dh_fail();
  for(unsigned n=0;n<H_WORDS;n++)selected.w[n]=ctx->header.w[n];
  if(!dh_header_valid(&selected,&directory,selected_slot==4096,1,misa()))dh_fail();
  for(unsigned n=0;n<H_WORDS;n++) {
   uint32_t word;if(!dh_flash_read(selected_slot+4*n,&word)||word!=selected.w[n])dh_fail();
  }
  if(!(MMIO(BOOT,0)&1))dh_fail();
  const int performance_valid=memory_crc(DH_PERF_BASE,selected.w[H_PERF_BYTES])==selected.w[H_PERF_CRC];
  const int lite_valid=memory_crc(DH_LITE_BASE,selected.w[H_LITE_BYTES])==selected.w[H_LITE_CRC];
  #ifndef DH_BOOT_FAULT_WARM_SKIP_RELOAD
  if(!performance_valid||!lite_valid) {
   if(!copy_verify(selected_slot+256,DH_PERF_BASE,selected.w[H_PERF_BYTES],selected.w[H_PERF_CRC])||
      !copy_verify(selected_slot+256+selected.w[H_PERF_BYTES],DH_LITE_BASE,
                   selected.w[H_LITE_BYTES],selected.w[H_LITE_CRC]))dh_fail();
  }
  #else
  (void)performance_valid;(void)lite_valid;
  #endif
  release_lite();
  enter();
 }
 ctx->magic=0;fence();
 int valid_directory=read_directory();
 if(MMIO(BOOT,16)&1)dh_run_recovery(&directory,valid_directory);
 if(!valid_directory||!dh_choose(&directory,&selected,&selected_slot,misa()))dh_run_recovery(&directory,valid_directory);
 if(!(MMIO(BOOT,0)&1))dh_fail();
 #ifdef DH_BOOT_FAULT_EARLY_RELEASE
 MMIO(BOOT,4)=UINT32_C(0x50455246);
 #endif
 uint32_t at=selected_slot+256;
 if(!copy_verify(at,DH_PERF_BASE,selected.w[H_PERF_BYTES],selected.w[H_PERF_CRC]))dh_fail();
 at+=selected.w[H_PERF_BYTES];
 if(!copy_verify(at,DH_LITE_BASE,selected.w[H_LITE_BYTES],selected.w[H_LITE_CRC]))dh_fail();
 at+=selected.w[H_LITE_BYTES];
 if(!copy_verify(at,DH_CONFIG_BASE,selected.w[H_CONFIG_BYTES],selected.w[H_CONFIG_CRC]))dh_fail();
 ctx->version=1;ctx->stride=directory.stride;ctx->capacity=directory.capacity;ctx->slot=selected_slot;
 for(unsigned n=0;n<H_WORDS;n++)ctx->header.w[n]=selected.w[n];
 ctx->reserved[0]=0;ctx->reserved[1]=0;
 ctx->crc=dh_crc((const void *)(uintptr_t)(DH_CONTEXT_BASE+4),112);
 fence();ctx->magic=DH_CONTEXT_MAGIC;fence();
 MMIO(BOOT,20)=UINT32_C(0x434f4e54);fence();
 if(!(MMIO(BOOT,0)&16))dh_fail();
 release_lite();
 enter();
}
