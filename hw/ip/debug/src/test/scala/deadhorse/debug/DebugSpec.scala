package deadhorse.debug
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class DebugSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t32/unit").toAbsolutePath
  }
  def high(x: Bool)=x.peek().litToBoolean
  test("debug memory binds flags lanes and rejects wrong-hart writes and reset epochs") {
    simulateRaw(new DebugMemory) {d=>
      d.reset_n.poke(false.B);d.hartMode.poke(3.U);d.hartReset.poke(0.U)
      d.commandHart.poke(1.U);d.commandBusy.poke(true.B);d.data.poke(0xabc.U)
      d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(3);d.reset_n.poke(true.B)
      def transaction(address: Long,origin: Int,write: Boolean=false,value: Long=0,mask: Int=15,
          resetAfterIssue: Boolean=false): Boolean={
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(address.U);d.bus.bits.origin.poke(origin.U)
        d.bus.bits.we.poke(write.B);d.bus.bits.wdata.poke(value.U);d.bus.bits.be.poke(mask.U)
        var clocks=0;while(!high(d.bus.gnt)) {d.clk.step();clocks+=1;assert(clocks<16)}
        d.clk.step();d.bus.req.poke(false.B)
        val issued=high(d.req)
        if(address==0x10400 && mask==2 && issued) assert(d.payload.addr.peek().litValue==0x10401)
        d.clk.step();if(resetAfterIssue)d.hartReset.poke((1<<origin).U)
        while(!high(d.bus.rvalid)) {d.clk.step();clocks+=1;assert(clocks<16)}
        val error=high(d.bus.err);d.clk.step();d.hartReset.poke(0.U);error
      }
      assert(!transaction(0x10400,1,mask=2))
      assert(!transaction(0x10100,1,true,1));assert(transaction(0x10100,1,true,0))
      assert(transaction(0x10108,0,true));assert(!transaction(0x10108,1,true))
      assert(transaction(0x10380,0,true,0x123));assert(!transaction(0x10380,1,true,0x123))
      assert(transaction(0x10800,2));assert(transaction(0x10800,1,resetAfterIssue=true))
      d.hartMode.poke(0.U);assert(transaction(0x10800,1))
    }
  }
  test("SBA retains accepted payload, returns once and quarantines cancelled work") {
    simulateRaw(new DebugSba) {d=>
      d.reset_n.poke(false.B);d.targetUp.poke(true.B);d.targetQuiet.poke(true.B)
      d.req.poke(false.B);d.address.poke(0.U);d.value.poke(0.U);d.mask.poke(0.U);d.write.poke(false.B)
      d.bus.gnt.poke(false.B);d.bus.rvalid.poke(false.B);d.bus.rdata.poke(0.U);d.bus.err.poke(false.B)
      d.clk.step(3);d.reset_n.poke(true.B)
      val random=new scala.util.Random(3201)
      for(index<-0 until 24) {
        val address=0x20000000L+4*index+1;val value=random.nextLong() & 0xffffffffL
        d.req.poke(true.B);d.address.poke(address.U);d.value.poke(value.U);d.write.poke((index%2==0).B);d.mask.poke(2.U)
        var steps=0;while(!high(d.grant)) {d.clk.step();steps+=1;assert(steps<16)}
        d.clk.step();d.req.poke(false.B);d.address.poke(0.U);d.value.poke(0.U)
        for(_<-0 to random.nextInt(5)) {
          assert(high(d.bus.req));assert(d.bus.bits.addr.peek().litValue==(address & ~3L))
          assert(d.bus.bits.wdata.peek().litValue==value && d.bus.bits.origin.peek().litValue==2)
          d.clk.step()
        }
        d.bus.gnt.poke(true.B);d.clk.step();d.bus.gnt.poke(false.B)
        if(index%3==0) {
          d.targetUp.poke(false.B);d.targetQuiet.poke(false.B);d.clk.step()
          assert(high(d.valid) && high(d.error));d.clk.step();d.targetUp.poke(true.B)
          d.req.poke(true.B);d.bus.rvalid.poke(true.B);d.clk.step();d.bus.rvalid.poke(false.B)
          for(_<-0 until 4) {assert(!high(d.grant) && !high(d.valid));d.clk.step()}
          d.req.poke(false.B);d.targetQuiet.poke(true.B);d.clk.step()
        } else {
          d.clk.step(3);d.bus.rvalid.poke(true.B);d.bus.rdata.poke(value.U);d.bus.err.poke((index%5==0).B)
          d.clk.step();d.bus.rvalid.poke(false.B)
          assert(high(d.valid) && high(d.error)==(index%5==0))
          assert(d.result.peek().litValue==(if(index%2==0 || index%5==0) 0L else value));d.clk.step()
        }
        assert(!high(d.valid));d.clk.step()
      }
    }
  }
}
