#include "Vibex_top.h"
#include "verilated.h"
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <vector>

// Port-only, one-cycle memory responder. No internal core state is inspected.
int main(int argc, char **argv) {
  if (argc != 2 && argc != 3) return 2;
  const bool flight = argc == 3 && std::string(argv[2]) == "flight";
  if (argc == 3 && !flight) return 2;
  // Optional external cycle observations; architectural RVFI rows stay unchanged.
  std::ofstream cycle_trace;
  if (const char *path = std::getenv("DEADHORSE_CYCLE_TRACE")) {
    cycle_trace.open(path);
    if (!cycle_trace) return 2;
  }
  std::ifstream input(argv[1], std::ios::binary);
  if (!input) return 2;
  std::vector<uint8_t> memory((std::istreambuf_iterator<char>(input)), {});
  const size_t capacity = flight ? 4*1024*1024 : 65536;
  if (memory.size() > capacity) return 2;
  memory.resize(capacity);
  const uint32_t base = flight ? 0x80000000 : 0x80000080;
  auto load = [&](uint32_t address) -> uint32_t {
    address &= ~3u;
    if (address < base || address - base > memory.size() - 4) throw std::runtime_error("memory address");
    uint32_t value = 0;
    for (int n=0; n<4; ++n) value |= uint32_t(memory[address-base+n]) << (8*n);
    return value;
  };
  VerilatedContext context;
  Vibex_top dut(&context);
  dut.clk_i=0; dut.rst_ni=1; dut.scan_rst_ni=1; dut.test_en_i=0;
  dut.boot_addr_i=flight ? 0x80010000 : 0x80000000; dut.hart_id_i=0; dut.ram_cfg_i=0;
  dut.fetch_enable_i=5; dut.debug_req_i=0;
  dut.irq_software_i=0; dut.irq_timer_i=0; dut.irq_external_i=0; dut.irq_fast_i=0; dut.irq_nm_i=0;
  dut.scramble_key_valid_i=0; dut.scramble_nonce_i=0;
  for(int n=0;n<4;++n) dut.scramble_key_i[n]=0;
  dut.instr_err_i=0; dut.data_err_i=0; dut.instr_rdata_intg_i=0; dut.data_rdata_intg_i=0;
  dut.instr_gnt_i=0; dut.data_gnt_i=0; dut.instr_rvalid_i=0; dut.data_rvalid_i=0;
  dut.instr_rdata_i=0; dut.data_rdata_i=0;
  dut.eval(); dut.rst_ni=0; dut.eval();
  bool ip=false, dp=false, software_interrupt=false; uint32_t ir=0, dr=0;
  try {
    // Separate functional fixture budget for the existing full T02 QEMU
    // workload. The smoke/architecture/divide budget remains unchanged.
    const unsigned deadline = flight ? 50000000 : 50000;
    for (unsigned cycle=0; cycle<deadline; ++cycle) {
      dut.clk_i=0; dut.rst_ni=cycle>=5;
      dut.irq_software_i=software_interrupt;
      dut.instr_rvalid_i=ip; dut.instr_rdata_i=ir;
      dut.data_rvalid_i=dp; dut.data_rdata_i=dr;
      dut.instr_gnt_i=0; dut.data_gnt_i=0; dut.eval();
      dut.instr_gnt_i=dut.rst_ni && dut.instr_req_o;
      dut.data_gnt_i=dut.rst_ni && dut.data_req_o; dut.eval();
      bool next_ip=dut.instr_gnt_i, next_dp=dut.data_gnt_i;
      uint32_t next_ir=next_ip ? load(dut.instr_addr_o) : 0, next_dr=0;
      const bool flight_marker = flight && dut.data_we_o &&
          (dut.data_addr_o == 0x10000000 || dut.data_addr_o == 0x10000004);
      if (next_dp && dut.data_addr_o == 0x02000000) {
        // QEMU virt's hart-zero CLINT MSIP, for architectural IRQ injection.
        next_dr=software_interrupt;
        if (dut.data_we_o && (dut.data_be_o & 1)) software_interrupt=dut.data_wdata_o & 1;
      } else if (next_dp && dut.data_addr_o != 0x100000 && !flight_marker) {
        next_dr=load(dut.data_addr_o);
        if (dut.data_we_o) for (int n=0;n<4;++n) if (dut.data_be_o & (1<<n))
          memory[(dut.data_addr_o & ~3u)-base+n]=(dut.data_wdata_o>>(8*n)) & 255;
      }
      dut.clk_i=1; dut.eval(); context.timeInc(1);
      if (dut.rvfi_valid) {
        if (cycle_trace.is_open()) cycle_trace << dut.rvfi_order << ' ' << cycle << '\n';
        std::cout << "{\"order\":" << dut.rvfi_order;
#define FIELD(name) std::cout << ",\"" #name "\":" << uint64_t(dut.rvfi_##name)
        FIELD(insn); FIELD(trap); FIELD(halt); FIELD(intr); FIELD(mode); FIELD(ixl);
        FIELD(rs1_addr); FIELD(rs2_addr); FIELD(rs1_rdata); FIELD(rs2_rdata);
        FIELD(rd_addr); FIELD(rd_wdata); FIELD(pc_rdata); FIELD(pc_wdata);
        FIELD(mem_addr); FIELD(mem_rmask); FIELD(mem_wmask); FIELD(mem_rdata); FIELD(mem_wdata);
#ifdef DEADHORSE_F
        FIELD(frs_en); FIELD(frs1_addr); FIELD(frs2_addr); FIELD(frs3_addr);
        FIELD(frs1_rdata); FIELD(frs2_rdata); FIELD(frs3_rdata);
        FIELD(frd_wen); FIELD(frd_addr); FIELD(frd_wdata); FIELD(ext_fcsr); FIELD(ext_fs);
        std::cout << ",\"fregs\":[";
        for (int n=0;n<32;++n) { if(n) std::cout << ','; std::cout << dut.rvfi_ext_fregs[n]; }
        std::cout << ']';
#endif
#undef FIELD
        std::cout << "}\n";
        if (dut.rvfi_mem_wmask && dut.rvfi_mem_addr == 0x100000) {
          if (dut.rvfi_mem_wdata != 0x5555) return 3;
          return 0;
        }
      }
      ip=next_ip; dp=next_dp; ir=next_ir; dr=next_dr;
    }
  } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 2; }
  std::cerr << "retirement deadline exceeded\n";
  return 2;
}
