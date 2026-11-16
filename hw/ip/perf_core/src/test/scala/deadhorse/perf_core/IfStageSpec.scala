package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class IfStageSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def check(d: IbexIfStage, corrupt: Boolean): Unit = {
    d.boot_addr_i.poke(0x1000.U); d.req_i.poke(false.B)
    d.instr_gnt_i.poke(false.B); d.instr_rvalid_i.poke(false.B); d.instr_rdata_i.poke(0.U)
    d.instr_bus_err_i.poke(false.B); d.ic_tag_rdata_i.poke(0.U); d.ic_data_rdata_i.poke(0.U)
    d.ic_scr_key_valid_i.poke(false.B); d.pmp_err_if_i.poke(false.B); d.pmp_err_if_plus2_i.poke(false.B)
    d.instr_valid_clear_i.poke(true.B); d.pc_set_i.poke(false.B); d.pc_mux_i.poke(0.U)
    d.nt_branch_mispredict_i.poke(false.B); d.nt_branch_addr_i.poke(0.U)
    d.exc_pc_mux_i.poke(0.U); d.exc_cause.poke(0.U)
    d.dummy_instr_en_i.poke(false.B); d.dummy_instr_mask_i.poke(0.U)
    d.dummy_instr_seed_en_i.poke(false.B); d.dummy_instr_seed_i.poke(0.U)
    d.icache_enable_i.poke(false.B); d.icache_inval_i.poke(false.B)
    d.branch_target_ex_i.poke(0x2002.U); d.csr_mepc_i.poke(0x3000.U)
    d.csr_depc_i.poke(0x4000.U); d.csr_mtvec_i.poke(0x5000.U); d.id_in_ready_i.poke(false.B)
    case class Instruction(raw: BigInt, bytes: Int, expanded: BigInt)
    // Independent memory/program fixture. C.NOP expands to ADDI x0,x0,0.
    val program=Seq(Instruction(0x00700093,4,0x00700093),Instruction(1,2,0x13),
      Instruction(0x00110113,4,0x00110113),Instruction(1,2,0x13),
      Instruction(0x00000073,4,0x00000073),Instruction(1,2,0x13))
    val targets=Seq((0,0,0,0x1080L),(1,0,0,0x2002L),(2,0,0,0x5000L),
      (2,1,7,0x501cL),(2,1,64,0x507cL),(2,2,0,0x1a110800L),
      (2,3,0,0x1a110808L),(3,0,0,0x3000L),(4,0,0,0x4000L))
    for((mux,exc,cause,target) <- targets; latency <- Seq(2,5)) {
      d.req_i.poke(false.B); d.instr_rvalid_i.poke(false.B); d.instr_gnt_i.poke(false.B)
      d.pc_set_i.poke(false.B); d.id_in_ready_i.poke(false.B)
      d.rst_ni.poke(false.B); d.clk_i.step(); d.rst_ni.poke(true.B)
      d.instr_valid_id_o.expect(false.B); d.instr_new_id_o.expect(false.B)
      val memory=scala.collection.mutable.Map.empty[Long,Int]
      var address=target
      val expected=program.map { instruction =>
        val at=address
        for(i <- 0 until instruction.bytes) memory(address+i)=((instruction.raw>>(i*8))&255).toInt
        address+=instruction.bytes
        (at,instruction)
      }
      def word(at: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v,i)=>v|(BigInt(memory.getOrElse(at+i,0))<<(8*i)))
      val replies=scala.collection.mutable.Queue.empty[(Int,BigInt)]
      var consumed=0; var cycle=0; var priorPayload: Option[(BigInt,BigInt)]=None
      d.pc_mux_i.poke(mux.U); d.exc_pc_mux_i.poke(exc.U); d.exc_cause.poke(cause.U)
      while(consumed<program.size && cycle<120) {
        d.req_i.poke(true.B); d.pc_set_i.poke((cycle==0).B)
        d.id_in_ready_i.poke((cycle%4!=2).B)
        d.csr_mtvec_init_o.expect((cycle==0 && mux==0).B)
        val reply=if(replies.nonEmpty && replies.front._1<=cycle) Some(replies.front) else None
        d.instr_rvalid_i.poke(reply.nonEmpty.B)
        d.instr_rdata_i.poke(reply.map(_._2).getOrElse(BigInt(0)).U)
        val grant=d.instr_req_o.peek().litValue==1 && cycle%3!=1
        d.instr_gnt_i.poke(grant.B)
        if(grant) {
          val at=d.instr_addr_o.peek().litValue.toLong
          assert((at&3)==0,"IF_UNALIGNED_BUS")
          replies.enqueue((cycle+latency,word(at)))
        }
        d.clk_i.step()
        if(reply.nonEmpty) replies.dequeue()
        if(d.instr_new_id_o.peek().litValue==1) {
          val (at,instruction)=expected(consumed)
          val observed=d.instr_rdata_id_o.peek().litValue ^ (if(corrupt) BigInt(1) else BigInt(0))
          assert(observed==instruction.expanded,"IF_INSTRUCTION_MISMATCH")
          d.instr_rdata_alu_id_o.expect(instruction.expanded.U)
          d.pc_id_o.expect(at.U); d.instr_rdata_c_id_o.expect((instruction.raw&65535).U)
          d.instr_is_compressed_id_o.expect((instruction.bytes==2).B)
          d.illegal_c_insn_id_o.expect(false.B); d.instr_fetch_err_o.expect(false.B)
          d.instr_fetch_err_plus2_o.expect(false.B); d.instr_valid_id_o.expect(true.B)
          consumed+=1
          priorPayload=Some((instruction.expanded,BigInt(at)))
        } else priorPayload.foreach { case(data,pc) =>
          d.instr_rdata_id_o.expect(data.U); d.pc_id_o.expect(pc.U)
        }
        d.instr_bp_taken_o.expect(false.B); d.dummy_instr_id_o.expect(false.B)
        d.pc_mismatch_alert_o.expect(false.B); d.instr_intg_err_o.expect(false.B)
        d.icache_ecc_error_o.expect(false.B)
        cycle+=1
      }
      assert(consumed==program.size,"IF_PROGRESS_DEADLINE")
    }
  }
  test("fetch stage consumes byte-memory instruction streams, redirects, compressed crossings and stalls") {
    simulateRaw(new IbexIfStage) { d => check(d,false) }
  }
  test("fetch checker rejects corrupted instruction data") {
    val error=intercept[TestFailedException] { simulateRaw(new IbexIfStage) { d => check(d,true) } }
    assert(error.getMessage.contains("IF_INSTRUCTION_MISMATCH"))
  }
}
