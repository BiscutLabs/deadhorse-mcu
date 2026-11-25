package deadhorse.pinmux

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class PinmuxTimerSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/pinmux/simulation").toAbsolutePath
  }
  test("all twelve timer channels route through thirteen pads with four exclusive capture routes") {
    simulateRaw(new Pinmux("build/t24/pinmux/pinmux_regs.json",watchdog=true)) {d=>
      def high(v: Bool)=v.peek().litToBoolean
      d.reset_n.poke(false.B);d.watchdogReset_n.get.poke(true.B);d.owner.poke(1.U)
      d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
      d.values.foreach(_.poke(0.U));d.enables.foreach(_.poke(0.U))
      d.timerValues.poke(0.U);d.timerEnables.poke(0.U);d.timerRunning.poke(0.U);d.timerInputs.poke(0.U)
      d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(4)
      def access(a: Int,w: Boolean=false,v: Int=0): (BigInt,Boolean)={
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
        d.bus.bits.wdata.poke(v.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(1.U)
        var n=0;while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<32)}
        d.clk.step();d.bus.req.poke(false.B)
        while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<32)}
        val r=(d.bus.rdata.peek().litValue,high(d.bus.err));d.clk.step(3);r
      }
      def wr(a: Int,v: Int): Unit=assert(!access(a,true,v)._2,s"TIMER_ROUTE_WRITE $a")
      for(p<-0 until 13) wr(0x40+4*p,15)
      for(p<-0 until 4) wr(0x80+4*p,15)
      for(c<-0 until 12) wr(0x40+4*c,c)
      d.timerEnables.poke(4095.U);d.timerRunning.poke(4095.U)
      for(c<-0 until 12) {
        d.timerValues.poke((1<<c).U);d.clk.step(2)
        assert(d.timerOut.peek().litValue==(1<<c) && d.timerEnable.peek().litValue==4095,"TIMER_PIN_IDENTITY")
        assert(access(0x40+4*c,true,15)._2,"RUNNING_TIMER_ROUTE_CHANGED")
      }
      d.watchdogReset_n.get.poke(false.B)
      assert(d.timerOut.peek().litValue==0 && d.timerEnable.peek().litValue==0,"TIMER_PAD_ASYNC_BREAK")
      d.timerEnables.poke(0.U);d.timerRunning.poke(0.U);d.timerValues.poke(0.U)
      d.watchdogReset_n.get.poke(true.B);d.clk.step(3)
      for(p<-9 until 13) wr(0x40+4*p,15)
      for(p<-0 until 4) wr(0x80+4*p,p+8)
      for(p<-0 until 4) {
        d.timerInputs.poke((1<<p).U);d.clk.step(4)
        assert(d.captures.peek().litValue==(1<<(p+8)) && d.captureValid.peek().litValue==0xf00,"TIMER_CAPTURE_IDENTITY")
        assert(access(0x40+4*(p+9),true,p)._2,"CAPTURE_OUTPUT_CONFLICT")
      }
      assert(access(0x80,true,9)._2,"DUPLICATE_CAPTURE")
      for(selector<-12 to 14) assert(access(0x40,true,selector)._2,"INVALID_TIMER_SELECTOR")
      d.timerRunning.poke(256.U);assert(access(0x80,true,15)._2,"LIVE_CAPTURE_CHANGED")
      assert((access(0xf0)._1&1)==1,"ROUTE_ERROR_EVENT")
    }
  }
}
