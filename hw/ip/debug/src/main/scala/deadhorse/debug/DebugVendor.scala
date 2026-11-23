package deadhorse.debug

import chisel3._
import chisel3.util._
import java.nio.file.Paths

/** Sources are verified/materialized by hw/vendor/riscv_dbg/prepare.py. */
class DebugModule extends BlackBox(Map("NrHarts"->2,"BusWidth"->32,
    "DmBaseAddress"->0x10000,"MaxRegisterAccessWidth"->32,"HartResetExtension"->1)) with HasBlackBoxPath {
  override def desiredName="dm_top"
  val io=IO(new Bundle {
    val clk_i=Input(Clock());val rst_ni=Input(Bool());val testmode_i=Input(Bool())
    val next_dm_addr_i=Input(UInt(32.W));val hart_reset_i=Input(UInt(2.W))
    val command_hart_o=Output(UInt(20.W));val command_busy_o=Output(Bool())
    val ndmreset_o=Output(Bool());val ndmreset_ack_i=Input(Bool());val dmactive_o=Output(Bool())
    val debug_req_o=Output(UInt(2.W));val unavailable_i=Input(UInt(2.W));val hartinfo_i=Input(UInt(64.W))
    val slave_req_i=Input(Bool());val slave_we_i=Input(Bool());val slave_addr_i=Input(UInt(32.W))
    val slave_be_i=Input(UInt(4.W));val slave_wdata_i=Input(UInt(32.W));val slave_rdata_o=Output(UInt(32.W))
    val master_req_o=Output(Bool());val master_add_o=Output(UInt(32.W));val master_we_o=Output(Bool())
    val master_wdata_o=Output(UInt(32.W));val master_be_o=Output(UInt(4.W));val master_gnt_i=Input(Bool())
    val master_r_valid_i=Input(Bool());val master_r_err_i=Input(Bool());val master_r_other_err_i=Input(Bool())
    val master_r_rdata_i=Input(UInt(32.W))
    val dmi_rst_ni=Input(Bool());val dmi_req_valid_i=Input(Bool());val dmi_req_ready_o=Output(Bool())
    val dmi_req_i=Input(UInt(41.W));val dmi_resp_valid_o=Output(Bool());val dmi_resp_ready_i=Input(Bool())
    val dmi_resp_o=Output(UInt(34.W))
  })
  for(file<-Seq("riscv-dbg/src/dm_pkg.sv","common_cells/src/fifo_v3.sv",
      "riscv-dbg/debug_rom/debug_rom.sv","riscv-dbg/debug_rom/debug_rom_one_scratch.sv") ++
      Seq("dm_csrs","dm_mem","dm_sba","dm_top").map(n=>s"riscv-dbg/src/$n.sv"))
    addPath(Paths.get("build/vendor/riscv_dbg",file).toAbsolutePath.toString)
}
class DebugTap extends BlackBox with HasBlackBoxPath {
  override def desiredName="dmi_jtag"
  val io=IO(new Bundle {
    val clk_i=Input(Clock());val rst_ni=Input(Bool());val testmode_i=Input(Bool())
    val dmi_rst_no=Output(Bool());val dmi_req_o=Output(UInt(41.W));val dmi_req_valid_o=Output(Bool())
    val dmi_req_ready_i=Input(Bool());val dmi_resp_i=Input(UInt(34.W));val dmi_resp_ready_o=Output(Bool())
    val dmi_resp_valid_i=Input(Bool());val tck_i=Input(Clock());val tms_i=Input(Bool());val trst_ni=Input(Bool())
    val td_i=Input(Bool());val td_o=Output(Bool());val tdo_oe_o=Output(Bool())
  })
  for(file<-Seq("riscv-dbg/src/dm_pkg.sv","tech_cells_generic/src/rtl/tc_clk.sv",
      "riscv-dbg/src/dmi_jtag_tap.sv","riscv-dbg/src/dmi_jtag.sv"))
    addPath(Paths.get("build/vendor/riscv_dbg",file).toAbsolutePath.toString)
}
