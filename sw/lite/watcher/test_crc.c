/* SPDX-License-Identifier: Apache-2.0 */
#include "crc16.h"
#include <stdio.h>

static uint32_t reference(uint32_t crc, unsigned byte) {
  crc ^= byte << 8;
  for (unsigned bit=0;bit<8;bit++) {
    unsigned top=crc & 0x8000;
    crc=(crc << 1) & 0xffff;
    if(top)crc^=0x1021;
  }
  return crc;
}
int main(void) {
  unsigned long checked=0;
  for(unsigned c=0;c<65536;c++)for(unsigned b=0;b<256;b++) {
    uint32_t got=crc_byte(c,b);
#ifdef BAD_REMAINDER
    got ^= 1; /* expected failure must be caught by the same oracle */
#endif
    if(got!=reference(c,b)) {
      fprintf(stderr,"CRC_REMAINDER_MISMATCH %u %u\n",c,b);return 1;
    }
    checked++;
  }
  uint32_t crc=0xffff;
  const unsigned char text[]="123456789";
  for(unsigned i=0;i<sizeof(text)-1;i++)crc=crc_byte(crc,text[i]);
  if(crc!=0x29b1)return 2;
  printf("PASS %lu exhaustive state-byte pairs; CCITT-FALSE check 29b1\n",checked);
  return 0;
}
