package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class ControllerSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def check(d: IbexController, corrupt: Boolean): Unit = {
    def defaults(): Unit = {
      d.illegal_insn_i.poke(false.B); d.ecall_insn_i.poke(false.B); d.mret_insn_i.poke(false.B)
      d.dret_insn_i.poke(false.B); d.wfi_insn_i.poke(false.B); d.ebrk_insn_i.poke(false.B)
      d.csr_pipe_flush_i.poke(false.B); d.instr_valid_i.poke(false.B); d.instr_i.poke(0.U)
      d.instr_compressed_i.poke(0.U); d.instr_is_compressed_i.poke(false.B); d.instr_bp_taken_i.poke(false.B)
      d.instr_fetch_err_i.poke(false.B); d.instr_fetch_err_plus2_i.poke(false.B); d.pc_id_i.poke(0x1020.U)
      d.instr_exec_i.poke(true.B); d.lsu_addr_last_i.poke(0x2345.U)
      d.load_err_i.poke(false.B); d.store_err_i.poke(false.B); d.mem_resp_intg_err_i.poke(false.B)
      d.branch_set_i.poke(false.B); d.branch_not_set_i.poke(false.B); d.jump_set_i.poke(false.B)
      d.csr_mstatus_mie_i.poke(true.B); d.irq_pending_i.poke(false.B); d.irqs_i.poke(0.U)
      d.irq_nm_ext_i.poke(false.B); d.debug_req_i.poke(false.B); d.debug_single_step_i.poke(false.B)
      d.debug_ebreakm_i.poke(false.B); d.debug_ebreaku_i.poke(false.B); d.trigger_match_i.poke(false.B)
      d.priv_mode_i.poke(3.U); d.stall_id_i.poke(false.B); d.stall_wb_i.poke(false.B); d.ready_wb_i.poke(true.B)
    }
    def boot(): Unit = {
      defaults(); d.rst_ni.poke(false.B); d.clk_i.step()
      d.instr_req_o.expect(false.B); d.pc_set_o.expect(true.B); d.pc_mux_o.expect(0.U)
      d.rst_ni.poke(true.B); d.clk_i.step()
      d.instr_req_o.expect(true.B); d.pc_set_o.expect(true.B)
      d.clk_i.step(); d.pc_set_o.expect(false.B); d.clk_i.step(); d.controller_run_o.expect(true.B)
    }
    def cause(expected: Int): Unit = {
      val observed=d.exc_cause_o.peek().litValue ^ (if(corrupt) BigInt(1) else BigInt(0))
      assert(observed==expected,"CONTROLLER_CAUSE_MISMATCH")
    }
    // Architectural interrupt priority: NMI, lowest-index fast, external,
    // software, timer. The model supplies requests, then checks entry effects.
    for((requests,nmi,expected) <- Seq((1<<16,false,39),(1<<17,false,35),(1<<15,false,43),
      ((1<<15)|(1<<17)|(1<<16),false,43),(1|(1<<14)|(1<<15),false,48),
      ((1<<3)|(1<<9),false,51),(0,true,63))) {
      boot(); d.irq_pending_i.poke(true.B); d.irqs_i.poke(requests.U); d.irq_nm_ext_i.poke(nmi.B)
      d.instr_valid_i.poke(true.B); d.stall_id_i.poke(true.B)
      for(_ <- 0 until 3) { d.pc_set_o.expect(false.B); d.csr_save_cause_o.expect(false.B); d.clk_i.step() }
      d.instr_valid_i.poke(false.B); d.stall_id_i.poke(false.B); d.clk_i.step()
      d.pc_set_o.expect(true.B); d.pc_mux_o.expect(2.U); d.exc_pc_mux_o.expect(1.U)
      d.csr_save_if_o.expect(true.B); d.csr_save_cause_o.expect(true.B); cause(expected)
      d.clk_i.step(); d.nmi_mode_o.expect(nmi.B)
    }
    // Debug takes priority over a regular IRQ once the current instruction is
    // gone. DRET restores normal execution; WFI then sleeps until a wake event.
    boot(); d.irq_pending_i.poke(true.B); d.irqs_i.poke((1<<15).U); d.debug_req_i.poke(true.B)
    d.clk_i.step(); d.debug_mode_entering_o.expect(true.B); d.exc_pc_mux_o.expect(2.U)
    d.debug_csr_save_o.expect(true.B); d.debug_cause_o.expect(3.U)
    d.clk_i.step(); d.debug_mode_o.expect(true.B)
    d.debug_req_i.poke(false.B); d.irq_pending_i.poke(false.B)
    d.instr_valid_i.poke(true.B); d.dret_insn_i.poke(true.B); d.clk_i.step()
    d.csr_restore_dret_id_o.expect(true.B); d.pc_mux_o.expect(4.U); d.pc_set_o.expect(true.B)
    d.clk_i.step(); d.debug_mode_o.expect(false.B)
    d.dret_insn_i.poke(false.B); d.wfi_insn_i.poke(true.B); d.clk_i.step()
    d.flush_id_o.expect(true.B); d.clk_i.step()
    d.wfi_insn_i.poke(false.B); d.instr_valid_i.poke(false.B); d.clk_i.step()
    for(_ <- 0 until 4) { d.ctrl_busy_o.expect(false.B); d.instr_req_o.expect(false.B); d.clk_i.step() }
    d.csr_mstatus_mie_i.poke(false.B); d.irq_pending_i.poke(true.B)
    d.clk_i.step(); d.instr_req_o.expect(true.B); d.clk_i.step(); d.controller_run_o.expect(true.B)
    // Fetch error outranks illegal instruction and records the failing halfword.
    boot(); d.instr_valid_i.poke(true.B); d.instr_fetch_err_i.poke(true.B)
    d.instr_fetch_err_plus2_i.poke(true.B); d.illegal_insn_i.poke(true.B)
    d.clk_i.step(); cause(1); d.csr_mtval_o.expect(0x1022.U)
    d.csr_save_cause_o.expect(true.B); d.flush_id_o.expect(true.B)
    // Compressed illegal instruction stores the original 16-bit encoding.
    boot(); d.instr_valid_i.poke(true.B); d.illegal_insn_i.poke(true.B)
    d.instr_is_compressed_i.poke(true.B); d.instr_compressed_i.poke(0x9c00.U)
    d.clk_i.step(); cause(2); d.csr_mtval_o.expect(0x9c00.U)
  }
  test("controller orders interrupts, debug, exceptions, sleep and wake at instruction boundaries") {
    simulateRaw(new IbexController) { d => check(d,false) }
  }
  test("controller checker rejects corrupted exception cause") {
    val error=intercept[TestFailedException] { simulateRaw(new IbexController) { d => check(d,true) } }
    assert(error.getMessage.contains("CONTROLLER_CAUSE_MISMATCH"))
  }
}
