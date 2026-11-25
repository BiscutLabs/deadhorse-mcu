// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <cstdint>
#include <vector>
#include <stdexcept>
// Independent serial NOR model: no controller state, registers or RTL internals.
struct Nor {
 std::vector<uint8_t> bytes;
 bool selected=false,oldClock=false,writeEnable=false,ignoreErase=false;
 uint32_t shift=0,address=0;unsigned bits=0,opcode=0,busyPolls=0;
 std::vector<uint8_t> payload;
 uint64_t reads=0,programs=0,erases=0;int powerCut=-1;
 std::vector<uint32_t> programAddresses;
 std::vector<uint32_t> readAddresses;
 explicit Nor(std::vector<uint8_t> image):bytes(std::move(image)){}
 unsigned reply() const {
  if(opcode==5&&bits>=8)return ((busyPolls?1u:0u)|(writeEnable?2u:0u))>>(7-((bits-8)%8))&1;
  if(opcode==3&&bits>=32) {
   uint32_t at=address+(bits-32)/8;
   return at<bytes.size()?(bytes[at]>>(7-((bits-32)%8))&1):1;
  }
  return 1;
 }
 void end() {
  if(opcode==6&&bits==8)writeEnable=true;
  if(opcode==5&&busyPolls)busyPolls--;
  if(opcode==3){reads++;readAddresses.push_back(address);}
  if(opcode==0x20||opcode==2) {
   if(!writeEnable||busyPolls)throw std::runtime_error("NOR write without WREN/ready");
   if(address>=bytes.size())throw std::runtime_error("NOR address out of device");
   writeEnable=false;busyPolls=2;
   if(opcode==0x20) {
    if(bits!=32)throw std::runtime_error("NOR erase framing");
    ++erases;uint32_t base=address&~4095u;
    if(!ignoreErase)for(unsigned n=0;n<4096;n++)bytes.at(base+n)=255;
   } else {
    if(bits<40||bits%8||payload.empty()||payload.size()>256)throw std::runtime_error("NOR program framing");
    ++programs;programAddresses.push_back(address);
    for(unsigned n=0;n<payload.size();n++)bytes.at((address&~255u)|((address+n)&255))&=payload[n];
   }
   if(powerCut>=0&&--powerCut==0)throw std::runtime_error("POWER_CUT");
  }
 }
 unsigned update(bool cs_n,bool sclk,unsigned mosi,unsigned oe) {
  if(cs_n) {
   if(selected)end();selected=false;oldClock=sclk;return 2;
  }
  if(!selected) {selected=true;oldClock=false;bits=0;shift=0;opcode=0;address=0;payload.clear();}
  if(!oldClock&&sclk) {
   if(bits<8||((opcode==3||opcode==2||opcode==0x20)&&bits<32)||opcode==2) {
    if(!(oe&1))throw std::runtime_error("NOR missing MOSI drive");
    shift=(shift<<1)|(mosi&1);
   }
   ++bits;
   if(bits==8)opcode=shift&255;
   if(bits==32&&(opcode==3||opcode==2||opcode==0x20))address=shift&0xffffff;
   if(opcode==2&&bits>32&&bits%8==0)payload.push_back(shift&255);
  }
  oldClock=sclk;
  // Hold the prior data throughout the sampling high phase; set next on low.
  if(!sclk)held=reply();
  return held<<1;
 }
 unsigned held=1;
};
