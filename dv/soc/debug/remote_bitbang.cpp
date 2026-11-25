// Production TAP pin driver. No DMI or architectural-state backdoor.
#include "VSocExternalClockTest.h"
#include "verilated.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <poll.h>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <memory>
#include <string>
#include <algorithm>
#include <vector>
#include <sstream>
static uint64_t nextSquareEdge(uint64_t tick,unsigned period,unsigned high) {
  const auto phase=tick%period;
  return tick+(phase<high?high-phase:period-phase);
}
static uint64_t nextUsbEdge(uint64_t tick) {
  const auto phase=(tick*48)%1000;
  return tick+((phase<500?500-phase:1000-phase)+47)/48;
}
static void verifySchedule() {
  // Independent exhaustive per-nanosecond oracle: check every transition in
  // complete periods for both AON rates against the event-skipping schedule.
  for(unsigned period:{1000U,31250U}) {
    uint64_t nextMain=0,nextAon=0,nextUsb=0;
    bool m=false,a=false,u=false;
    for(uint64_t t=0;t<1000000;t++) {
      if(t==nextMain) {m=(t%125)<62;nextMain=nextSquareEdge(t,125,62);}
      if(t==nextAon) {a=(t%period)<period/2;nextAon=nextSquareEdge(t,period,period/2);}
      if(t==nextUsb) {u=((t*48)%1000)<500;nextUsb=nextUsbEdge(t);}
      if(m!=((t%125)<62) || a!=((t%period)<period/2) || u!=(((t*48)%1000)<500))
        throw std::runtime_error("clock schedule differs from nanosecond oracle");
    }
  }
}
int main(int argc,char** argv) {
  verifySchedule();
  if(argc<2 || argc>5) return 2;
  const bool sleepStart=argc>=3 && std::string(argv[2])=="sleep";
  if(argc>=3 && !sleepStart && std::string(argv[2])!="run") return 2;
  const std::string control=argc>=4?argv[3]:"";
  const unsigned aonPeriod=argc==5 && std::string(argv[4])=="32000"?31250:1000;
  if(argc==5 && std::string(argv[4])!="32000" && std::string(argv[4])!="1000000") return 2;
  auto context=std::make_unique<VerilatedContext>();context->commandArgs(argc,argv);
  auto top=std::make_unique<VSocExternalClockTest>(context.get());
  top->mainClock=0;top->i1_aonClock=0;top->i1_usbClock=0;
  top->coldReset_n=0;top->warmReset_n=1;top->mainServiceReset_n=1;top->mainCoreReset_n=1;
  top->i1_aonServiceReset_n=1;top->i1_usbServiceReset_n=1;
  top->uartRx=1;top->i1_uartRx_0=1;top->i1_uartRx_1=1;
  top->i1_i2cSclIn=1;top->i1_i2cSdaIn=1;top->i1_aonExtraIn=0;
  top->i1_inactive_jtagTck=0;top->i1_inactive_jtagTms=1;top->i1_inactive_jtagTdi=0;
  top->i1_clockControl_reset_n=1;top->i1_clockControl_coreIdle=0;
  top->i1_clockControl_stable=0;top->i1_clockControl_closed=0;top->i1_clockControl_jtagWake=0;
  top->eval();
  uint64_t tick=0,retired=0,applicationAddi=0,stoppedNs=0,wakes=0;
  bool armed=false,stopped=false;
  uint64_t resetEnd=0,forceStopEnd=0,resetPulses=0,mainEdgesDuringReset=0;
  bool resetPending=false;
  bool aonStopped=false;
  uint64_t aonStoppedNs=0,serviceResetPulses=0;
  auto evaluate=[&]() {
    // External-clock test configuration: the source is continuously available.
    // Production startup and oscillator-off wake are covered by PLAN05 tests.
    top->i1_clockControl_coreIdle=top->coreSleeping;
    top->i1_clockControl_closed=stopped;
    top->i1_clockControl_stable=top->i1_clockControl_qualify;
    top->eval();
  };
  std::string lastControl;
  auto advance=[&](unsigned ns) {
    const uint64_t end=tick+ns;
    while(tick<end) {
      // A deliberately interrupted external clock is a reset robustness test,
      // not a legal sleep-entry sequence. Only public clock/reset pins change.
      if(resetPending && !top->mainClock) {
        resetPending=false;forceStopEnd=tick+10000000;resetEnd=tick+37;
        top->mainCoreReset_n=0;evaluate();resetPulses++;
      }
      if(resetEnd && tick==resetEnd) {top->mainCoreReset_n=1;evaluate();resetEnd=0;}
      // Stop only on a low clock phase after both public demand outputs fall.
      // Wake solely from the real ungated AON demand, never from host traffic.
      if(armed && !top->mainClock && !top->clockHold && !top->i1_mainDemand) {
        stopped=true;armed=false;
      }
      if(stopped && top->i1_mainDemand) {stopped=false;wakes++;}
      const bool main=!stopped && tick>=forceStopEnd && (tick%125)<62,aon=!aonStopped && (tick%aonPeriod)<aonPeriod/2,usb=((tick*48)%1000)<500;
      if(main!=bool(top->mainClock)||aon!=bool(top->i1_aonClock)||usb!=bool(top->i1_usbClock)) {
        bool rise=main&&!top->mainClock;
        top->mainClock=main;top->i1_aonClock=aon;top->i1_usbClock=usb;
        context->time(tick);evaluate();
        if(rise && !top->mainCoreReset_n) mainEdgesDuringReset++;
        if(rise && top->rvfi_valid) {
          retired++;
          if(top->rvfi_pc_rdata==0x20000000 && top->rvfi_insn==0x00128293) applicationAddi++;
        }
      }
      if(context->gotFinish()) throw std::runtime_error("RTL assertion/finish");
      auto next=std::min({end,nextSquareEdge(tick,125,62),nextSquareEdge(tick,aonPeriod,aonPeriod/2),nextUsbEdge(tick)});
      if(resetEnd>tick) next=std::min(next,resetEnd);
      if(forceStopEnd>tick) next=std::min(next,forceStopEnd);
      // These public-control decisions observe the outputs of the edge just
      // evaluated. Preserve their original next-nanosecond scheduling exactly.
      if((resetPending && !top->mainClock) || (stopped && top->i1_mainDemand) ||
         (armed && !top->mainClock && !top->clockHold && !top->i1_mainDemand)) next=std::min(next,tick+1);
      if(stopped) stoppedNs+=next-tick;
      if(aonStopped) aonStoppedNs+=next-tick;
      tick=next;
    }
  };
  auto stopAon=[&]() {while(top->i1_aonClock) advance(1);aonStopped=true;};
  auto controls=[&]() {
    if(control.empty()) return;
    std::ifstream f(control);std::string line;std::getline(f,line);
    if(line.empty() || line==lastControl) return;
    lastControl=line;
    // Sequence prefix makes repeated external commands explicit and idempotent.
    auto split=line.find(' ');const auto action=split==std::string::npos?line:line.substr(split+1);
    if(action=="perf-reset-stopped") resetPending=true;
    else if(action=="aon-stop") stopAon();
    else if(action=="aon-run") {aonStopped=false;advance(20*aonPeriod);}
    else if(action=="pin-reset") {
      top->warmReset_n=0;evaluate();advance(37);
      top->warmReset_n=1;evaluate();
    }
    else if(action=="aon-reset" || action=="main-service-reset") {
      if(!aonStopped) throw std::runtime_error("service reset test requires stopped AON");
      if(action=="aon-reset") top->i1_aonServiceReset_n=0;else top->mainServiceReset_n=0;
      evaluate();advance(37);
      top->i1_aonServiceReset_n=1;top->mainServiceReset_n=1;evaluate();serviceResetPulses++;
    } else throw std::runtime_error("unknown external pin scenario: "+action);
    std::ofstream done(control+".done");done<<line<<std::endl;
  };
  advance(20000);top->coldReset_n=1;evaluate();advance(700*aonPeriod);
  if(sleepStart) {
    armed=true;advance(100000);
    if(!stopped) throw std::runtime_error("main did not reach a legal stopped-clock state");
  }
  int server=socket(AF_INET,SOCK_STREAM,0);if(server<0) return 3;
  sockaddr_in address{};address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
  if(bind(server,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0 || listen(server,1)<0) return 4;
  socklen_t length=sizeof(address);getsockname(server,reinterpret_cast<sockaddr*>(&address),&length);
  {std::ofstream ready(argv[1]);ready<<ntohs(address.sin_port)<<std::endl;}
  int client=accept(server,nullptr,nullptr);if(client<0)return 5;
  bool quit=false;
  while(!quit) {
    controls();
    pollfd event{client,POLLIN,0};int present=poll(&event,1,1);
    if(present<0) return 6;
    if(!present) {advance(5000);continue;}
    char buf[4096];ssize_t n=read(client,buf,sizeof(buf));if(n<=0)break;
    for(ssize_t i=0;i<n;i++) {
      char c=buf[i];
      if(c>='0'&&c<='7') {
        unsigned b=c-'0';top->i1_inactive_jtagTck=(b>>2)&1;
        top->i1_inactive_jtagTms=(b>>1)&1;top->i1_inactive_jtagTdi=b&1;
        evaluate();advance(5000);
      } else if(c=='R') {
        char bit=top->i1_inactive_jtagTdo?'1':'0';if(write(client,&bit,1)!=1)return 7;
      } else if(c=='Q') {quit=true;break;}
      else if(c>='r' && c<='u') {
        // No TRST pad. SRST is the real external warm-reset input; TAP resets by TMS.
        unsigned b=c-'r';top->warmReset_n=!(b&1);evaluate();advance(5000);
      } else if(c!='B' && c!='b') {std::cerr<<"unknown remote-bitbang byte "<<int(c)<<std::endl;return 8;}
    }
  }
  std::cout<<"remote_bitbang: simulated_ns="<<tick<<" perf_retired="<<retired
    <<" application_addi="<<applicationAddi<<" stopped_ns="<<stoppedNs<<" wakes="<<wakes
    <<" reset_pulses="<<resetPulses<<" main_edges_during_reset="<<mainEdgesDuringReset
    <<" aon_stopped_ns="<<aonStoppedNs<<" service_reset_pulses="<<serviceResetPulses
    <<" reset_halt_observed="<<unsigned(top->resetHaltObserved)<<std::endl;
  if(sleepStart && (!stoppedNs || wakes!=1)) throw std::runtime_error("missing demand-driven main wake");
  top->final();close(client);close(server);return 0;
}
