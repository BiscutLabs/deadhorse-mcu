// SPDX-License-Identifier: Apache-2.0
#include "VSocBootRomProbe.h"
#include "verilated.h"
#include "nor.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <cstdlib>
#include <algorithm>
#include <memory>
int main(int argc,char**argv) {
 std::unique_ptr<Nor> savedFlash;
 try {
  if(argc!=3&&argc!=5)return 2;
  std::ifstream input(argv[1],std::ios::binary);
  if(!input)throw std::runtime_error("flash input missing");
  savedFlash=std::make_unique<Nor>(std::vector<uint8_t>((std::istreambuf_iterator<char>(input)),{}));
  Nor& nor=*savedFlash;
  if(std::getenv("DH_POWER_CUT"))nor.powerCut=std::stoi(std::getenv("DH_POWER_CUT"));
  const std::string scenario=argv[2];
  const bool warm=scenario.rfind("warm-",0)==0;
  const bool failClosed=scenario=="warm-bad-context"||scenario=="warm-bad-context-reset"||scenario=="warm-flash-missing"||scenario=="warm-flash-corrupt";
  const uint32_t failPc=std::getenv("DH_FAIL_PC")?std::stoul(std::getenv("DH_FAIL_PC"),nullptr,0):0;
  if(failClosed&&!failPc)throw std::runtime_error("missing authenticated fail PC");
  const unsigned expectedMarker=std::getenv("DH_EXPECTED_MARKER")?std::stoul(std::getenv("DH_EXPECTED_MARKER"),nullptr,0):0;
  std::vector<uint8_t> expectedPerf,expectedLite,expectedConfig,seenPerf,seenLite,seenConfig;
  std::vector<bool> wrotePerf,wroteLite,wroteConfig;
  std::vector<bool> warmWrotePerf,warmWroteLite;
  if(std::getenv("DH_SELECTED_SLOT")) {
   unsigned slot=std::stoul(std::getenv("DH_SELECTED_SLOT"),nullptr,0);
   auto word=[&](unsigned at){return uint32_t(nor.bytes.at(at))|(uint32_t(nor.bytes.at(at+1))<<8)|(uint32_t(nor.bytes.at(at+2))<<16)|(uint32_t(nor.bytes.at(at+3))<<24);};
   unsigned base=4096+slot*word(8),at=base+256;
   auto segment=[&](unsigned count,std::vector<uint8_t>&expected,std::vector<uint8_t>&seen,std::vector<bool>&written){
    if(at>nor.bytes.size()||count>nor.bytes.size()-at)throw std::runtime_error("peer image range");
    expected.assign(nor.bytes.begin()+at,nor.bytes.begin()+at+count);at+=count;
    seen.resize(count);written.resize(count);
   };
   segment(word(base+16),expectedPerf,seenPerf,wrotePerf);
   segment(word(base+28),expectedLite,seenLite,wroteLite);
   segment(word(base+40),expectedConfig,seenConfig,wroteConfig);
  }
  auto allWritten=[](const auto&expected,const auto&seen,const auto&written){
   return expected==seen&&std::all_of(written.begin(),written.end(),[](bool b){return b;});
  };
  VerilatedContext context;VSocBootRomProbe d(&context);
  d.oscIn=0;d.aonClockIn=0;d.aonClockSelect=0;d.porBypass=0;d.externalReset_n=1;
  d.model_lfClock=0;d.model_porReference=0;d.model_supplyMv=0;
  d.pins_uartRx_0=1;d.pins_uartRx_1=1;d.pins_uartRx_2=1;
  d.pins_i2cSclIn=1;d.pins_i2cSdaIn=1;d.pins_aonExtraIn=0;
  d.pins_inactive_gpioIn=scenario=="strap"?2:0;
  d.pins_inactive_jtagTms=1;d.pins_inactive_qspiDqIn=2;d.eval();
  uint64_t ticks=0,mainCycles=0,retirements=0;unsigned boots=0,app=0;
  uint32_t stackMin=0x20004000;bool recovery=false,liteWrite=false,release=false,failedClosed=false;
  unsigned warmPerfWrites=0,warmLiteWrites=0,warmReleases=0;
  bool firstApplication=false,warmGuard=false;
  unsigned checkedApplicationBoot=0;
  size_t warmReadChecked=0;
  bool dmaActiveAtReset=false,warmAsserted=false,warmReleaseAuthorized=false;
  bool secondEpoch=false;
  uint64_t liteCopyBegin=0,worstLiteLoadTicks=0;
  bool liteLoadException=false;
  const bool allowMaxLiteException=std::getenv("DH_MAX_LITE_LOAD_D104")!=nullptr;
  if(allowMaxLiteException&&(scenario!="held"||expectedLite.size()!=1024))
   throw std::runtime_error("D104 exception is only the supported maximum held image");
  std::vector<uint8_t> uartOutput;bool oldTx=true;int txBit=-1;uint64_t txSample=0;unsigned txByte=0;
  auto tick=[&]() {
   bool oldMain=d.status_mainLevel,oldDma=d.dmaActive;
   ticks++;d.oscIn=d.oscEn?!d.oscIn:0;
   if(ticks%1500==0)d.model_lfClock=!d.model_lfClock;
   if(ticks%48==0)d.model_porReference=!d.model_porReference;
   d.eval();
   d.pins_inactive_qspiDqIn=nor.update(d.pins_inactive_qspiCs_n&1,d.pins_inactive_qspiSclk,
     d.pins_inactive_qspiDqOut,d.pins_inactive_qspiDqEnable);
   d.eval();context.timeInc(1);
   // Start at the first offered CPU write, before any bridge grant/retirement.
   if(d.liteWriteOffer&&!liteCopyBegin)liteCopyBegin=ticks;
   if(warm&&!secondEpoch&&warmGuard&&d.warmActive&&!warmAsserted) {
    warmAsserted=true;dmaActiveAtReset=oldDma;
    if(!d.liteHeld||d.liteResetReleased)throw std::runtime_error("warm reset failed to hold lite");
   }
   if(warmAsserted&&!secondEpoch) {
    if(d.liteReleaseCommand) {
     const bool pairedReload=scenario=="warm-reload"||scenario=="warm-lite-reload";
     if(boots!=2||!allWritten(expectedPerf,seenPerf,wrotePerf)||!allWritten(expectedLite,seenLite,wroteLite)||
        (pairedReload&&(!std::all_of(warmWrotePerf.begin(),warmWrotePerf.end(),[](bool b){return b;})||
                        !std::all_of(warmWroteLite.begin(),warmWroteLite.end(),[](bool b){return b;})||
                        warmPerfWrites!=expectedPerf.size()/4||warmLiteWrites!=expectedLite.size()/4)))
      throw std::runtime_error("early warm lite release before paired-image confirmation");
     warmReleaseAuthorized=true;
    }
    if((!d.liteHeld||d.liteStart)&&!warmReleaseAuthorized)
     throw std::runtime_error("warm lite escaped hold without release command");
   }
   if(warmAsserted&&d.warmActive&&d.dmaActive)throw std::runtime_error("DMA survived warm reset");
   if(warm&&!secondEpoch&&boots>=2)while(warmReadChecked<nor.readAddresses.size()) {
    uint32_t address=nor.readAddresses[warmReadChecked++];
    if(address<20480||address>=20480+256+expectedPerf.size()+expectedLite.size())
     throw std::runtime_error("warm ROM reselected/read unrelated flash");
   }
   bool tx=d.pins_uartTx_0;
   if(txBit<0&&oldTx&&!tx){txBit=0;txByte=0;txSample=ticks+1250;}
   if(txBit>=0&&ticks==txSample) {
    if(txBit<8){txByte|=unsigned(tx)<<txBit;txBit++;txSample+=833;}
    else {if(!tx)throw std::runtime_error("UART reply framing");uartOutput.push_back(txByte);txBit=-1;}
   }
   oldTx=tx;
   if(!oldMain&&d.status_mainLevel) {
    mainCycles++;
    if(d.rvfi_valid) {
     retirements++;
     if(d.rvfi_pc_rdata==0x80){boots++;if(boots==2){warmWrotePerf.assign(expectedPerf.size(),false);warmWroteLite.assign(expectedLite.size(),false);warmReadChecked=nor.readAddresses.size();}}
     if(!secondEpoch&&boots>=2&&d.rvfi_pc_rdata==failPc)failedClosed=true;
     if(failedClosed&&d.rvfi_pc_rdata>=0x20000000)throw std::runtime_error("failure path entered application");
     if(d.rvfi_trap)throw std::runtime_error("unexpected core trap PC="+std::to_string(d.rvfi_pc_rdata));
     if(d.rvfi_pc_rdata<0x10000&&d.rvfi_rd_addr==2) {
      uint32_t sp=d.rvfi_rd_wdata;
      if(sp<0x20003e00||sp>0x20004000)throw std::runtime_error("ROM stack escaped allocation");
      stackMin=std::min(stackMin,sp);
     }
     if(d.rvfi_pc_rdata>=0x20000000&&d.rvfi_pc_rdata<0x20003800&&checkedApplicationBoot!=boots) {
      if(expectedPerf.empty()||!allWritten(expectedPerf,seenPerf,wrotePerf)||
         !allWritten(expectedLite,seenLite,wroteLite)||!allWritten(expectedConfig,seenConfig,wroteConfig))
       throw std::runtime_error("application entered before exact image copies");
      if(boots==2&&(scenario=="warm-reload"||scenario=="warm-lite-reload")&&
         (!std::all_of(warmWrotePerf.begin(),warmWrotePerf.end(),[](bool b){return b;})||warmPerfWrites!=expectedPerf.size()/4||!std::all_of(warmWroteLite.begin(),warmWroteLite.end(),[](bool b){return b;})||warmLiteWrites!=expectedLite.size()/4))
       throw std::runtime_error("incomplete warm paired-image reload");
      checkedApplicationBoot=boots;
      firstApplication=true;
     }
     if(d.rvfi_mem_wmask) {
      if(failedClosed)throw std::runtime_error("failure path wrote memory or MMIO");
      uint32_t at=d.rvfi_mem_addr,value=d.rvfi_mem_wdata;
      if(at==0x40010018&&(value==2||value==8||value==10))
       std::cerr<<"UART error cleared mask="<<value<<" ticks="<<ticks<<" PC="<<d.rvfi_pc_rdata<<'\n';
      if(boots>=2&&d.rvfi_pc_rdata<0x10000&&at>=0x20000000&&at<0x20004000&&d.dmaActive)
       throw std::runtime_error("ROM wrote SRAM before DMA drained");
      auto record=[&](uint32_t base,auto&seen,auto&written){
       for(unsigned lane=0;lane<4;lane++)if((d.rvfi_mem_wmask>>lane)&1) {
        uint32_t address=(at&~3u)+lane;
        if(address>=base&&address-base<seen.size()){seen[address-base]=(value>>(8*lane))&255;written[address-base]=true;}
       }
      };
      // Keep the actual image scoreboard through application corruption and
      // warm ROM writes; never infer reload correctness from a nonzero count.
      record(0x20000000,seenPerf,wrotePerf);record(0x30000000,seenLite,wroteLite);
      if(!firstApplication&&d.rvfi_pc_rdata<0x10000) {
       record(0x20003800,seenConfig,wroteConfig);
      }
      if(!secondEpoch&&boots>=2&&d.rvfi_pc_rdata<0x10000) {
       if(at>=0x20000000&&at<0x20003800){warmPerfWrites++;record(0x20000000,seenPerf,warmWrotePerf);}
       if(at>=0x30000000&&at<0x30000400){warmLiteWrites++;record(0x30000000,seenLite,warmWroteLite);}
       if(at==0x40000304||at==0x4000030c)warmReleases++;
      }
      if(at>=0x30000000&&at<0x30000400)liteWrite=true;
      if(at==0x40000314&&value==0x434f4e54) {
       if(!liteCopyBegin)throw std::runtime_error("context committed without lite copy");
       uint64_t elapsed=ticks-liteCopyBegin;
       if(elapsed>24000000) {
        if(!allowMaxLiteException)throw std::runtime_error("lite boot load exceeds250ms at assumed96MHz quantum");
        liteLoadException=true;
       }
       worstLiteLoadTicks=std::max(worstLiteLoadTicks,elapsed);liteCopyBegin=0;
      }
      if(at==0x40000304&&value==0x50455246){
       if(expectedLite.empty()||!allWritten(expectedLite,seenLite,wroteLite))throw std::runtime_error("early lite release");release=true;
      }
      if(at==0x40010000&&value==3)recovery=true;
      if(at==0x40012000){
       app=value;
       if(warm&&value==0xf1) {
        warmGuard=true;
        if(scenario=="warm-flash-missing")for(unsigned n=0;n<96;n++)nor.bytes.at(20480+n)=255;
        if(scenario=="warm-flash-corrupt")nor.bytes.at(20480+256+4)^=1;
        if(scenario=="warm-newer") {
         const char* path=std::getenv("DH_COMPETING_BLOB");if(!path)throw std::runtime_error("missing competing image");
         std::ifstream other(path,std::ios::binary);if(!other)throw std::runtime_error("competing image input");
         std::vector<uint8_t> data((std::istreambuf_iterator<char>(other)),{});
         if(data.size()>16384)throw std::runtime_error("competing image size");
         std::copy(data.begin(),data.end(),nor.bytes.begin()+36864);
        }
       }
      }
      if(at>=0x20003a80&&at<0x20003e00&&d.rvfi_pc_rdata>=0x20000000)
       throw std::runtime_error("application wrote ROM globals");
     }
    }
   }
  };
  for(unsigned n=0;n<15000;n++)tick();d.model_supplyMv=3300;
  auto complete=[&](){return warm?(failedClosed||app==0xe2||app==0xee):bool(app||recovery);};
  const uint64_t bootDeadline=scenario=="warm-dma-stall"?UINT64_C(288000000):UINT64_C(96000000);
  while(ticks<bootDeadline&&!complete())tick();
  if(failedClosed) {
   const auto entry=boots;const auto flashReads=nor.reads;
   // Bounded persistence after the first failure instruction, not an
   // unbounded claim: more than 128 nominal AON edges.
   for(unsigned n=0;n<400000;n++)tick();
   if(boots!=entry||nor.reads!=flashReads)throw std::runtime_error("failure path restarted boot/selection");
  }
  if(boots!=(warm?2u:1u)||!retirements)throw std::runtime_error("boot execution missing");
  if(warm) {
   if(scenario.rfind("warm-dma-",0)==0&&!dmaActiveAtReset)throw std::runtime_error("DMA drain test was vacuous");
   if(!warmAsserted||recovery)throw std::runtime_error("warm reset/recovery contract");
   if(failClosed) {
    unsigned expectedWrites=scenario=="warm-flash-corrupt"?expectedPerf.size()/4:0;
    if(!failedClosed||app!=0xf1||warmPerfWrites!=expectedWrites||warmLiteWrites||warmReleases||!d.liteHeld)throw std::runtime_error("warm invalid context/image did not fail closed");
   }
   else {
    if(app!=0xe2||failedClosed||warmReleases!=1||d.liteHeld)throw std::runtime_error("warm application/watcher/data state");
    if(scenario=="warm-match"&&(warmPerfWrites||warmLiteWrites))throw std::runtime_error("matching SRAM was recopied");
    if((scenario=="warm-reload"||scenario=="warm-lite-reload")&&(!warmPerfWrites||!warmLiteWrites))throw std::runtime_error("corrupt SRAM was not reloaded");
   }
  }
  if(scenario=="normal"&&(!app||!liteWrite||!release||recovery))throw std::runtime_error("normal boot contract");
  if(scenario=="held"&&(!app||!liteWrite||release||recovery))throw std::runtime_error("leave held contract");
  if((scenario=="recovery"||scenario=="strap")&&(!recovery||app||release||liteWrite))throw std::runtime_error("recovery contract");
  if(app!=expectedMarker)throw std::runtime_error("exact application marker mismatch");
  if(scenario=="warm-bad-context-reset") {
   // Ordinary pin is warm: invalid committed context must still fail closed.
   failedClosed=false;app=0;
   d.externalReset_n=0;for(unsigned n=0;n<12000;n++)tick();d.externalReset_n=1;
   uint64_t deadline=ticks+96000000;while(ticks<deadline&&!failedClosed)tick();
   if(boots!=3||!failedClosed||app||recovery||!d.liteHeld)
    throw std::runtime_error("pin warm reset escaped invalid context");
   // Genuine cold reset clears context-ready and permits fresh selection.
   secondEpoch=true;failedClosed=false;firstApplication=false;warmGuard=false;warmAsserted=false;
   checkedApplicationBoot=0;app=0;release=false;liteWrite=false;recovery=false;
   std::fill(wrotePerf.begin(),wrotePerf.end(),false);std::fill(wroteLite.begin(),wroteLite.end(),false);
   std::fill(wroteConfig.begin(),wroteConfig.end(),false);
   d.model_supplyMv=0;for(unsigned n=0;n<12000;n++)tick();d.model_supplyMv=3300;
   deadline=ticks+96000000;while(ticks<deadline&&!app&&!recovery)tick();
   if(boots!=4||app!=0xf1||recovery||!release||!liteWrite||!firstApplication)
    throw std::runtime_error("cold reset failed to recover cold boot");
  }
  if(argc==5) {
   if(!recovery)throw std::runtime_error("UART campaign needs recovery mode");
   std::ifstream requests(argv[3],std::ios::binary);
   if(!requests)throw std::runtime_error("request records missing");
   auto wait=[&](unsigned n){for(unsigned i=0;i<n;i++)tick();};
   wait(24000);
   auto read32=[&](){uint32_t v=0;for(unsigned n=0;n<4;n++){int b=requests.get();if(b<0)throw std::runtime_error("short request header");v|=uint32_t(b)<<(8*n);}return v;};
   unsigned recordIndex=0;
   while(requests.peek()!=EOF) {
    recordIndex++;
    unsigned gap=read32(),length=read32(),expected=read32(),timeout=read32();
    if(length>4096||!timeout)throw std::runtime_error("invalid request record");
    wait(gap);auto initial=uartOutput.size();
    for(unsigned n=0;n<length;n++) {
     int value=requests.get();if(value<0)throw std::runtime_error("short request bytes");
     uint8_t b=value;d.pins_uartRx_0=0;wait(834);
     for(unsigned bit=0;bit<8;bit++){d.pins_uartRx_0=(b>>bit)&1;wait(834);}
     d.pins_uartRx_0=1;wait(834);
    }
    auto frames=[&](){return unsigned(std::count(uartOutput.begin()+initial,uartOutput.end(),uint8_t(0)));};
    uint64_t deadline=ticks+timeout;
    if(expected)while(frames()<expected&&ticks<deadline)tick();
    else while(ticks<deadline)tick();
    if(frames()!=expected||(expected&&ticks>=deadline)||(!expected&&uartOutput.size()!=initial)) {
     std::cerr<<"UART record="<<recordIndex<<" expected="<<expected<<" frames="<<frames()
      <<" ticks="<<ticks<<" PC="<<d.rvfi_pc_rdata<<" NOR reads="<<nor.reads
      <<" erases="<<nor.erases<<" programs="<<nor.programs<<" reply=";
     for(auto b:uartOutput)std::cerr<<std::hex<<unsigned(b)<<',';
     std::cerr<<std::dec<<'\n';
     throw std::runtime_error("UART response count/deadline");
    }
   }
   std::ofstream replies(argv[4],std::ios::binary);replies.write(reinterpret_cast<const char*>(uartOutput.data()),uartOutput.size());
   std::ofstream flashOut(std::string(argv[4])+".flash",std::ios::binary);flashOut.write(reinterpret_cast<const char*>(nor.bytes.data()),nor.bytes.size());
  }
  if(stackMin<0x20003e00)throw std::runtime_error("ROM stack overflow");
  std::cout<<"{\"status\":\"pass\",\"cycles\":"<<mainCycles<<",\"app\":"<<app
    <<",\"stack_bytes\":"<<(0x20004000-stackMin)<<",\"flash_reads\":"<<nor.reads
    <<",\"rom_entries\":"<<boots<<",\"warm_perf_words\":"<<warmPerfWrites
    <<",\"warm_lite_writes\":"<<warmLiteWrites<<",\"warm_releases\":"<<warmReleases
    <<",\"erases\":"<<nor.erases<<",\"programs\":"<<nor.programs
    <<",\"dma_active_at_reset\":"<<dmaActiveAtReset
    <<",\"whole_reset_recovered\":"<<secondEpoch
    <<",\"lite_load_quanta\":"<<worstLiteLoadTicks
    <<",\"lite_load_budget_met\":"<<(worstLiteLoadTicks<=24000000?"true":"false")
    <<",\"lite_load_D104_exception\":"<<(liteLoadException?"true":"false")
    <<",\"last_program_address\":"<<(nor.programAddresses.empty()?0:nor.programAddresses.back())<<"}\n";
 }catch(const std::exception&e){
  if(std::string(e.what())=="POWER_CUT"&&savedFlash&&argc==5) {
   std::ofstream flashOut(std::string(argv[4])+".flash",std::ios::binary);
   flashOut.write(reinterpret_cast<const char*>(savedFlash->bytes.data()),savedFlash->bytes.size());
   std::cout<<"{\"status\":\"power-cut\"}\n";return 3;
  }
  std::cerr<<e.what()<<'\n';return 1;
 }
}
