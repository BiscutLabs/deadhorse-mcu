package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class IdStageSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def check(d: IbexIdStage, corrupt: Boolean): Unit = {
    def defaults(): Unit = {
      d.instr_valid_i.poke(false.B); d.instr_rdata_i.poke(0x13.U); d.instr_rdata_alu_i.poke(0x13.U)
      d.instr_rdata_c_i.poke(0.U); d.instr_is_compressed_i.poke(false.B); d.instr_bp_taken_i.poke(false.B)
      d.instr_exec_i.poke(true.B); d.branch_decision_i.poke(false.B); d.illegal_c_insn_i.poke(false.B)
      d.instr_fetch_err_i.poke(false.B); d.instr_fetch_err_plus2_i.poke(false.B); d.pc_id_i.poke(0x1000.U)
      d.ex_valid_i.poke(true.B); d.lsu_resp_valid_i.poke(false.B)
      d.imd_val_we_ex_i.poke(0.U); d.imd_val_d_ex_i.poke(0.U)
      d.priv_mode_i.poke(3.U); d.csr_mstatus_tw_i.poke(false.B); d.illegal_csr_insn_i.poke(false.B)
      d.data_ind_timing_i.poke(false.B); d.lsu_req_done_i.poke(false.B)
      d.lsu_addr_incr_req_i.poke(false.B); d.lsu_addr_last_i.poke(0x2000.U)
      d.csr_mstatus_mie_i.poke(true.B); d.irq_pending_i.poke(false.B); d.irqs_i.poke(0.U); d.irq_nm_i.poke(false.B)
      d.lsu_load_err_i.poke(false.B); d.lsu_load_resp_intg_err_i.poke(false.B)
      d.lsu_store_err_i.poke(false.B); d.lsu_store_resp_intg_err_i.poke(false.B)
      d.debug_req_i.poke(false.B); d.debug_single_step_i.poke(false.B)
      d.debug_ebreakm_i.poke(false.B); d.debug_ebreaku_i.poke(false.B); d.trigger_match_i.poke(false.B)
      d.result_ex_i.poke(0x123.U); d.csr_rdata_i.poke(0x456.U)
      d.rf_rdata_a_i.poke(0x102.U); d.rf_rdata_b_i.poke(0x21.U)
      d.rf_waddr_wb_i.poke(0.U); d.rf_wdata_fwd_wb_i.poke(0.U); d.rf_write_wb_i.poke(false.B)
      d.ready_wb_i.poke(true.B); d.outstanding_load_wb_i.poke(false.B); d.outstanding_store_wb_i.poke(false.B)
    }
    def boot(): Unit = {
      defaults(); d.rst_ni.poke(false.B); d.clk_i.step(); d.rst_ni.poke(true.B); d.clk_i.step(3)
    }
    def instruction(word: BigInt): Unit = {
      d.instr_rdata_i.poke(word.U); d.instr_rdata_alu_i.poke(word.U); d.instr_valid_i.poke(true.B)
    }
    def value(port: UInt, expected: BigInt): Unit = {
      val observed=port.peek().litValue ^ (if(corrupt) BigInt(1) else BigInt(0))
      assert(observed==expected,"ID_MODEL_MISMATCH")
    }
    boot(); instruction(0x02110293) // ADDI x5,x2,33
    d.rf_raddr_a_o.expect(2.U); d.rf_waddr_id_o.expect(5.U)
    value(d.alu_operand_a_ex_o,0x102); value(d.alu_operand_b_ex_o,33)
    d.rf_we_id_o.expect(true.B); d.en_wb_o.expect(true.B); value(d.rf_wdata_id_o,0x123)
    d.illegal_csr_insn_i.poke(true.B); d.rf_we_id_o.expect(false.B); d.rf_ren_a_o.expect(false.B)
    // Multiplication remains in the multicycle state until result-valid. This
    // checks the original boundary; registered execution integration is separate.
    boot(); instruction(0x023102b3); d.ex_valid_i.poke(false.B)
    d.mult_en_ex_o.expect(true.B); d.perf_mul_wait_o.expect(true.B); d.rf_we_id_o.expect(false.B)
    d.en_wb_o.expect(false.B); d.clk_i.step(); d.instr_first_cycle_id_o.expect(false.B)
    d.clk_i.step(3); d.en_wb_o.expect(false.B)
    d.ex_valid_i.poke(true.B); d.rf_we_id_o.expect(true.B); d.en_wb_o.expect(true.B)
    value(d.rf_wdata_id_o,0x123)
    // A load requests once, waits for a response, and uses the last-address
    // increment path when the LSU asks for the second aligned access.
    boot(); instruction(0x00412283)
    d.lsu_req_o.expect(true.B); d.lsu_we_o.expect(false.B); d.en_wb_o.expect(false.B)
    value(d.alu_operand_b_ex_o,4); d.clk_i.step()
    d.lsu_req_o.expect(false.B); d.expecting_load_resp_o.expect(true.B)
    d.lsu_addr_incr_req_i.poke(true.B); value(d.alu_operand_a_ex_o,0x2000); value(d.alu_operand_b_ex_o,4)
    d.lsu_resp_valid_i.poke(true.B); d.en_wb_o.expect(true.B)
    // Taken conditional branches first compare, then compute the target;
    // untaken branches retire in the first cycle in this profile.
    for(taken <- Seq(false,true)) {
      boot(); instruction(0x00310463); d.branch_decision_i.poke(taken.B)
      d.perf_branch_o.expect(true.B); d.en_wb_o.expect((!taken).B)
      if(taken) { d.clk_i.step(); d.pc_set_o.expect(true.B); d.en_wb_o.expect(true.B); value(d.alu_operand_a_ex_o,0x1000); value(d.alu_operand_b_ex_o,8) }
    }
    boot(); instruction(0x008002ef) // JAL x5,+8
    d.pc_set_o.expect(true.B); d.perf_jump_o.expect(true.B); d.en_wb_o.expect(false.B)
    d.clk_i.step(); d.pc_set_o.expect(false.B); d.en_wb_o.expect(true.B); value(d.alu_operand_b_ex_o,4)
    boot(); instruction(0x340112f3) // CSRRW x5,mscratch,x2
    d.csr_access_o.expect(true.B); d.csr_op_en_o.expect(true.B); value(d.rf_wdata_id_o,0x456)
    d.illegal_csr_insn_i.poke(true.B); d.rf_we_id_o.expect(false.B)
    // Independently written intermediate words retain byte order and enables.
    boot(); val a=BigInt("312345678",16); val b=BigInt("287654321",16)
    d.imd_val_d_ex_i.poke(((a<<34)|b).U); d.imd_val_we_ex_i.poke(1.U); d.clk_i.step()
    value(d.imd_val_q_ex_o,a<<34); d.imd_val_we_ex_i.poke(2.U); d.clk_i.step()
    value(d.imd_val_q_ex_o,(a<<34)|b)
    // Regression for the pending source-priority analysis proposal: unlike
    // normal IF traffic, duplicated instruction inputs intentionally disagree.
    // Mult/div precedes jump in the upstream procedural selector.
    boot(); instruction(0x02f0100f); d.instr_rdata_alu_i.poke(0x02004033.U); d.ex_valid_i.poke(false.B)
    d.perf_div_wait_o.expect(true.B); d.perf_jump_o.expect(false.B); d.pc_set_o.expect(false.B)
  }
  test("ID operands and control follow instruction semantics through multicycle completion") {
    simulateRaw(new IbexIdStage) { d => check(d,false) }
  }
  test("ID checker rejects corrupt operand data") {
    val error=intercept[TestFailedException] { simulateRaw(new IbexIdStage) { d => check(d,true) } }
    assert(error.getMessage.contains("ID_MODEL_MISMATCH"))
  }
}
