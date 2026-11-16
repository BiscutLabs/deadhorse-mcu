package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class LoadStoreSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def exercise(d: IbexLoadStoreUnit, corrupt: Boolean): Unit = {
    val random = new scala.util.Random(0x15a011L)
    println("LSU seed=0x15a011")
    d.lsu_req_i.poke(false.B); d.data_gnt_i.poke(false.B); d.data_rvalid_i.poke(false.B)
    d.data_bus_err_i.poke(false.B); d.data_pmp_err_i.poke(false.B); d.data_rdata_i.poke(0.U)
    d.lsu_we_i.poke(false.B); d.lsu_type_i.poke(0.U); d.lsu_wdata_i.poke(0.U)
    d.lsu_sign_ext_i.poke(false.B); d.adder_result_ex_i.poke(0.U)
    d.rst_ni.poke(false.B); d.clk_i.step(); d.rst_ni.poke(true.B)
    d.busy_o.expect(false.B); d.addr_last_o.expect(0.U)
    case class Reply(due: Int, value: BigInt, error: Boolean)
    def transaction(kind: Int, offset: Int, write: Boolean, signed: Boolean,
        grantMode: Int, latency: Int, errorBeat: Int): Unit = {
      val address=16+offset
      val size=if(kind==0) 4 else if(kind==1) 2 else 1
      val beats=if(offset+size>4) 2 else 1
      val memory=Array.fill(64)(random.nextInt(256))
      val initial=memory.clone()
      val value=BigInt(32,random)
      val expectedMemory=initial.clone()
      if(write) for(i <- 0 until size) expectedMemory(address+i)=((value>>(i*8))&255).toInt
      val unsigned=(0 until size).foldLeft(BigInt(0))((v,i)=>v|(BigInt(initial(address+i))<<(i*8)))
      val expectedRead=(if(signed && unsigned.testBit(size*8-1)) unsigned-(BigInt(1)<<(size*8)) else unsigned)&0xffffffffL
      val queue=scala.collection.mutable.Queue.empty[Reply]
      var requested=true; var responded=false; var grants=0; var cycle=0
      d.lsu_type_i.poke(kind.U); d.lsu_we_i.poke(write.B)
      d.lsu_sign_ext_i.poke(signed.B); d.lsu_wdata_i.poke(value.U)
      while(!responded && cycle<40) {
        d.lsu_req_i.poke(requested.B)
        d.adder_result_ex_i.poke(address.U)
        if(d.addr_incr_req_o.peek().litValue==1) d.adder_result_ex_i.poke((address+4).U)
        val reply=if(queue.nonEmpty && queue.front.due<=cycle) Some(queue.front) else None
        d.data_rvalid_i.poke(reply.nonEmpty.B)
        d.data_rdata_i.poke(reply.map(_.value).getOrElse(BigInt(0)).U)
        d.data_bus_err_i.poke(reply.exists(_.error).B)
        val grant=d.data_req_o.peek().litValue==1 && (grantMode==0 || cycle%3==grantMode-1)
        d.data_gnt_i.poke(grant.B)
        if(grant) {
          val aligned=d.data_addr_o.peek().litValue.toInt
          assert(aligned==16+grants*4,"LSU_ADDRESS_MISMATCH")
          assert(grants<beats,"LSU_EXTRA_REQUEST")
          val busValue=(0 until 4).foldLeft(BigInt(0))((v,i)=>v|(BigInt(memory(aligned+i))<<(8*i)))
          if(write) {
            val be=d.data_be_o.peek().litValue
            val data=d.data_wdata_o.peek().litValue
            for(i <- 0 until 4 if be.testBit(i)) memory(aligned+i)=((data>>(8*i))&255).toInt
          }
          queue.enqueue(Reply(cycle+latency,busValue,grants==errorBeat)); grants+=1
        }
        val done=d.lsu_req_done_o.peek().litValue==1
        if(d.lsu_resp_valid_o.peek().litValue==1) {
          assert(reply.nonEmpty,"LSU_SPURIOUS_RESPONSE")
          val failed=errorBeat>=0
          d.load_err_o.expect((failed && !write).B); d.store_err_o.expect((failed && write).B)
          d.lsu_rdata_valid_o.expect((!write && !failed).B)
          if(!write && !failed) {
            val observed=d.lsu_rdata_o.peek().litValue ^ (if(corrupt) BigInt(1) else BigInt(0))
            assert(observed==expectedRead,"LSU_MODEL_MISMATCH")
          }
          if(write && !failed) assert(memory.sameElements(expectedMemory),"LSU_STORE_MISMATCH")
          val expectedLast=if(beats==1 || errorBeat==0) address else 20
          d.addr_last_o.expect(expectedLast.U)
          assert(grants==beats,"LSU_MISSING_REQUEST")
          responded=true
        }
        d.load_resp_intg_err_o.expect(false.B); d.store_resp_intg_err_o.expect(false.B)
        d.clk_i.step()
        if(reply.nonEmpty) queue.dequeue()
        if(done) requested=false
        cycle+=1
      }
      assert(responded,"LSU_DEADLINE")
      d.lsu_req_i.poke(false.B); d.data_rvalid_i.poke(false.B)
      d.data_bus_err_i.poke(false.B); d.data_gnt_i.poke(false.B)
      d.busy_o.expect(false.B)
    }
    for(kind <- 0 until 4; offset <- 0 until 4; write <- Seq(false,true);
        signed <- Seq(false,true); grantMode <- 0 until 3; latency <- Seq(2,6)) {
      transaction(kind,offset,write,signed,grantMode,latency,-1)
    }
    for(offset <- 0 until 4; write <- Seq(false,true); error <- 0 until (if(offset==0) 1 else 2)) {
      transaction(0,offset,write,false,1,4,error)
    }
  }
  test("LSU aligns byte-memory transactions with delayed grants, ordered replies and bus errors") {
    simulateRaw(new IbexLoadStoreUnit) { d => exercise(d,false) }
  }
  test("LSU byte-memory checker rejects corrupt load data") {
    val error=intercept[TestFailedException] {
      simulateRaw(new IbexLoadStoreUnit) { d => exercise(d,true) }
    }
    assert(error.getMessage.contains("LSU_MODEL_MISMATCH"))
  }
}
