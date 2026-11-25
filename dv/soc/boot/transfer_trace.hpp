// SPDX-License-Identifier: Apache-2.0
// Optional passive T42 observer. Handshakes use PRE-edge values; retirement
// follows the existing boot peer's post-edge RVFI convention.
#include <array>
struct TransferSample {
 bool main,aon;
 std::array<bool,19> flags;
 uint32_t address,cpuAddress;bool write,cpuWrite,flash;
 explicit TransferSample(const VSocBootRomProbe& d):main(d.status_mainLevel),aon(d.transfer_aonClock),
  flags{bool(d.transfer_offer),bool(d.transfer_ask),bool(d.transfer_permit),bool(d.transfer_admit),
   bool(d.transfer_sourceReq),bool(d.transfer_sourceReq&&d.transfer_sourceGrant),bool(d.transfer_sourceReply),
   bool(d.transfer_requestPush),bool(d.transfer_requestPop),bool(d.transfer_targetReq),
   bool(d.transfer_targetReq&&d.transfer_targetGrant),bool(d.transfer_targetReply),bool(d.transfer_ramReq),
   bool(d.transfer_ramReq&&d.transfer_ramGrant),bool(d.transfer_ramReply),bool(d.transfer_responsePush),
   bool(d.transfer_responsePop),bool(d.transfer_cpuReq&&d.transfer_cpuGrant),bool(d.transfer_cpuReply)},
  address(d.transfer_address),cpuAddress(d.transfer_cpuAddress),write(d.transfer_write),
  cpuWrite(d.transfer_cpuWrite),flash(!(d.pins_inactive_qspiCs_n&1)) {}
};
struct TransferTrace {
 std::ofstream file;bool active=false,finished=false;uint64_t edges=0;
 explicit TransferTrace() {if(auto path=std::getenv("DH_TRANSFER_TRACE")) {
  file.open(path);if(!file)throw std::runtime_error("transfer trace open");
  file<<"tick,aon_edges,event,address,write,data,pc\n";
 }}
 void row(uint64_t tick,const char* event,uint32_t address=0,bool write=false,uint32_t data=0,uint32_t pc=0) {
  file<<tick<<','<<edges<<','<<event<<','<<address<<','<<write<<','<<data<<','<<pc<<'\n';
 }
 static unsigned memoryKind(uint32_t insn) {
  // Do not identify loads from mem_rmask alone: unused RVFI fields may carry
  // nonzero values. Decode the retired RV32IMFC instruction first.
  if((insn&3)==3) {
   unsigned op=insn&127;
   return op==3||op==7?1:op==35||op==39?2:0;
  }
  unsigned quadrant=insn&3,funct3=(insn>>13)&7;
  if(quadrant==0||quadrant==2) {
   if(funct3==2||funct3==3)return 1; // LW/FLW or LWSP/FLWSP
   if(funct3==6||funct3==7)return 2; // SW/FSW or SWSP/FSWSP
  }
  return 0;
 }
 void sample(const TransferSample& before,const VSocBootRomProbe& d,uint64_t tick) {
  if(!file.is_open()||finished)return;
  TransferSample after(d);bool mainRise=!before.main&&after.main,aonRise=!before.aon&&after.aon;
  if(aonRise)++edges;
  if(!active&&d.liteWriteOffer) {active=true;row(tick,"begin",0,false,after.flash);}
  if(!active)return;
  const char* names[]={"offer","ask","permit","admit","source_req","source_take","source_reply",
   "request_push","request_pop","target_req","target_take","target_reply","ram_req","ram_take",
   "ram_reply","response_push","response_pop","cpu_take","cpu_reply"};
  for(unsigned n=0;n<19;n++) {
   bool level=n<=4||n==9||n==12;
   bool aon=n==8||(n>=10&&n<=15);
   if(level&&after.flags[n]!=before.flags[n]) {
    std::string event=std::string(names[n])+(after.flags[n]?"_up":"_down");
    row(tick,event.c_str(),after.address,after.write);
   } else if(!level&&(aon?aonRise:mainRise)&&before.flags[n])
    row(tick,names[n],n>=17?before.cpuAddress:before.address,n>=17?before.cpuWrite:before.write);
  }
  if(d.transfer_cpuReq&&(!oldCpuReq||d.transfer_cpuAddress!=oldCpuAddress))
   row(tick,"cpu_offer",d.transfer_cpuAddress,d.transfer_cpuWrite);
  oldCpuReq=d.transfer_cpuReq;oldCpuAddress=d.transfer_cpuAddress;
  if(after.flash!=before.flash)row(tick,after.flash?"flash_on":"flash_off");
  unsigned kind=memoryKind(d.rvfi_insn);
  if(mainRise&&d.rvfi_valid&&!kind)
   row(tick,"instruction",0,false,0,d.rvfi_pc_rdata);
  if(mainRise&&d.rvfi_valid&&kind) {
   if(!(kind==2?d.rvfi_mem_wmask:d.rvfi_mem_rmask))throw std::runtime_error("memory retirement lacks mask");
   row(tick,"retire",d.rvfi_mem_addr,kind==2,
    kind==2?d.rvfi_mem_wdata:d.rvfi_mem_rdata,d.rvfi_pc_rdata);
   if(kind==2&&d.rvfi_mem_addr==0x40000314&&d.rvfi_mem_wdata==0x434f4e54) {
    row(tick,"end");finished=true;file.flush();
   }
  }
 }
 bool oldCpuReq=false;uint32_t oldCpuAddress=0;
};
