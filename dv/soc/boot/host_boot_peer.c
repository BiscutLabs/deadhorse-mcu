/* Independent native memory/MMIO peer; digital timing is tested in the SoC. */
#include "host_boot_overrides.h"
#include <setjmp.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
unsigned char flash_bytes[65536],release_perf[14336],release_lite[1024];
uint32_t flash_fail=UINT32_MAX,boot_status,boot_mode,reset_causes;
uint32_t entered[5],releases,payload_reads,boot_result;
static uint32_t release_key,context_key;
static jmp_buf returned;
extern void boot_main(void);
static void flush_keys(void) {
 if(context_key==UINT32_C(0x434f4e54)){boot_status|=16;context_key=0;}
 if(release_key==UINT32_C(0x50455246)) {
  if(!(boot_status&1))abort();
  memcpy(release_perf,(const void *)(uintptr_t)DH_PERF_BASE,sizeof(release_perf));
  memcpy(release_lite,(const void *)(uintptr_t)DH_LITE_BASE,sizeof(release_lite));
  releases++;boot_status=(boot_status&~1u)|2;release_key=0;
 }
}
volatile uint32_t *host_boot_mmio(uint32_t at) {
 flush_keys();
 if(at>=DH_PERF_BASE && at<DH_PERF_BASE+16384 && !(at&3))return (volatile uint32_t *)(uintptr_t)at;
 if(at>=DH_LITE_BASE && at<DH_LITE_BASE+1024 && !(at&3)) {
  if(!(boot_status&1))abort();
  return (volatile uint32_t *)(uintptr_t)at;
 }
 switch(at) {
 case 0x40000300:return &boot_status;
 case 0x40000304:return &release_key;
 case 0x40000310:return &boot_mode;
 case 0x40000314:return &context_key;
 case 0x40000500:return &reset_causes;
 default:abort();
 }
}
void host_boot_init(void) {
 static int mapped;
 if(!mapped) {
  for(unsigned n=0;n<2;n++) {
   uintptr_t base=n?DH_LITE_BASE:DH_PERF_BASE;size_t size=n?4096:16384;
   if(mmap((void *)base,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0)==MAP_FAILED)abort();
  }
  mapped=1;
 }
 memset((void *)(uintptr_t)DH_PERF_BASE,0xa5,16384);
 memset((void *)(uintptr_t)DH_LITE_BASE,0x5a,4096);
 memset(flash_bytes,255,sizeof(flash_bytes));flash_fail=UINT32_MAX;
 boot_status=1;boot_mode=0;reset_causes=1;release_key=0;context_key=0;
 releases=0;payload_reads=0;boot_result=0;
}
void host_boot_warm(uint32_t causes) {
 boot_status=(boot_status&16)|9;reset_causes=causes;
 release_key=0;context_key=0;releases=0;payload_reads=0;boot_result=0;
}
int dh_flash_initialize(void){return 1;}
int dh_flash_ready(void){return 1;}
int dh_flash_read(uint32_t at,uint32_t *word) {
 if(at>65532||(at&3)||at==flash_fail)return 0;
 if(at>=4096&&(at-4096)%16384>=256)payload_reads++;
 *word=(uint32_t)flash_bytes[at]|((uint32_t)flash_bytes[at+1]<<8)|
       ((uint32_t)flash_bytes[at+2]<<16)|((uint32_t)flash_bytes[at+3]<<24);
 return 1;
}
void dh_enter(uint32_t entry,uint32_t config,uint32_t bytes,uint32_t generation,uint32_t causes) {
 flush_keys();entered[0]=entry;entered[1]=config;entered[2]=bytes;entered[3]=generation;entered[4]=causes;
 boot_result=1;longjmp(returned,1);
}
void dh_run_recovery(const dh_directory *d,int valid){(void)d;(void)valid;boot_result=2;longjmp(returned,1);}
void dh_fail(void){boot_result=3;longjmp(returned,1);}
unsigned host_boot_run(void){if(!setjmp(returned))boot_main();return boot_result;}
