package deadhorse.top

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocI1SupportSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t20/i1/support-simulation").toAbsolutePath
  }
  def high(x: Bool): Boolean=x.peek().litToBoolean
  test("reset slot cancels once across stopped-clock reset, drains normally and rejects withdrawn offers") {
    simulateRaw(new SocResetSlot) { d =>
      d.reset_n.poke(false.B);d.endpointReset_n.poke(false.B);d.endpointReady.poke(false.B)
      d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
      d.target.gnt.poke(false.B);d.target.rvalid.poke(false.B);d.target.err.poke(false.B);d.target.rdata.poke(0.U)
      d.clk.step(2);d.reset_n.poke(true.B);d.endpointReset_n.poke(true.B);d.endpointReady.poke(true.B);d.clk.step(3)
      def offer(): Unit = {
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(0x40040800L.U);d.bus.bits.we.poke(false.B)
        d.clk.step();assert(high(d.bus.gnt));assert(!high(d.quiescent))
      }
      offer();d.bus.req.poke(false.B);d.clk.step(3)
      assert(!high(d.target.req) && !high(d.bus.rvalid),"WITHDRAWN_REQUEST_ISSUED")
      offer();d.clk.step();d.bus.req.poke(false.B);assert(high(d.target.req))
      d.target.gnt.poke(true.B);d.clk.step();d.target.gnt.poke(false.B)
      assert(!high(d.quiescent))
      // No main edges during this entire asserted/released pulse.
      d.endpointReset_n.poke(false.B);d.endpointReady.poke(false.B)
      // Flush the asserted level into the simulator before releasing it;
      // consecutive queued pokes alone describe a zero-duration pulse.
      assert(!high(d.endpointReset_n))
      d.endpointReset_n.poke(true.B);d.endpointReady.poke(true.B)
      d.clk.step();assert(high(d.bus.rvalid) && high(d.bus.err),"RESET_CANCELLATION_LOST")
      d.clk.step(4);assert(!high(d.bus.rvalid) && !high(d.target.req))
      offer();d.clk.step();d.bus.req.poke(false.B)
      d.target.gnt.poke(true.B);d.clk.step();d.target.gnt.poke(false.B)
      d.target.rdata.poke(0x12345678L.U);d.target.rvalid.poke(true.B);d.clk.step()
      assert(high(d.bus.rvalid) && !high(d.bus.err));assert(d.bus.rdata.peek().litValue==0x12345678L)
      d.target.rvalid.poke(false.B);d.clk.step(3);assert(high(d.quiescent))
    }
  }
  test("retained memory uses independent byte model, denies program stores and quarantines revoked loader grant") {
    simulateRaw(new SocRetainedMemory(SocTestFiles.description)) { d =>
      d.reset_n.poke(false.B);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
      d.halted.poke(true.B);d.started.poke(false.B);d.loaderBusy.poke(false.B);d.locked.poke(false.B)
      d.memValid.poke(false.B);d.memOffset.poke(0.U);d.memWord.poke(0.U);d.clk.step(2);d.reset_n.poke(true.B);d.clk.step()
      def bus(address: Long,write: Boolean=false,value: BigInt=0,mask: Int=15,origin: Int=0): (BigInt,Boolean) = {
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(address.U);d.bus.bits.we.poke(write.B)
        d.bus.bits.wdata.poke(value.U);d.bus.bits.be.poke(mask.U);d.bus.bits.origin.poke(origin.U)
        var n=0;while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<8)}
        d.clk.step();d.bus.req.poke(false.B)
        while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<12)}
        val r=(d.bus.rdata.peek().litValue,high(d.bus.err));d.clk.step(2);r
      }
      def load(offset: Int,value: BigInt): Unit = {
        d.loaderBusy.poke(true.B);d.memOffset.poke(offset.U);d.memWord.poke(value.U);d.memValid.poke(true.B)
        var n=0;while(!high(d.memReady)) {d.clk.step();n+=1;assert(n<8)}
        assert(!high(d.memDone));d.clk.step();d.memValid.poke(false.B)
        assert(high(d.memDone));d.clk.step(2);d.loaderBusy.poke(false.B)
      }
      load(0,0x13579bdfL);assert(bus(0x30000000L)==(BigInt(0x13579bdfL),false))
      assert(bus(0x30000000L,true,0xdeadbeefL)._2);assert(bus(0x30000000L)._1==0x13579bdfL)
      d.loaderBusy.poke(true.B)
      assert(!bus(0x30000000L)._2,"LITE_PROGRAM_READ_DURING_LOADER")
      assert(bus(0x30000000L,origin=1)._2);assert(bus(0x30000800L)._2)
      d.loaderBusy.poke(false.B)
      val random=new scala.util.Random(0x2011)
      val bytes=Array.fill(64)(0)
      for(word<-0 until 16) assert(!bus(0x30000800L+4*word,true,0)._2)
      for(_<-0 until 48) {
        val word=random.nextInt(16);val value=BigInt(32,random);val mask=random.nextInt(16)
        assert(!bus(0x30000800L+4*word,true,value,mask)._2)
        for(lane<-0 until 4 if (mask&(1<<lane))!=0) bytes(word*4+lane)=((value>>(lane*8))&255).toInt
        val expected=(0 until 4).map(l=>BigInt(bytes(word*4+l))<<(8*l)).reduce(_|_)
        assert(bus(0x30000800L+4*word)==(expected,false),"RETAINED_BYTE_MODEL")
      }
      d.memOffset.poke(0.U);d.memWord.poke(0xaabbccddL.U);d.memValid.poke(true.B);d.loaderBusy.poke(true.B)
      d.clk.step();assert(high(d.memReady));d.halted.poke(false.B);d.clk.step();d.memValid.poke(false.B)
      d.clk.step(3);assert(high(d.busy) && !high(d.memDone),"REVOKED_LOADER_PERMISSION")
      d.reset_n.poke(false.B);d.clk.step();d.reset_n.poke(true.B)
      d.loaderBusy.poke(false.B);d.halted.poke(true.B);d.clk.step(2)
      assert(bus(0x30000000L)==(BigInt(0x13579bdfL),false),"REVOKED_WRITE_CHANGED_RAM")
      assert(bus(0x30000c00L)._2)
      load(4,0x2468ace0L);assert(bus(0x30000004L)._1==0x2468ace0L)
    }
  }
}
