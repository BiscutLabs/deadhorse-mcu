// SPDX-License-Identifier: Apache-2.0
// Independent bus/radio oracle around the unchanged production LiteHart.
#ifdef WATCHER_ROUTED
#include "VWatcherTimingFixture.h"
using Dut = VWatcherTimingFixture;
#else
#include "VLiteHart.h"
using Dut = VLiteHart;
#endif
#include "verilated.h"
#include <array>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static void require(bool b, const char *s) { if (!b) throw std::runtime_error(s); }
static std::array<uint8_t,8> radio(unsigned kind) {
  std::array<uint8_t,8> p{0x48,0x44,1,7,0x12,0x34,0,0};
  if (kind==0) p[0]^=1;
  uint16_t c=0xffff;
  for (unsigned i=0;i<6;i++) {
    c^=uint16_t(p[i])<<8;
    for (unsigned b=0;b<8;b++) c=(c&0x8000)?(c<<1)^0x1021:c<<1;
  }
  p[6]=c>>8;p[7]=c;
  if (kind==1) p[7]^=1;
  return p;
}
struct Model {
  Dut d;
  std::array<uint8_t,2048> ram{};
  std::array<uint8_t,8> packet{};
  std::deque<uint8_t> tx,rx;
  uint32_t output=0,oe=0,enabled=0,pending=0,control=0,divider=0,length=0,mux=0;
  uint32_t mailbox=0,mailCount=0,minSp=0x30000800;
  uint64_t cycles=0,retired=0,due=0,lastMail=0;
  uint32_t response=0;
  unsigned bits=0,half=0,halfTicks=0,shift=0;
  bool busy=false,completion=false,reply=false,stackInitialized=false;
  unsigned latency;
  explicit Model(const char *path,unsigned delay):latency(delay) {
    std::ifstream f(path,std::ios::binary);
    require(bool(f),"missing binary");
    f.read(reinterpret_cast<char*>(ram.data()),1024);
    d.clk=0;d.reset_n=0;d.entry=0x30000000;d.start=0;d.irq=0;
    for(int i=0;i<4;i++) tick();
    d.reset_n=1;for(int i=0;i<5;i++) tick();d.start=1;tick();d.start=0;
  }
  uint32_t access(uint32_t a,bool write,uint32_t data,unsigned be) {
    require(d.bus_bits_origin==0,"wrong origin");
    if(a>=0x30000000 && a<0x30000800) {
      unsigned off=a-0x30000000;uint32_t value=0;
      for(unsigned i=0;i<4;i++) {
        if(write && (be&(1<<i))) {
          require(off>=1024,"program self-write");ram[off+i]=data>>(8*i);
        }
        value|=uint32_t(ram[off+i])<<(8*i);
      }
      return value;
    }
    require(be==15,"partial peripheral access");
    if(a>=0x40020000 && a<0x40020020) {
      switch(a-0x40020000) {
        case 0: if(write) control=data;return control;
        case 4: require(!write,"status write");return busy;
        case 8: require(write && !busy && tx.size()<8,"TX overflow");tx.push_back(data);return 0;
        case 12: {require(!write && !rx.empty(),"RX underflow");auto v=rx.front();rx.pop_front();return v;}
        case 16: if(write) divider=data;return divider;
        case 20: if(write) length=data;return length;
        case 24:
          require(write && data==1 && control==1 && divider==1 && length==8 &&
                  tx.size()==8 && rx.empty() && !busy,"bad SPI start");
          busy=true;bits=half=halfTicks=shift=0;completion=false;return 0;
        case 28: require(write && data==1,"bad done clear");completion=false;return 0;
      }
    }
    if(a>=0x40020100 && a<0x40020124) {
      switch(a-0x40020100) {
        case 0:return 0;
        case 4:if(write)output=data;return output;
        case 8:if(write)oe=data;return oe;
        case 12:require(!write,"event write");return pending;
        case 16:if(write)enabled=data;return enabled;
        case 20:require(write,"clear read");pending&=~data;return 0;
        case 32:require(write && !oe && !control && !enabled && data==15,"unsafe startup mux");mux=data;return 0;
      }
    }
    if(a==0x4000100c) {require(!write,"mail status write");return 5;}
    if(a==0x40001000) {require(write,"mail data read");mailbox=data;return 0;}
    if(a==0x40001004) {require(write && data==1,"mail command");mailCount++;lastMail=cycles;return 0;}
    throw std::runtime_error("unexpected/main-domain access "+std::to_string(a));
  }
  void tick() {
    d.clk=0;d.bus_gnt=0;d.bus_rvalid=reply && due==cycles;
    d.bus_rdata=response;d.bus_err=0;d.irq=(pending&enabled)!=0;d.eval();
    if(d.bus_rvalid) reply=false;
    if(d.bus_req) {
      require(!reply,"overlapping transaction");d.bus_gnt=1;
      response=access(d.bus_bits_addr,d.bus_bits_we,d.bus_bits_wdata,d.bus_bits_be);
      reply=true;due=cycles+latency;
    }
    d.eval();d.clk=1;d.eval();cycles++;
    if(d.trace_valid) {
      require(!d.trace_trap,"unexpected firmware trap");retired++;
      if(d.trace_writeRegister && d.trace_rd==2) {
        // AUIPC/ADDI may transiently hold the upper address before SP init.
        if(d.trace_data==0x30000800)stackInitialized=true;
        if(!stackInitialized)return;
        require(d.trace_data>=0x30000400 && d.trace_data<=0x30000800,"stack out of RAM");
        if(d.trace_data<minSp)minSp=d.trace_data;
      }
    }
    if(busy && ++halfTicks==divider) {
      halfTicks=0;half^=1;
      if(half) shift=(shift<<1)|((packet[bits/8]>>(7-bits%8))&1);
      else {
        bits++;
        if(bits%8==0) {require(tx.front()==0,"unexpected radio MOSI");tx.pop_front();rx.push_back(shift);shift=0;}
        if(bits==64) {busy=false;completion=true;}
      }
    }
  }
  void sleep() {
    uint64_t begin=cycles;
    while(!d.sleeping) {tick();require(cycles-begin<20000,"watcher never sleeps");}
  }
  void run(unsigned kind) {
    sleep();require(stackInitialized,"SP never initialized");
    require(!busy && tx.empty() && rx.empty(),"undrained SPI");
    require(mux==15 && output==(1u<<5) && oe==(1u<<5) && enabled==(1u<<4),"radio power/IRQ contract");
    packet=radio(kind);unsigned before=mailCount;uint64_t begin=cycles,insns=retired;
    pending|=1u<<4;do{tick();require(cycles-begin<20000,"wake lost");}while(d.sleeping);
    sleep();
    require(mailCount==before+(kind==2),"invalid packet accepted or valid packet lost");
    if(kind==2) {
      require(mailbox==0x57071234,"mail payload mismatch");
      std::cout<<"PUBLISH "<<latency<<" "<<lastMail-begin<<"\n";
    }
    require(!pending && !completion && !busy && tx.empty() && rx.empty(),"events not drained");
    std::cout<<"CASE "<<kind<<" "<<latency<<" "<<cycles-begin<<" "<<retired-insns<<"\n";
  }
};
int main(int argc,char **argv) {
  try {
    require(argc==2,"binary argument required");
    for(unsigned latency:{1u,2u,4u}) {
      Model m(argv[1],latency);
      for(unsigned kind:{0u,1u,2u,2u})m.run(kind);
      std::cout<<"STACK "<<latency<<" "<<0x30000800-m.minSp<<"\n";
    }
  } catch(const std::exception &e) {std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}
}
