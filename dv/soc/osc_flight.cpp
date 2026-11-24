#include "VSocOscFlight.h"
#include "verilated.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

// Production pins, analog behavioral-model inputs and passive RVFI only.
int main(int argc,char**argv) {
 try {
  if(argc!=5)return 2;
  bool sleep=std::stoul(argv[1])!=0;
  std::ifstream image(argv[2]);std::vector<uint32_t> words;uint32_t w;
  while(image>>std::hex>>w)words.push_back(w);
  if(words.size()<5 || words[0] || words[1] || words[2] || words[3])
    throw std::runtime_error("missing lite image");
  std::ofstream trace(argv[3]),cycles(argv[4]);if(!trace||!cycles)return 2;
  VerilatedContext context;VSocOscFlight d(&context);
  bool hostLow=false,finished=false,released=false;
  uint64_t ticks=0,mainCycles=0,retirements=0,sourceAge=0;
  d.oscIn=0;d.aonClockIn=0;d.aonClockSelect=0;d.porBypass=0;
  d.externalReset_n=1;d.model_lfClock=0;d.model_porReference=0;d.model_supplyMv=0;
  d.pins_uartRx_0=1;d.pins_uartRx_1=1;d.pins_uartRx_2=1;
  d.pins_i2cSclIn=1;d.pins_i2cSdaIn=1;
  d.pins_recoveryScl=1;d.pins_recoverySda=1;
  d.pins_inactive_jtagTms=1;d.eval();
  auto tick=[&]() {
   // Assumed 96 MHz simulation quantum: OSC_IN48MHz, AON32kHz, POR1MHz.
   bool oldMain=d.status_mainLevel;
   ++ticks;
   if(d.oscEn) {++sourceAge;if(sourceAge>6000)d.oscIn=!d.oscIn;}
   else {sourceAge=0;d.oscIn=0;}
   if(ticks%1500==0)d.model_lfClock=!d.model_lfClock;
   if(ticks%48==0)d.model_porReference=!d.model_porReference;
   d.pins_recoverySda=!hostLow && !d.pins_recoverySdaLow;
   d.eval();context.timeInc(1);
   d.pins_recoverySda=!hostLow && !d.pins_recoverySdaLow;d.eval();
   if(!oldMain && d.status_mainLevel){
    if(released && d.pins_inactive_gpioEnable)throw std::runtime_error("GPIO marker drove a pad");
    ++mainCycles;
    if(d.rvfi_valid){
     if(!released)throw std::runtime_error("performance core retired before lite release");
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
  auto aon=[&](unsigned n){for(uint64_t i=0;i<uint64_t(n)*3000;++i)tick();};
  aon(5);if(!d.oscEn || d.status_aonReleased)throw std::runtime_error("POR power-up contract");
  d.model_supplyMv=3300;aon(620);
  if(!d.status_servicesReleased || d.status_coreReady || retirements)
    throw std::runtime_error("initial boot hold missing");
  auto line=[&](bool scl,bool low){hostLow=low;d.pins_recoveryScl=scl;aon(5);};
  auto send=[&](unsigned v){
   for(int bit=7;bit>=0;--bit){bool low=!(v&(1u<<bit));line(false,low);line(true,low);line(false,low);}
   line(false,false);line(true,false);if(d.pins_recoverySda)throw std::runtime_error("loader NACK");line(false,false);
  };
  auto command=[&](unsigned op,std::vector<uint32_t> data){
   line(true,false);line(true,true);line(false,true);send(0x6a);send(op);
   for(uint32_t v:data)for(int i=0;i<4;++i)send((v>>(8*i))&255);
   line(false,true);line(true,true);line(true,false);aon(8);
  };
  uint32_t crc=~0u;
  for(uint32_t v:words)for(int i=0;i<4;++i){crc^=(v>>(8*i))&255;for(int b=0;b<8;++b)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}
  command(1,{uint32_t(words.size()*4),16,~crc,0x10000,16,0,0,0x2025});
  for(unsigned i=0;i<words.size();++i)command(2,{4*i,words[i]});command(3,{});
  if(d.status_coreReady || retirements)throw std::runtime_error("programmed core not held");
  released=true;command(6,{});
  if(sleep){
   unsigned waited=0;
   while(d.oscEn){aon(1);if(++waited>=20000)throw std::runtime_error("firmware sleep deadline");}
   auto frozen=mainCycles;aon(40);
   if(d.oscEn || d.status_mainLevel || mainCycles!=frozen || !d.status_coreSleeping)
     throw std::runtime_error("deep sleep did not stop main");
   d.pins_uartRx_0=0;waited=0;
   while(!d.oscEn){aon(1);if(++waited>=16)throw std::runtime_error("UART wake lost");}
   aon(10);d.pins_uartRx_0=1;aon(64);
   if(d.status_fault || !d.status_servicesReleased)throw std::runtime_error("wake fault");
  }
  // Existing production measurement cap; no deadline relaxation.
  while(!finished && mainCycles<50000000)tick();
  if(!finished)throw std::runtime_error("existing 50M-cycle measurement deadline");
  if(d.status_fault || !d.oscEn)throw std::runtime_error("final clock fault");
  std::cout<<"PASS real boot and "<<(sleep?"deep wake":"baseline")
    <<"; retirements="<<retirements<<" main_cycles="<<mainCycles<<'\n';
  return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
