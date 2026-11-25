package deadhorse.timers

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class GeneralTimersControlSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/timers/control-simulation").toAbsolutePath
  }
  test("start validates applied values; DMA replacement, masking, stop and watchdog retain their contracts") {
    simulateRaw(new GeneralTimers("build/t21/timers/timers_regs.json",watchdog=true)) { d=>
      def high(v: Bool)=v.peek().litToBoolean
      d.reset_n.poke(false.B);d.watchdogReset_n.get.poke(true.B);d.performanceReady.get.poke(true.B)
      d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.owner.poke(1.U)
      d.captureIn.poke(0.U);d.captureValid.poke(0.U);d.dmaAck.poke(0.U)
      d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(4)
      def access(a: Int,w: Boolean=false,v: Int=0,origin: Int=1): (BigInt,Boolean)={
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
        d.bus.bits.wdata.poke(v.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(origin.U)
        var n=0;while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<32)}
        d.clk.step();d.bus.req.poke(false.B)
        while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<32)}
        val r=(d.bus.rdata.peek().litValue,high(d.bus.err));d.clk.step(2);r
      }
      def wr(a: Int,v: Int): Unit=assert(!access(a,true,v)._2,s"CONTROL_WRITE $a")
      def rd(a: Int): BigInt={val(v,e)=access(a);assert(!e);v}
      wr(48,0);wr(64,9);wr(128,5);wr(192,9);wr(20,1)
      wr(64,4);wr(192,3)
      assert(access(48,true,1)._2 && rd(48)==0,"START_STALE_ACTIVE_COMPARE")
      wr(20,1);wr(48,1);d.clk.step(20);assert(d.pinsEnable.peek().litValue==1)
      wr(48,0);wr(64,31);wr(192,8);wr(20,1);wr(32,1);wr(48,1)
      d.clk.step(100)
      assert(d.dmaRequest.peek().litValue==1 && (rd(44)&1)==1,"DMA_OVERRUN")
      d.dmaAck.poke(1.U);wr(44,511)
      var pulses=0
      for(_<-0 until 128) {d.clk.step();if(d.dmaRequest.peek().litValue==1) pulses+=1}
      assert(pulses==4 && rd(44)==0,"DMA_EVENT_ACK_REPLACEMENT")
      d.dmaAck.poke(0.U);d.clk.step(40);wr(32,0)
      assert(d.dmaRequest.peek().litValue==0,"DMA_MASK_CLEAR")
      wr(32,1);d.clk.step(40);wr(48,0)
      assert(d.dmaRequest.peek().litValue==0,"DMA_STOP_CLEAR")
      wr(48,1);d.clk.step(40);assert(d.pinsEnable.peek().litValue==1)
      d.watchdogReset_n.get.poke(false.B)
      assert(d.pinsEnable.peek().litValue==0 && d.pinsOut.peek().litValue==0,"TIMER_ASYNC_WATCHDOG")
      d.performanceReady.get.poke(false.B);d.clk.step(4);d.watchdogReset_n.get.poke(true.B)
      d.clk.step(40);assert(d.pinsEnable.peek().litValue==0,"TIMER_BREAK_RETAINED")
      wr(20,1);d.clk.step(40);assert(d.pinsEnable.peek().litValue==0,"DMA_CANNOT_REARM")
      d.performanceReady.get.poke(true.B);d.clk.step(4)
      assert(access(48,true,0,origin=0)._2,"DENIED_STOP_ERRORS")
      wr(20,1);d.clk.step(40)
      assert(d.pinsEnable.peek().litValue==0,"DENIED_STOP_CANNOT_REARM")
      wr(48,0);wr(20,1);wr(48,1)
      d.clk.step(4);assert(d.pinsEnable.peek().litValue==1,"CPU_STOP_ACK_REARMS")
      wr(48,0);wr(64,999);wr(192,300);wr(20,1);wr(48,1)
      wr(192,400);wr(20,1);assert(rd(16)==1)
      assert(access(48,true,0,origin=0)._2 && rd(16)==1,"DENIED_STOP_PRESERVES_PENDING")
      d.clk.step(1100);assert(rd(16)==0)
      val wave=(0 until 2000).count { _=>val bit=d.pinsOut.peek().litValue.testBit(0);d.clk.step();bit }
      assert(wave==800,"DENIED_STOP_PRESERVES_COMPARE")
      wr(192,200);wr(20,1);assert(rd(16)==1);wr(48,0)
      assert(rd(16)==0 && d.pinsEnable.peek().litValue==0,"STOP_CANCELS_QUEUED_COMPARE")
      wr(20,1);wr(48,1)
      // Assert watchdog after an APPLY bus acceptance, before its register pulse.
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(20.U);d.bus.bits.we.poke(true.B)
      d.bus.bits.wdata.poke(1.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(1.U)
      while(!high(d.bus.gnt)) d.clk.step()
      d.clk.step();d.bus.req.poke(false.B);d.watchdogReset_n.get.poke(false.B)
      assert(d.pinsEnable.peek().litValue==0,"ASYNC_DISABLE_WITH_ACCEPTED_APPLY")
      d.watchdogReset_n.get.poke(true.B);d.clk.step(10)
      assert(rd(16)==0 && d.pinsEnable.peek().litValue==0,"STALE_APPLY_CANNOT_REARM")
      d.performanceReady.get.poke(false.B);wr(48,0)
      d.performanceReady.get.poke(true.B);d.clk.step(4);wr(20,1);wr(48,1)
      assert(d.pinsEnable.peek().litValue==0,"STALE_EPOCH_STOP_CANNOT_REARM")
      wr(48,0);wr(20,1);wr(48,1);assert(d.pinsEnable.peek().litValue==1)

    }
  }
}
