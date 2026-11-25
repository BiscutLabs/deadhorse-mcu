#include "VPadBootTest.h"
#include "verilated.h"
#include "nor.hpp"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

int main(int argc,char**argv) {
 try {
  if(argc!=5)throw std::runtime_error("request response aon-select por-bypass");
  std::ifstream file(argv[1],std::ios::binary);
  std::vector<uint8_t> request((std::istreambuf_iterator<char>(file)),{}),reply;
  if(request.empty())throw std::runtime_error("empty host request");
  VerilatedContext context;VPadBootTest d(&context);Nor nor(std::vector<uint8_t>(1<<20,255));
  d.clk=0;d.reset_n=0;d.model_lfClock=0;d.model_porReference=0;d.model_supplyMv=0;
  d.inputs=(1<<4)|(7<<6)|(1<<9)|(std::stoi(argv[3])<<1)|(std::stoi(argv[4])<<2);
  d.external_enable=UINT64_C(0x00fe)|(UINT64_C(3)<<16)|(UINT64_C(1)<<20)|(UINT64_C(3)<<34)|(UINT64_C(7)<<37);
  d.external_data=(UINT64_C(1)<<2)|(UINT64_C(3)<<16)|(UINT64_C(1)<<20);
  uint64_t ticks=0,sample=0;int bit=-1;unsigned byte=0;bool previous=true,decode=false;
  auto evaluate=[&](){
   d.eval();
   // Independent flash peer sees only physical serial pins and output enables.
   unsigned value=nor.update((d.observed>>23)&1,(d.observed>>18)&1,(d.observed>>19)&15,(d.drive>>19)&15);
   d.external_data=(d.external_data&~(UINT64_C(1)<<20))|(uint64_t(value&2)<<19);d.eval();
  };
  auto tick=[&]() {
   ++ticks;d.clk=!d.clk;
   if(ticks%1500==0){d.model_lfClock=!d.model_lfClock;d.inputs^=1;}
   if(ticks%48==0)d.model_porReference=!d.model_porReference;
   // Timed foundry pads: service every scheduled event before the next clock edge.
   uint64_t end=context.time()+10417;evaluate();
   while(d.eventsPending() && d.nextTimeSlot()<=end){context.time(d.nextTimeSlot());evaluate();}
   context.time(end);evaluate();
   if(!(d.observed&1))throw std::runtime_error("OSC_EN not high during boot/reset");
   bool tx=(d.observed>>9)&1;
   if(decode) {
    if(bit<0&&previous&&!tx){bit=0;byte=0;sample=ticks+1250;}
    if(bit>=0&&ticks==sample){
     if(bit<8){byte|=unsigned(tx)<<bit;bit++;sample+=834;}
     else {if(!tx)throw std::runtime_error("pad UART stop bit");reply.push_back(byte);bit=-1;}
    }
   }
   previous=tx;
  };
  auto wait=[&](uint64_t n){while(n--)tick();};
  // Reset defaults drive OSC_EN after the first pad propagation interval.
  d.eval();
  while(d.eventsPending()&&d.nextTimeSlot()<=20000){context.time(d.nextTimeSlot());d.eval();}
  context.time(20000);d.eval();
  d.model_supplyMv=3300;wait(100000);d.reset_n=1;
  for(unsigned epoch=0;epoch<2;epoch++) {
   wait(9600000);reply.clear();bit=-1;previous=(d.observed>>9)&1;decode=true;
   if(!previous){std::cerr<<"status="<<unsigned(d.status)<<" oe="<<std::hex<<d.drive<<" pads="<<d.observed<<std::dec<<" ticks="<<ticks<<"\n";throw std::runtime_error("UART did not reach idle");}
   for(uint8_t b:request){
    d.inputs&=~(1<<6);wait(834);
    for(unsigned i=0;i<8;i++){d.inputs=(d.inputs&~(1<<6))|(((b>>i)&1)<<6);wait(834);}
    d.inputs|=1<<6;wait(834);
   }
   uint64_t deadline=ticks+96000000;
   while((reply.empty()||reply.back()!=0)&&ticks<deadline)tick();
   if(reply.empty()||reply.back()!=0)throw std::runtime_error("no UART response through pads");
   std::ofstream output(std::string(argv[2])+std::to_string(epoch),std::ios::binary);
   output.write(reinterpret_cast<const char*>(reply.data()),reply.size());output.close();
   decode=false;
   if(epoch==0){
    d.reset_n=0;
    // Normal mode requires a POR cold reset for a fresh recovery boot. A warm
    // pin reset without a committed bundle correctly fails closed (T41/C4).
    if(!std::stoi(argv[4]))d.model_supplyMv=0;
    wait(100000);d.model_supplyMv=3300;wait(100000);d.reset_n=1;
   }
  }
  std::cout<<"PASS pad ROM recovery and cold-reset reboot ticks="<<ticks<<"\n";
  d.final();return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
