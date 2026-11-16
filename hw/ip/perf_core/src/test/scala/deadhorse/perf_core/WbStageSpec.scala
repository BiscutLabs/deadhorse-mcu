package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class WbStageSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def check(d: IbexWbStage, corrupt: Boolean): Unit = {
    val random=new scala.util.Random(0xbab011L)
    println("WB seed=0xbab011")
    for(control <- 0 until 256; _ <- 0 until 4) {
      def bit(n: Int)=(control&(1<<n))!=0
      val a=BigInt(32,random); val b=BigInt(32,random); val address=random.nextInt(32)
      d.rst_ni.poke(bit(7).B); d.en_wb_i.poke(bit(0).B); d.instr_type_wb_i.poke(random.nextInt(4).U)
      d.pc_id_i.poke(BigInt(32,random).U); d.instr_is_compressed_id_i.poke(bit(1).B)
      d.instr_perf_count_id_i.poke(bit(2).B); d.rf_waddr_id_i.poke(address.U)
      d.rf_wdata_id_i.poke(a.U); d.rf_wdata_lsu_i.poke(b.U)
      d.rf_we_id_i.poke(bit(3).B); d.rf_we_lsu_i.poke(bit(4).B)
      d.lsu_resp_valid_i.poke(bit(5).B); d.lsu_resp_err_i.poke(bit(6).B)
      d.dummy_instr_id_i.poke(bit(7).B)
      val selected=Seq((bit(3),a),(bit(4),b)).collect { case(true,value)=>value }
      val expected=selected.foldLeft(BigInt(0))(_|_)
      val observed=d.rf_wdata_wb_o.peek().litValue ^ (if(corrupt) BigInt(1) else BigInt(0))
      assert(observed==expected,"WB_MODEL_MISMATCH")
      d.rf_we_wb_o.expect(selected.nonEmpty.B); d.rf_waddr_wb_o.expect(address.U)
      val retired=bit(0)&&bit(2)&& !(bit(5)&&bit(6))
      d.perf_instr_ret_wb_o.expect(retired.B); d.perf_instr_ret_compressed_wb_o.expect((retired&&bit(1)).B)
      d.ready_wb_o.expect(true.B); d.rf_write_wb_o.expect(false.B)
      d.outstanding_load_wb_o.expect(false.B); d.outstanding_store_wb_o.expect(false.B)
      d.pc_wb_o.expect(0.U); d.rf_wdata_fwd_wb_o.expect(0.U); d.instr_done_wb_o.expect(false.B)
      d.perf_instr_ret_wb_spec_o.expect(false.B); d.perf_instr_ret_compressed_wb_spec_o.expect(false.B)
      d.dummy_instr_wb_o.expect(bit(7).B)
    }
  }
  test("writeback bypass preserves both write masks, retirement qualification and tieoffs") {
    simulateRaw(new IbexWbStage) { d => check(d,false) }
  }
  test("writeback checker rejects corrupt data") {
    val error=intercept[TestFailedException] { simulateRaw(new IbexWbStage) { d => check(d,true) } }
    assert(error.getMessage.contains("WB_MODEL_MISMATCH"))
  }
}
