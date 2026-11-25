/* SPDX-License-Identifier: Apache-2.0 */
#include "platform.h"
enum { OK,BAD_REQUEST,DENIED,BUS_ERROR,TIMEOUT,BUSY };
static uint8_t frame[272],previous[270],reply[24];
static uint16_t used,previous_size,reply_size;
static uint32_t last_byte;
static uint8_t active,discard,executing,have_previous,update_active;
static dh_header update_header;
static dh_directory update_directory;
static uint32_t update_slot,next_offset;
static uint8_t directory_valid;
static uint32_t get32(const uint8_t *p) {
 return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static void put32(uint8_t *p,uint32_t v) {for(unsigned i=0;i<4;i++){p[i]=v&255;v>>=8;}}
static int equal(const uint8_t *a,const uint8_t *b,unsigned n) {
 for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;
 return 1;
}
/* COBS decoded in place. Input is bounded before any access. */
static unsigned decode(unsigned n) {
 unsigned read=0,write=0;
 while(read<n) {
  unsigned code=frame[read++];if(!code||code-1>n-read)return 0;
  for(unsigned i=1;i<code;i++)frame[write++]=frame[read++];
  if(code!=255&&read<n)frame[write++]=0;
 }
 return write;
}
static void send(const uint8_t *bytes,unsigned n) {
 /* Responses are short enough that a COBS run never reaches 254 bytes. */
 unsigned at=0;
 while(at<n) {
  unsigned end=at;while(end<n&&bytes[end])end++;
  if(!dh_uart_write((uint8_t)(end-at+1)))return;
  while(at<end)if(!dh_uart_write(bytes[at++]))return;
  if(end<n){at++;if(at==n&&!dh_uart_write(1))return;}
 }
 (void)dh_uart_write(0);
}
static unsigned response(uint8_t *out,const uint8_t *request,uint8_t status,uint32_t value,unsigned count) {
 for(unsigned i=0;i<8;i++)out[i]=request[i];
 out[0]=1;out[1]|=128;out[8]=(uint8_t)(count+1);out[9]=0;out[10]=status;
 for(unsigned i=0;i<count;i++){out[11+i]=value&255;value>>=8;}
 put32(out+11+count,dh_crc(out,11+count));return 15+count;
}
static int staging(uint32_t address,unsigned bytes) {
 #ifdef DH_BOOT_FAULT_RANGE
 (void)address;(void)bytes;return 1;
 #else
 return !(address&3)&&address>=DH_STAGING_BASE&&address<=DH_STAGING_BASE+DH_STAGING_BYTES&&
        bytes<=DH_STAGING_BASE+DH_STAGING_BYTES-address;
 #endif
}
static unsigned begin_update(uint32_t target,unsigned length) {
 update_active=0;
 if(!directory_valid||target>1||length!=sizeof(dh_header))return BAD_REQUEST;
 for(unsigned i=0;i<H_WORDS;i++) {
  update_header.w[i]=get32(previous+10+4*i);
  if((i&3)==3)dh_recovery_poll();
 }
 if(!dh_header_valid(&update_header,&update_directory,0,0,misa()))return BAD_REQUEST;
 dh_recovery_poll();
 dh_header *candidate=&dh_selected;uint32_t newest=0;unsigned protected_slot=0;
 for(unsigned n=1;n<=2;n++) {
  uint32_t at=dh_slot(&update_directory,n);
  if(!dh_read_header(at,candidate))return BUS_ERROR;
  if(dh_header_valid(candidate,&update_directory,0,1,misa())) {
   int integrity=dh_payload_status(at,candidate);if(integrity<0)return BUS_ERROR;
   if(integrity&&candidate->w[H_GENERATION]>newest){newest=candidate->w[H_GENERATION];protected_slot=n;}
  }
 }
 if(update_header.w[H_GENERATION]<=newest||protected_slot==target+1)return DENIED;
 update_slot=dh_slot(&update_directory,target+1);
 for(uint32_t n=0;n<update_directory.stride;n+=4096)if(!dh_flash_erase(update_slot+n))return BUS_ERROR;
 next_offset=256;update_active=1;return OK;
}
static unsigned data_update(uint32_t address,unsigned length) {
 if(!update_active||!length||(length&3)||address!=next_offset||
    length>update_header.w[H_EXTENT]-next_offset)return BAD_REQUEST;
 for(unsigned n=0;n<length;n+=4)if(!dh_flash_program(update_slot+address+n,get32(previous+10+n)))return BUS_ERROR;
 next_offset+=length;return OK;
}
static unsigned commit_update(uint32_t address,unsigned length) {
 if(!update_active||address||length||next_offset!=update_header.w[H_EXTENT])return BAD_REQUEST;
 if(!dh_payload_valid(update_slot,&update_header))return BUS_ERROR;
 #ifdef DH_BOOT_FAULT_COMMIT
 if(!dh_flash_program(update_slot+4*H_COMMIT,DH_COMMIT))return BUS_ERROR;
 #endif
 for(unsigned n=0;n<H_COMMIT;n++)if(!dh_flash_program(update_slot+4*n,update_header.w[n]))return BUS_ERROR;
 #ifndef DH_BOOT_FAULT_COMMIT
 if(!dh_flash_program(update_slot+4*H_COMMIT,DH_COMMIT))return BUS_ERROR;
 #endif
 update_active=0;return OK;
}
static void __attribute__((noinline)) execute(unsigned n) {
 const unsigned opcode=previous[1],length=n-14;
 const uint32_t address=get32(previous+4);
 unsigned status=OK,count=opcode==3?2:0;uint32_t value=0;
 if(previous[0]!=1)status=BAD_REQUEST;
 else if(opcode==1) {
  if(length)status=BAD_REQUEST;
  else if(!staging(address,4))status=DENIED;
  else {value=MMIO(address,0);count=4;}
 } else if(opcode==2) {
  if(length!=5||(previous[14]&240))status=BAD_REQUEST;
  else if(!staging(address,4))status=DENIED;
  else {
   uint32_t mask=0;for(unsigned i=0;i<4;i++)if(previous[14]&(1u<<i))mask|=255u<<(8*i);
   MMIO(address,0)=(MMIO(address,0)&~mask)|(get32(previous+10)&mask);
  }
 } else if(opcode==3) {
  if(!length||(length&3))status=BAD_REQUEST;
  else if(!staging(address,length))status=DENIED;
  else {for(unsigned i=0;i<length;i+=4)MMIO(address,i)=get32(previous+10+i);value=length;}
 } else if(opcode==5) {
  if(address||length)status=BAD_REQUEST;
  else {
   reply_size=(uint16_t)response(reply,previous,OK,0,0);
   reply[8]=10;reply[11]=1;put32(reply+12,UINT32_C(0x35304844));put32(reply+16,UINT32_C(0x117));
   put32(reply+20,dh_crc(reply,20));reply_size=24;return;
  }
 } else if(opcode==0x10)status=begin_update(address,length);
 else if(opcode==0x11)status=data_update(address,length);
 else if(opcode==0x12)status=commit_update(address,length);
 else status=BAD_REQUEST;
 if(opcode>=0x10&&opcode<=0x12&&status!=OK)update_active=0;
 reply_size=(uint16_t)response(reply,previous,(uint8_t)status,value,count);
}
static void __attribute__((noinline)) received(unsigned n) {
 if(n<14||n>270||get32(frame+n-4)!=dh_crc(frame,n-4)||
    ((unsigned)frame[8]|((unsigned)frame[9]<<8))!=n-14)return;
 uint8_t short_reply[17];
 if(executing) {
  send(short_reply,response(short_reply,frame,BUSY,0,frame[1]==3?2:0));return;
 }
 if(have_previous&&frame[2]==previous[2]&&frame[3]==previous[3]) {
  if(n==previous_size&&equal(frame,previous,n))send(reply,reply_size);
  else send(short_reply,response(short_reply,frame,BAD_REQUEST,0,frame[1]==3?2:0));
  return;
 }
 for(unsigned i=0;i<n;i++)previous[i]=frame[i];
 previous_size=(uint16_t)n;executing=1;
 /* The immutable request snapshot is complete. Nested frames now receive
  * BUSY and cannot alter it. Service at most the hardware FIFO's eight slots
  * before header validation; never poll while frame is being decoded/copied. */
 for(unsigned i=0;i<8;i++)dh_recovery_poll();
 execute(n);executing=0;have_previous=1;send(reply,reply_size);
}
void dh_recovery_poll(void) {
 if(!active)return;
 uint32_t now=cycles();
 if(dh_uart_errors()||(used&&now-last_byte>=DH_CYCLES_PER_SECOND/10)){used=0;discard=1;}
 int byte=dh_uart_read();if(byte<0)return;last_byte=now;
 if(!byte) {
  unsigned n=used;used=0;
  if(discard){discard=0;return;}
  n=decode(n);if(n)received(n);return;
 }
 if(discard)return;
 if(used>=sizeof(frame)){used=0;discard=1;return;}
 frame[used++]=(uint8_t)byte;
}
void dh_recovery_loop(const dh_directory *directory,int valid) {
 update_directory=*directory;directory_valid=valid!=0;
 dh_uart_initialize();active=1;
 for(;;)dh_recovery_poll();
}
