package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class CsRegistersSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def check(d: IbexCsRegisters, corrupt: Boolean): Unit = {
    d.hart_id_i.poke(19.U); d.csr_mtvec_init_i.poke(false.B); d.boot_addr_i.poke("h12345600".U)
    d.csr_access_i.poke(false.B); d.csr_addr_i.poke(0.U); d.csr_wdata_i.poke(0.U)
    d.csr_op_i.poke(0.U); d.csr_op_en_i.poke(false.B)
    d.irq_software_i.poke(false.B); d.irq_timer_i.poke(false.B); d.irq_external_i.poke(false.B)
    d.irq_fast_i.poke(0.U); d.nmi_mode_i.poke(false.B); d.debug_mode_i.poke(false.B)
    d.debug_mode_entering_i.poke(false.B); d.debug_cause_i.poke(0.U); d.debug_csr_save_i.poke(false.B)
    d.pc_if_i.poke(0x100.U); d.pc_id_i.poke(0x102.U); d.pc_wb_i.poke(0x106.U)
    d.ic_scr_key_valid_i.poke(false.B); d.csr_save_if_i.poke(false.B); d.csr_save_id_i.poke(false.B)
    d.csr_save_wb_i.poke(false.B); d.csr_restore_mret_i.poke(false.B); d.csr_restore_dret_i.poke(false.B)
    d.csr_save_cause_i.poke(false.B); d.csr_mcause_i.poke(0.U); d.csr_mtval_i.poke(0.U)
    d.instr_ret_i.poke(false.B); d.instr_ret_compressed_i.poke(false.B); d.instr_ret_spec_i.poke(false.B)
    d.instr_ret_compressed_spec_i.poke(false.B); d.iside_wait_i.poke(false.B); d.jump_i.poke(false.B)
    d.branch_i.poke(false.B); d.branch_taken_i.poke(false.B); d.mem_load_i.poke(false.B)
    d.mem_store_i.poke(false.B); d.dside_wait_i.poke(false.B); d.mul_wait_i.poke(false.B); d.div_wait_i.poke(false.B)
    d.rst_ni.poke(false.B); d.clk_i.step(); d.rst_ni.poke(true.B)
    def access(address: Int, op: Int = 0, value: BigInt = 0): Unit = {
      d.csr_access_i.poke(true.B); d.csr_addr_i.poke(address.U); d.csr_op_i.poke(op.U)
      d.csr_wdata_i.poke(value.U); d.csr_op_en_i.poke((op!=0).B)
    }
    def idle(): Unit = { d.csr_access_i.poke(false.B); d.csr_op_en_i.poke(false.B); d.csr_op_i.poke(0.U) }
    def read(address: Int, expected: BigInt, illegal: Boolean = false): Unit = {
      access(address); d.illegal_csr_insn_o.expect(illegal.B)
      val observed=d.csr_rdata_o.peek().litValue ^ (if(corrupt) BigInt(1) else BigInt(0))
      assert(observed==expected,s"CSR_MODEL_MISMATCH address=$address expected=$expected actual=$observed")
      idle()
    }
    def write(address: Int, value: BigInt, op: Int = 1, illegal: Boolean = false): Unit = {
      access(address,op,value); d.illegal_csr_insn_o.expect(illegal.B); d.clk_i.step(); idle()
    }
    read(0x301,BigInt("40101104",16)); read(0xf14,19); read(0x300,0x80)
    read(0x3a0,0,illegal=true); read(0x747,0,illegal=true); read(0xc00,0,illegal=true)
    // Scratch registers are an independent software dictionary under write,
    // atomic bit set and clear, tested with reproducible values.
    val random=new scala.util.Random(0xc5b011L); println("CSR seed=0xc5b011")
    var scratch=BigInt(0); val mask=(BigInt(1)<<32)-1
    for(_ <- 0 until 64; op <- 1 to 3) {
      val value=BigInt(32,random)
      scratch=op match { case 1=>value; case 2=>scratch|value; case 3=>scratch & (mask^value) }
      write(0x340,value,op); read(0x340,scratch)
    }
    write(0xf12,0,illegal=true); read(0xf12,22)
    d.csr_mtvec_init_i.poke(true.B); d.clk_i.step(); d.csr_mtvec_init_i.poke(false.B)
    read(0x305,BigInt("12345601",16)); write(0x305,0xabc); read(0x305,0xa01)
    write(0x341,0x777); read(0x341,0x776)
    write(0x300,mask); read(0x300,0x221888)
    write(0x300,0x800); read(0x300,0) // unsupported MPP becomes U
    write(0x304,mask); read(0x304,BigInt("7fff0888",16))
    d.irq_timer_i.poke(true.B); d.irq_fast_i.poke(4.U)
    d.irqs_o.expect(((1<<16)|4).U); d.irq_pending_o.expect(true.B)
    read(0x344,0x40080); write(0x304,0); d.irq_pending_o.expect(false.B)
    // Debug-only writes are blocked outside D mode. Trigger writes additionally
    // require debug mode even though the trigger CSRs may be read in M mode.
    write(0x7b1,0x456,illegal=true); read(0x7b1,0,illegal=true)
    write(0x7a2,0x100); read(0x7a2,0)
    d.debug_mode_i.poke(true.B)
    write(0x7a0,mask); read(0x7a0,0); write(0x7a2,0x100); write(0x7a1,4)
    d.trigger_match_o.expect(true.B); d.pc_if_i.poke(0x104.U); d.trigger_match_o.expect(false.B)
    read(0x7a1,BigInt("2800104c",16)); write(0x7b0,mask); read(0x7b0,BigInt("4000b007",16))
    write(0x7b1,0x789); read(0x7b1,0x788)
    d.debug_mode_i.poke(false.B)
    // Enable counters, load a low-word carry boundary, and count actual edges
    // using a host integer rather than the hardware's split increment network.
    write(0x320,5); write(0xb80,7); write(0xb00,mask); write(0xb82,2); write(0xb02,mask)
    read(0xb80,7); read(0xb82,2); write(0x320,0)
    d.instr_ret_i.poke(true.B); d.clk_i.step(3); d.instr_ret_i.poke(false.B)
    read(0xb00,2); read(0xb80,8); read(0xb02,2); read(0xb82,3)
    d.instr_ret_spec_i.poke(true.B); read(0xb02,3); d.instr_ret_spec_i.poke(false.B)
    read(0xb03,0); read(0x323,0)
    // Traps preserve previous state for recoverable NMI and qualify the sticky
    // double-fault bits. Save controls are one-hot in these architectural tests.
    write(0x300,0x88); write(0x341,0x222); write(0x342,3)
    d.csr_save_id_i.poke(true.B); d.csr_save_cause_i.poke(true.B)
    d.csr_mcause_i.poke(2.U); d.csr_mtval_i.poke(0xdead.U)
    d.double_fault_seen_o.expect(false.B); d.clk_i.step()
    d.csr_save_cause_i.poke(false.B); d.csr_save_id_i.poke(false.B)
    read(0x341,0x102); read(0x342,2); read(0x343,0xdead); read(0x300,0x1880); read(0x7c0,0x40)
    d.csr_save_if_i.poke(true.B); d.csr_save_cause_i.poke(true.B)
    d.double_fault_seen_o.expect(true.B); d.clk_i.step()
    d.csr_save_if_i.poke(false.B); d.csr_save_cause_i.poke(false.B); read(0x7c0,0xc0)
    d.nmi_mode_i.poke(true.B); d.csr_restore_mret_i.poke(true.B); d.clk_i.step()
    d.csr_restore_mret_i.poke(false.B); d.nmi_mode_i.poke(false.B)
    read(0x341,0x102); read(0x342,2); read(0x7c0,0x80)
    // Enter U through MRET; illegal machine CSR writes do not modify scratch.
    write(0x300,0x80); d.csr_restore_mret_i.poke(true.B); d.clk_i.step(); d.csr_restore_mret_i.poke(false.B)
    d.priv_mode_id_o.expect(0.U); write(0x340,0,illegal=true); read(0x340,scratch,illegal=true)
    // Debug trap captures the originating U privilege and selected PC, then
    // DRET restores it. No regular trap state is altered by this entry.
    d.debug_csr_save_i.poke(true.B); d.debug_cause_i.poke(3.U)
    d.csr_save_wb_i.poke(true.B); d.csr_save_cause_i.poke(true.B); d.clk_i.step()
    d.debug_csr_save_i.poke(false.B); d.csr_save_wb_i.poke(false.B); d.csr_save_cause_i.poke(false.B)
    d.priv_mode_id_o.expect(3.U); d.debug_mode_i.poke(true.B)
    read(0x7b0,BigInt("4000b0c4",16)); read(0x7b1,0x106)
    d.csr_restore_dret_i.poke(true.B); d.clk_i.step(); d.csr_restore_dret_i.poke(false.B)
    d.priv_mode_id_o.expect(0.U)
    d.rst_ni.poke(false.B); d.clk_i.step(); d.rst_ni.poke(true.B)
    d.priv_mode_id_o.expect(3.U); read(0x340,0); read(0xb00,0); read(0x7c0,0)
    // Preserve procedural priority even when a producer violates the unique
    // selector promise: save > DRET > MRET, and PC IF > ID > WB > default ID.
    // This intentionally checks the proposed source-priority proof contract,
    // not the synthesis completion of an invalid unique-case input.
    val pcs=Vector(BigInt(0x111),BigInt(0x223),BigInt(0x447))
    d.pc_if_i.poke(pcs(0).U); d.pc_id_i.poke(pcs(1).U); d.pc_wb_i.poke(pcs(2).U)
    for(outer <- 0 until 8; inner <- 0 until 8) {
      d.rst_ni.poke(false.B); d.clk_i.step(); d.rst_ni.poke(true.B)
      d.debug_mode_i.poke(true.B); write(0x7b0,0); d.debug_mode_i.poke(false.B)
      write(0x300,0x1800)
      val save=(outer&1)!=0; val dret=(outer&2)!=0; val mret=(outer&4)!=0
      d.csr_save_cause_i.poke(save.B); d.csr_restore_dret_i.poke(dret.B); d.csr_restore_mret_i.poke(mret.B)
      d.csr_save_if_i.poke(((inner&1)!=0).B); d.csr_save_id_i.poke(((inner&2)!=0).B)
      d.csr_save_wb_i.poke(((inner&4)!=0).B); d.clk_i.step()
      d.csr_save_cause_i.poke(false.B); d.csr_restore_dret_i.poke(false.B); d.csr_restore_mret_i.poke(false.B)
      d.csr_save_if_i.poke(false.B); d.csr_save_id_i.poke(false.B); d.csr_save_wb_i.poke(false.B)
      val privilege=if(save) 3 else if(dret) 0 else 3
      val pc=(0 until 3).find(index => (inner&(1<<index))!=0).map(pcs).getOrElse(pcs(1))
      d.priv_mode_id_o.expect(privilege.U)
      read(0x341,if(save) pc else BigInt(0),illegal=privilege==0)
    }
  }
  test("CSR accesses, interrupts, counters, trap stack and debug match architectural expectations") {
    simulateRaw(new IbexCsRegisters) { d => check(d,false) }
  }
  test("CSR checker rejects corrupt read data") {
    val error=intercept[TestFailedException] { simulateRaw(new IbexCsRegisters) { d => check(d,true) } }
    assert(error.getMessage.contains("CSR_MODEL_MISMATCH"))
  }
}
