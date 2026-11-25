package deadhorse.pinmux
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class PinmuxSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t24/pinmux-simulation").toAbsolutePath
  }
  def high(b: Bool)=b.peek().litToBoolean
  def oracle(d: PinmuxPad): Unit={
    d.reset_n.poke(false.B);d.select.poke(0.U);d.values.poke(0.U);d.enables.poke(0.U);d.clk.step(2)
    d.reset_n.poke(true.B);var previous=0
    val random=new scala.util.Random(24)
    val cases=(for(s<-0 to 3;v<-0 to 7;e<-0 to 7;k<-0 until 2) yield(s,v,e))++
      (0 until 600).map(_=>(random.nextInt(4),random.nextInt(8),random.nextInt(8)))
    for((s,v,e)<-cases) {
      d.select.poke(s.U);d.values.poke(v.U);d.enables.poke(e.U)
      val isChanging=s!=previous;val driven= !isChanging && s!=0 && ((e>>(s-1))&1)==1
      d.clk.step()
      assert(high(d.enable)==driven,"PINMUX_ENABLE_ORACLE")
      assert(high(d.value)==(driven && ((v>>(s-1))&1)==1),"PINMUX_VALUE_ORACLE")
      assert(d.active.peek().litValue==s && high(d.settling)==isChanging,"PINMUX_SELECT_ORACLE")
      previous=s
    }
    d.reset_n.poke(false.B)
    assert(!high(d.enable) && !high(d.value) && d.active.peek().litValue==0,"PINMUX_ASYNC_RESET")
  }
  test("all selections, source enables, rapid changes and async reset follow cycle oracle; seed24") {
    simulateRaw(new PinmuxPad)(oracle)
  }
  test("actual stuck-high output enable is rejected by the same oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new PinmuxPad {override protected def outputEnable(v: Bool): Bool=true.B})(oracle)
    };assert(e.getMessage.contains("PINMUX_ENABLE_ORACLE"))
  }
  test("clock demand spans accepted selection write through registered pad handover") {
    simulateRaw(new Pinmux("build/t24/pinmux/pinmux_regs.json")) {d=>
      d.reset_n.poke(false.B);d.owner.poke(1.U);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
      d.timerValues.poke(0.U);d.timerEnables.poke(0.U);d.timerRunning.poke(0.U);d.timerInputs.poke(0.U)
      d.values.foreach(_.poke(7.U));d.enables.foreach(_.poke(7.U));d.clk.step(3)
      d.reset_n.poke(true.B);d.clk.step(3);assert(!high(d.clockHold))
      d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(true.B);d.bus.bits.wdata.poke(1.U)
      d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(1.U);d.bus.req.poke(true.B)
      assert(high(d.bus.gnt));d.clk.step();d.bus.req.poke(false.B)
      var n=0
      while(d.pinsEnable.peek().litValue==0) {
        assert(high(d.clockHold),"PINMUX_WRITE_CLOCK_DEMAND");d.clk.step();n+=1;assert(n<12)
      }
      assert(high(d.clockHold) && d.pinsOut.peek().litValue==1,"PINMUX_HANDOVER_CLOCK_DEMAND")
      d.clk.step(8);assert(!high(d.clockHold),"PINMUX_IDLE_CLOCK_DEMAND")
    }
  }
  test("MMIO lane masks, denied owners, exact decode and stable-selection data writes") {
    simulateRaw(new Pinmux("build/t24/pinmux/pinmux_regs.json")) {d=>
      d.reset_n.poke(false.B);d.owner.poke(1.U);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
      d.timerValues.poke(0.U);d.timerEnables.poke(0.U);d.timerRunning.poke(0.U);d.timerInputs.poke(0.U)
      d.values.zipWithIndex.foreach {case(v,i)=>v.poke((i+1).U)};d.enables.foreach(_.poke(7.U));d.clk.step(3)
      d.reset_n.poke(true.B);d.clk.step(3)
      def access(a: Int,w: Boolean=false,v: Int=0,mask: Int=15,origin: Int=1): (BigInt,Boolean)={
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B);d.bus.bits.wdata.poke(v.U)
        d.bus.bits.be.poke(mask.U);d.bus.bits.origin.poke(origin.U);var n=0
        while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<32)}
        d.clk.step();d.bus.req.poke(false.B)
        while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<32)}
        val r=(d.bus.rdata.peek().litValue,high(d.bus.err));d.clk.step(3);r
      }
      assert(d.pinsEnable.peek().litValue==0)
      for(i<-0 until 3) assert(!access(4*i,true,i+1)._2)
      assert(d.pinsOut.peek().litValue==3 && d.pinsEnable.peek().litValue==7)
      assert(!access(0,true,0,mask=2)._2 && access(0)._1==1)
      for(o<-0 until 8 if o!=1) {assert(access(0,true,0,origin=o)._2);assert(access(0)._1==1)}
      for(a<-Seq(3,12,28,36,256,4092)) assert(access(a,true,0)._2)
      d.values(0).poke(0.U);d.clk.step();assert(d.pinsOut.peek().litValue==2)
      d.enables(1).poke(0.U);d.clk.step();assert(d.pinsEnable.peek().litValue==5 && d.pinsOut.peek().litValue==0)
      assert(access(0x10)._1==1 && access(0x14)._1==2 && access(0x18)._1==3 && access(0x20)._1==0)
      d.reset_n.poke(false.B);assert(d.pinsEnable.peek().litValue==0 && d.pinsOut.peek().litValue==0)
    }
  }
}
