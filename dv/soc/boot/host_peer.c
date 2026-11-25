/* Independent host-level NOR/UART adapter; wire checks are separate. */
#include "host_overrides.h"
#include <setjmp.h>
#include <stdlib.h>
#include <string.h>
dh_header dh_selected;
unsigned char flash_bytes[65536],input_bytes[4096],output_bytes[4096];
unsigned input_size,input_at,output_size,erases,programs,program_commit_index;
uint32_t fail_address=UINT32_MAX,staging_words[64];
unsigned cut_after=UINT32_MAX,mutations;
unsigned error_pending,clock_ticks;
static unsigned initializing;
static jmp_buf initial_return;
extern void dh_recovery_loop(const dh_directory *,int);
volatile uint32_t *host_mmio(uint32_t at) {
 static uint32_t forbidden;
 if(at<DH_STAGING_BASE||at>=DH_STAGING_BASE+256||(at&3))return &forbidden;
 return staging_words+(at-DH_STAGING_BASE)/4;
}
uint32_t cycles(void){return clock_ticks++;}
int dh_uart_read(void) {
 if(initializing){initializing=0;longjmp(initial_return,1);}
 if(input_at==input_size)return -1;
 return input_bytes[input_at++];
}
int dh_uart_errors(void){unsigned e=error_pending;error_pending=0;return e;}
int dh_uart_write(uint8_t v){if(output_size>=sizeof(output_bytes))abort();output_bytes[output_size++]=v;return 1;}
void dh_uart_initialize(void){}
int dh_flash_read(uint32_t at,uint32_t *word) {
 if(at>65532||at==fail_address)return 0;
 *word=(uint32_t)flash_bytes[at]|((uint32_t)flash_bytes[at+1]<<8)|((uint32_t)flash_bytes[at+2]<<16)|((uint32_t)flash_bytes[at+3]<<24);
 dh_recovery_poll();return 1;
}
int dh_flash_program(uint32_t at,uint32_t word) {
 if(at>65532||(at&3))return 0;
 ++programs;
 if((at-4096)%16384==92&&word==DH_COMMIT)program_commit_index=programs;
 for(unsigned n=0;n<4;n++)flash_bytes[at+n]&=(word>>(8*n))&255;
 if(++mutations==cut_after)return 0;
 dh_recovery_poll();return 1;
}
int dh_flash_erase(uint32_t at) {
 if(at>61440||(at&4095))return 0;
 ++erases;
 if(++mutations==cut_after){memset(flash_bytes+at,255,512);return 0;}
 memset(flash_bytes+at,255,4096);dh_recovery_poll();return 1;
}
void host_init(void) {
 dh_directory d={16384,65536};initializing=1;
 if(!setjmp(initial_return))dh_recovery_loop(&d,1);
}
void host_poll(void){dh_recovery_poll();}
