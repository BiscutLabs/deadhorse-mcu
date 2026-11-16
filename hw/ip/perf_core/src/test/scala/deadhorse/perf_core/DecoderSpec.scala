package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class DecoderSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  test("decoder recognizes independently encoded RV32IM operations and contains illegal compressed inputs") {
    simulateRaw(new IbexDecoder) { d =>
      val random = new scala.util.Random(0xdec011L)
      println("Decoder seed=0xdec011")
      def instruction(opcode: Int, rd: Int, f3: Int, rs1: Int, rs2: Int, f7: Int): BigInt =
        BigInt(opcode) | (BigInt(rd)<<7) | (BigInt(f3)<<12) | (BigInt(rs1)<<15) | (BigInt(rs2)<<20) | (BigInt(f7)<<25)
      d.rst_ni.poke(true.B); d.instr_first_cycle_i.poke(true.B)
      d.branch_taken_i.poke(false.B); d.illegal_c_insn_i.poke(false.B)
      val ops = Seq((0,0,"ADD"),(0,1,"SLL"),(0,2,"SLT"),(0,3,"SLTU"),
        (0,4,"XOR"),(0,5,"SRL"),(0,6,"OR"),(0,7,"AND"),(32,0,"SUB"),(32,5,"SRA"))
      for((f7,f3,name) <- ops; _ <- 0 until 24) {
        val a=random.nextInt(32); val b=random.nextInt(32); val dst=random.nextInt(32)
        val i=instruction(0x33,dst,f3,a,b,f7)
        d.instr_rdata_i.poke(i.U); d.instr_rdata_alu_i.poke(i.U)
        d.illegal_insn_o.expect(false.B); d.rf_we_o.expect(true.B)
        d.rf_raddr_a_o.expect(a.U); d.rf_raddr_b_o.expect(b.U); d.rf_waddr_o.expect(dst.U)
        d.rf_ren_a_o.expect(true.B); d.rf_ren_b_o.expect(true.B)
        d.alu_operator_o.expect(IbexAluOp(name)); d.mult_sel_o.expect(false.B); d.div_sel_o.expect(false.B)
      }
      for(f3 <- 0 until 8) {
        val i=instruction(0x33,7,f3,4,5,1)
        d.instr_rdata_i.poke(i.U); d.instr_rdata_alu_i.poke(i.U)
        d.illegal_insn_o.expect(false.B); d.rf_we_o.expect(true.B)
        d.mult_en_o.expect((f3<4).B); d.div_en_o.expect((f3>=4).B)
        d.multdiv_operator_o.expect(Seq(0,1,1,1,2,2,3,3)(f3).U)
        d.multdiv_signed_mode_o.expect(Seq(0,3,1,0,3,0,3,0)(f3).U)
      }
      // Encode signed immediates independently; sign-extension is checked
      // against mathematical values, not a decoder expression.
      for(imm <- Seq(-2048,-1025,-1,0,1,1023,2047)) {
        val i=BigInt(0x13)|(BigInt(3)<<7)|(BigInt(9)<<15)|(BigInt(imm&4095)<<20)
        d.instr_rdata_i.poke(i.U); d.instr_rdata_alu_i.poke(i.U)
        d.imm_i_type_o.expect((BigInt(imm)&0xffffffffL).U)
        d.illegal_insn_o.expect(false.B); d.rf_we_o.expect(true.B)
      }
      // Replicated inputs are arbitrary ports at this boundary. ADD controls
      // must remain ADD even when the independent main decode is a load.
      d.instr_rdata_i.poke(instruction(3,1,2,2,0,0).U)
      d.instr_rdata_alu_i.poke(instruction(0x33,3,0,4,5,0).U)
      d.data_req_o.expect(true.B); d.alu_op_b_mux_sel_o.expect(0.U)
      d.alu_operator_o.expect(IbexAluOp("ADD"))
      for(i <- Seq.fill(256)(BigInt(32,random))) {
        d.instr_rdata_i.poke(i.U); d.instr_rdata_alu_i.poke(BigInt(32,random).U)
        d.illegal_c_insn_i.poke(true.B)
        d.illegal_insn_o.expect(true.B)
        d.rf_we_o.expect(false.B); d.data_req_o.expect(false.B); d.data_we_o.expect(false.B)
        d.jump_in_dec_o.expect(false.B); d.jump_set_o.expect(false.B); d.branch_in_dec_o.expect(false.B)
        d.csr_access_o.expect(false.B); d.mult_en_o.expect(false.B); d.div_en_o.expect(false.B)
      }
    }
  }
  test("decoder checker rejects corrupted operation selection") {
    val error = intercept[TestFailedException] {
      simulateRaw(new IbexDecoder) { d =>
        d.rst_ni.poke(true.B); d.instr_first_cycle_i.poke(true.B)
        d.branch_taken_i.poke(false.B); d.illegal_c_insn_i.poke(false.B)
        // ADD x0,x0,x0. Corrupt only the observed output before comparison.
        d.instr_rdata_i.poke(0x33.U); d.instr_rdata_alu_i.poke(0x33.U)
        assert((d.alu_operator_o.peek().litValue ^ 1) == 0, "DECODER_MODEL_MISMATCH")
      }
    }
    assert(error.getMessage.contains("DECODER_MODEL_MISMATCH"))
  }
}
