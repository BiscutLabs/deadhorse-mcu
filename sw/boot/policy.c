/* SPDX-License-Identifier: Apache-2.0
 * Directory arithmetic and bitwise CRC adapted from pinned RISCay boot.c /
 * boot_slots.py at4671317186003740ceb61360ba08c59bbdf10136. Paired ABI is new.
 */
#include "boot.h"
/* Compile-time reflected CRC-32 remainders. No RAM table or initialization.
 * The independent test uses zlib plus a bitwise arbitrary-remainder oracle. */
#define CRC_STEP(c) (((c)>>1) ^ (UINT32_C(0xedb88320)&(0u-((c)&1u))))
#define CRC_TWO(c) CRC_STEP(CRC_STEP(c))
#define CRC_FOUR(c) CRC_TWO(CRC_TWO(c))
#define CRC_ENTRY(c) CRC_FOUR(CRC_FOUR(c))
#define CRC_ROW(x) CRC_ENTRY((x)+0u),CRC_ENTRY((x)+1u),CRC_ENTRY((x)+2u),CRC_ENTRY((x)+3u), \
 CRC_ENTRY((x)+4u),CRC_ENTRY((x)+5u),CRC_ENTRY((x)+6u),CRC_ENTRY((x)+7u), \
 CRC_ENTRY((x)+8u),CRC_ENTRY((x)+9u),CRC_ENTRY((x)+10u),CRC_ENTRY((x)+11u), \
 CRC_ENTRY((x)+12u),CRC_ENTRY((x)+13u),CRC_ENTRY((x)+14u),CRC_ENTRY((x)+15u)
static const uint32_t crc_table[256]={
 CRC_ROW(0u),CRC_ROW(16u),CRC_ROW(32u),CRC_ROW(48u),
 CRC_ROW(64u),CRC_ROW(80u),CRC_ROW(96u),CRC_ROW(112u),
 CRC_ROW(128u),CRC_ROW(144u),CRC_ROW(160u),CRC_ROW(176u),
 CRC_ROW(192u),CRC_ROW(208u),CRC_ROW(224u),CRC_ROW(240u)
};
uint32_t dh_crc_byte(uint32_t c,uint8_t b) {
 return (c>>8)^crc_table[(c^b)&255u];
}
uint32_t dh_crc(const void *bytes,uint32_t count) {
 const uint8_t *p=bytes;uint32_t c=~0u;
 for(uint32_t i=0;i<count;i++)c=dh_crc_byte(c,p[i]);
 #ifdef DH_BOOT_FAULT_CRC
 return ~c^1u;
 #else
 return ~c;
 #endif
}
int dh_directory_decode(const uint32_t w[8],dh_directory *out) {
 if(w[0]!=DH_DIRECTORY_MAGIC||w[1]!=2||w[7]!=dh_crc(w,28)||!w[2]||
    (w[2]&4095u)||(w[3]&4095u)||w[3]>DH_FLASH_MAX||w[3]<4096||
    w[2]>(w[3]-4096)/3||w[4]!=4096+w[2]||w[5]!=4096+2*w[2]||w[6]!=4096)return 0;
 out->stride=w[2];out->capacity=w[3];return 1;
}
uint32_t dh_slot(const dh_directory *d,unsigned slot) {return 4096+slot*d->stride;}
int dh_header_valid(const dh_header *h,const dh_directory *d,int golden,int committed,uint32_t misa) {
 const uint32_t *w=h->w;
 if(w[H_MAGIC]!=DH_IMAGE_MAGIC||w[H_VERSION]!=3||w[H_HARDWARE]!=1||
    w[H_RESERVED0]||w[H_RESERVED1]||w[H_RESERVED2]||w[H_CRC]!=dh_crc(w,88)||
    w[H_COMMIT]!=(committed?DH_COMMIT:~0u)||(w[H_FLAGS]&~1u))return 0;
 if(golden?w[H_GENERATION]!=0:(w[H_GENERATION]==0||w[H_GENERATION]==~0u))return 0;
 if(!w[H_PERF_BYTES]||(w[H_PERF_BYTES]&3)||w[H_PERF_BYTES]>DH_PERF_BYTES||
    w[H_PERF_ENTRY]>=w[H_PERF_BYTES]||(w[H_PERF_ENTRY]&1)||
    w[H_PERF_ALLOCATION]<w[H_PERF_BYTES]||w[H_PERF_ALLOCATION]>DH_PERF_BYTES)return 0;
 if(!w[H_LITE_BYTES]||(w[H_LITE_BYTES]&3)||w[H_LITE_BYTES]>DH_LITE_BYTES||w[H_LITE_ENTRY]||
    w[H_LITE_STACK]<16||w[H_LITE_STACK]>1024||w[H_LITE_DATA]>1024-w[H_LITE_STACK])return 0;
 if((w[H_PERF_ISA]&UINT32_C(0xc0000100))!=UINT32_C(0x40000100)||
    (w[H_PERF_ISA]&~misa)||w[H_LITE_ISA]!=UINT32_C(0x40000010))return 0;
 if((w[H_CONFIG_BYTES]&3)||w[H_CONFIG_BYTES]>256||(!w[H_CONFIG_BYTES]&&w[H_CONFIG_CRC]))return 0;
 /* Each addend was bounded above before this sum. */
 uint32_t extent=256+w[H_PERF_BYTES]+w[H_LITE_BYTES]+w[H_CONFIG_BYTES];
 return w[H_EXTENT]==extent&&extent<=d->stride;
}
int dh_read_header(uint32_t slot,dh_header *h) {
 for(unsigned i=0;i<H_WORDS;i++)if(!dh_flash_read(slot+4*i,&h->w[i]))return 0;
 return 1;
}
static int crc_flash(uint32_t address,uint32_t bytes,uint32_t expected) {
 uint32_t c=~0u;
 for(uint32_t n=0;n<bytes;n+=4) {
  uint32_t word;if(!dh_flash_read(address+n,&word))return -1;
  for(unsigned i=0;i<4;i++){c=dh_crc_byte(c,word&255);word>>=8;}
 }
 return ~c==expected;
}
int dh_payload_status(uint32_t slot,const dh_header *h) {
 uint32_t at=slot+256;
 for(unsigned segment=0;segment<3;segment++) {
  unsigned length=segment==0?H_PERF_BYTES:segment==1?H_LITE_BYTES:H_CONFIG_BYTES;
  unsigned checksum=segment==0?H_PERF_CRC:segment==1?H_LITE_CRC:H_CONFIG_CRC;
  int status=crc_flash(at,h->w[length],h->w[checksum]);if(status!=1)return status;
  at+=h->w[length];
 }
 return 1;
}
int dh_payload_valid(uint32_t slot,const dh_header *h) {return dh_payload_status(slot,h)==1;}
int dh_choose(const dh_directory *d,dh_header *best,uint32_t *slot,uint32_t misa) {
 dh_header candidate;int found=0;
 for(unsigned n=1;n<=2;n++) {
  uint32_t address=dh_slot(d,n);
  if(dh_read_header(address,&candidate)&&dh_header_valid(&candidate,d,0,1,misa)&&dh_payload_valid(address,&candidate)&&
     (!found||candidate.w[H_GENERATION]>best->w[H_GENERATION])) {*best=candidate;*slot=address;found=1;}
 }
 if(!found) {
  uint32_t address=dh_slot(d,0);
  if(dh_read_header(address,best)&&dh_header_valid(best,d,1,1,misa)&&dh_payload_valid(address,best)) {*slot=address;found=1;}
 }
 return found;
}
