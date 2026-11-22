#include "VDeadhorseSoc.h"
#include "verilated.h"
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <vector>
#include <stdexcept>
// Actual public pins only: ROM initialization, recovery I2C and retired RVFI.
int main(int argc,char**argv) {
 try {
  if(argc!=5)return 2;
  unsigned mhz=std::stoul(argv[1]);if(mhz!=8 && mhz!=9)return 2;
  std::ifstream image(argv[2]);std::vector<uint32_t> words;uint32_t w;
  while(image>>std::hex>>w)words.push_back(w);
  if(words.size()<5 || words[0] || words[1] || words[2] || words[3])throw std::runtime_error("missing lite image");
  std::ofstream trace(argv[3]),cycles(argv[4]);if(!trace||!cycles)return 2;
  VerilatedContext context;VDeadhorseSoc d(&context);
  bool hostLow=false,finished=false,released=false;uint64_t ticks=0,mainCycles=0,retirements=0;
  d.mainClock=0;d.i1_aonClock=0;d.i1_usbClock=0;
  d.coldReset_n=0;d.warmReset_n=0;d.mainCoreReset_n=0;d.mainServiceReset_n=0;
  d.i1_aonServiceReset_n=0;d.i1_usbServiceReset_n=0;
  d.uartRx=1;d.i1_uartRx_0=1;d.i1_uartRx_1=1;
  d.i1_i2cSclIn=1;d.i1_i2cSdaIn=1;d.i1_recoveryScl=1;d.i1_recoverySda=1;
  d.i1_liteHalted=1;d.eval();
  auto tick=[&]() {
   // 288 MHz event quantum: exact 8/9 MHz main, 48 MHz USB and 1 MHz AON.
   bool mainRise=false;
   ++ticks;
   if(ticks%(144/mhz)==0){d.mainClock=!d.mainClock;mainRise=d.mainClock;}
   if(ticks%3==0)d.i1_usbClock=!d.i1_usbClock;
   if(ticks%144==0)d.i1_aonClock=!d.i1_aonClock;
   d.i1_recoverySda=!hostLow && !d.i1_recoverySdaLow;d.eval();context.timeInc(1);
   d.i1_recoverySda=!hostLow && !d.i1_recoverySdaLow;d.eval();
   if(mainRise){
    ++mainCycles;
    if(d.rvfi_valid){
     if(!released)throw std::runtime_error("performance core retired before real lite release");
     ++retirements;cycles<<d.rvfi_order<<' '<<mainCycles<<'\n';
     trace<<"{\"order\":"<<d.rvfi_order;
#define FIELD(n) trace<<",\"" #n "\":"<<uint64_t(d.rvfi_##n)
     FIELD(insn);FIELD(trap);FIELD(halt);FIELD(intr);FIELD(mode);FIELD(ixl);
     FIELD(rs1_addr);FIELD(rs2_addr);FIELD(rs1_rdata);FIELD(rs2_rdata);
     FIELD(rd_addr);FIELD(rd_wdata);FIELD(pc_rdata);FIELD(pc_wdata);
     FIELD(mem_addr);FIELD(mem_rmask);FIELD(mem_wmask);FIELD(mem_rdata);FIELD(mem_wdata);
     FIELD(frs_en);FIELD(frd_wen);FIELD(frd_addr);FIELD(frd_wdata);FIELD(ext_fs);
#undef FIELD
     trace<<"}\n";
     if(d.rvfi_trap || d.rvfi_intr)throw std::runtime_error("unexpected trap/interrupt");
     if(d.rvfi_mem_wmask && d.rvfi_mem_addr==0x40012000 && d.rvfi_mem_wdata>2){
      if(d.rvfi_mem_wdata!=0x5555)throw std::runtime_error("failure termination marker");
      finished=true;
     }
    }
   }
  };
  auto aon=[&](unsigned n){for(unsigned i=0;i<n*288;++i)tick();};
  aon(5);d.coldReset_n=1;d.warmReset_n=1;d.mainCoreReset_n=1;d.mainServiceReset_n=1;
  d.i1_aonServiceReset_n=1;d.i1_usbServiceReset_n=1;aon(30);
  if(d.coreReady || retirements)throw std::runtime_error("initial boot hold missing");
  auto line=[&](bool scl,bool low){hostLow=low;d.i1_recoveryScl=scl;aon(5);};
  auto send=[&](unsigned v){
   for(int bit=7;bit>=0;--bit){bool low=!(v&(1u<<bit));line(false,low);line(true,low);line(false,low);}
   line(false,false);line(true,false);if(d.i1_recoverySda)throw std::runtime_error("loader NACK");line(false,false);
  };
  auto command=[&](unsigned op,std::vector<uint32_t> data){
   line(true,false);line(true,true);line(false,true);send(0x6a);send(op);
   for(uint32_t v:data)for(int i=0;i<4;++i)send((v>>(8*i))&255);
   line(false,true);line(true,true);line(true,false);aon(8);
  };
  uint32_t crc=~0u;for(uint32_t v:words)for(int i=0;i<4;++i){crc^=(v>>(8*i))&255;for(int b=0;b<8;++b)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}
  command(1,{uint32_t(words.size()*4),16,~crc,0x10000,16,0,0,0x2025});
  for(unsigned i=0;i<words.size();++i)command(2,{4*i,words[i]});command(3,{});
  if(!d.i1_loaderProgrammed || d.coreReady || retirements)throw std::runtime_error("programmed/held contract failed");
  // The allow flag only checks observations; it does not drive the design.
  released=true;command(6,{});if(!d.i1_loaderLocked)throw std::runtime_error("loader lock missing");
  while(!finished && mainCycles<50000000)tick();
  if(!finished)throw std::runtime_error("existing 50M-cycle measurement deadline");
  std::cout<<"PASS real loader/lite release, no traps; retirements="<<retirements<<" main_cycles="<<mainCycles<<'\n';
  return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
