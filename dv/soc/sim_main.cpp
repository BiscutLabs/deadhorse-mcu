#include "VDeadhorseSoc.h"
#include "verilated.h"
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

// Only public clocks, resets, UART pins and RVFI. All memory/bus service is RTL.
int main(int argc, char **argv) {
  if(argc>2 || (argc==2 && std::string(argv[1])!="flight")) return 2;
  const unsigned deadline=argc==2 ? 50000000 : 50000; // Existing fixture budgets.
  std::ofstream cycles;
  if(const char *path=std::getenv("DEADHORSE_CYCLE_TRACE")) { cycles.open(path); if(!cycles) return 2; }
  std::ofstream bus;
  if(const char *path=std::getenv("DEADHORSE_BUS_TRACE")) { bus.open(path); if(!bus) return 2; }
  VerilatedContext context;
  VDeadhorseSoc dut(&context);
  dut.mainClock=0; dut.uartRx=1;
  dut.coldReset_n=1; dut.warmReset_n=1; dut.mainServiceReset_n=1; dut.mainCoreReset_n=1;
  dut.eval(); dut.coldReset_n=0; dut.eval();
  for(unsigned cycle=0; cycle<deadline; ++cycle) {
    dut.mainClock=0; dut.coldReset_n=cycle>=5; dut.eval();
    if(bus.is_open()) bus<<cycle<<' '<<unsigned(dut.memoryTrace_iReq)<<' '
      <<unsigned(dut.memoryTrace_iGnt)<<' '<<dut.memoryTrace_iAddr<<' '
      <<unsigned(dut.memoryTrace_iValid)<<' '<<unsigned(dut.memoryTrace_dReq)<<' '
      <<unsigned(dut.memoryTrace_dGnt)<<'\n';
    dut.mainClock=1; dut.eval(); context.timeInc(1);
    if(dut.rvfi_valid) {
      if(cycles.is_open()) cycles<<dut.rvfi_order<<' '<<cycle<<'\n';
      std::cout<<"{\"order\":"<<dut.rvfi_order;
#define FIELD(name) std::cout<<",\"" #name "\":"<<uint64_t(dut.rvfi_##name)
      FIELD(insn); FIELD(trap); FIELD(halt); FIELD(intr); FIELD(mode); FIELD(ixl);
      FIELD(rs1_addr); FIELD(rs2_addr); FIELD(rs1_rdata); FIELD(rs2_rdata);
      FIELD(rd_addr); FIELD(rd_wdata); FIELD(pc_rdata); FIELD(pc_wdata);
      FIELD(mem_addr); FIELD(mem_rmask); FIELD(mem_wmask); FIELD(mem_rdata); FIELD(mem_wdata);
      FIELD(frs_en); FIELD(frs1_addr); FIELD(frs2_addr); FIELD(frs3_addr);
      FIELD(frs1_rdata); FIELD(frs2_rdata); FIELD(frs3_rdata);
      FIELD(frd_wen); FIELD(frd_addr); FIELD(frd_wdata); FIELD(ext_fcsr); FIELD(ext_fs);
#undef FIELD
      std::cout<<",\"fregs\":[";
      for(int n=0;n<32;++n) { if(n) std::cout<<','; std::cout<<dut.rvfi_ext_fregs[n]; }
      std::cout<<"]}\n";
      if(dut.rvfi_trap) { std::cerr<<"Unexpected architectural trap\n"; return 3; }
      if(dut.rvfi_mem_wmask && dut.rvfi_mem_addr==0x100000) return dut.rvfi_mem_wdata==0x5555 ? 0 : 3;
    }
  }
  std::cerr<<"retirement deadline exceeded\n"; return 2;
}
