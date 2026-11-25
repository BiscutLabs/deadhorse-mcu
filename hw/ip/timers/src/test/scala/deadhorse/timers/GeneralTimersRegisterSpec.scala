package deadhorse.timers

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Preserved boundary cases from the retired timer/PWM maps, using public MMIO. */
class GeneralTimersRegisterSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/timers/register-simulation").toAbsolutePath
  }
  def init(d: GeneralTimers): TimerBus={
    d.reset_n.poke(false.B);d.owner.poke(1.U);d.captureIn.poke(0.U);d.captureValid.poke(4095.U)
    d.dmaAck.poke(0.U);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
    d.clk.step(4);d.reset_n.poke(true.B);d.clk.step(4);new TimerBus(d.clk,d.bus,1)
  }
  for(mhz<-Seq(8,9)) test(s"timebase load, wrap, stop and live-load rejection at $mhz MHz") {
    simulateRaw(new GeneralTimers("build/t21/timers/timers_regs.json",mhz)) {d=>
      val b=init(d);b.wr(8,BigInt("fffffff0",16));b.wr(12,1)
      assert(d.timeNow.peek().litValue==BigInt("fffffff0",16))
      b.wr(0,1);val before=d.timeNow.peek().litValue;d.clk.step(mhz*40)
      assert(d.timeNow.peek().litValue==((before+40)&BigInt("ffffffff",16)),"TIME_WRAP_RATE")
      assert(d.clockHold.peek().litToBoolean)
      assert(b.access(12,true,1)._2,"LIVE_LOAD_REJECTED")
      b.wr(0,0);val stopped=d.timeNow.peek().litValue;d.clk.step(50)
      assert(d.timeNow.peek().litValue==stopped && !d.clockHold.peek().litToBoolean)
      d.reset_n.poke(false.B);assert(d.timeNow.peek().litValue==0)
    }
  }
  test("byte strobes, duty endpoints, queued snapshot, maximum prescaler and software DMA ack") {
    simulateRaw(new GeneralTimers("build/t21/timers/timers_regs.json")) {d=>
      val b=init(d)
      b.wr(64,0xabcd);b.wr(64,0x1234,1);assert(b.rd(64)==0xab34)
      b.wr(192,0x1ffff);b.wr(192,0,4);assert(b.rd(192)==0xffff)
      for(a<-Seq(3,56,76,92,176,240,304,332,1020)) assert(b.access(a,true,1)._2,"TIMER_EXACT_DECODE")
      b.wr(128,5);b.wr(64,65535)
      for(h<-Seq(0,65535,65536)) {
        b.wr(48,0);b.wr(192,h);b.wr(20,1);b.wr(48,1)
        if(h==65535) {
          val highs=(0 until 65536).count {_=>val v=d.pinsOut.peek().litValue.testBit(0);d.clk.step();v}
          assert(highs==65535,"MAX_DUTY_WIDTH")
        } else for(_<-0 until 32) {assert(d.pinsOut.peek().litValue.testBit(0)==(h!=0));d.clk.step()}
      }
      b.wr(192,65537);b.wr(20,1);assert((b.rd(52)&1)!=0 && b.rd(16)==0,"INVALID_DUTY")
      b.wr(48,0);b.wr(64,999);b.wr(192,300);b.wr(20,1);b.wr(48,1)
      b.wr(192,400);b.wr(20,1);b.wr(192,1)
      d.clk.step(1100)
      val snapshot=(0 until 2000).count {_=>val v=d.pinsOut.peek().litValue.testBit(0);d.clk.step();v}
      assert(snapshot==800,"QUEUED_SNAPSHOT")
      b.wr(32,1);d.clk.step(1100);assert(d.dmaRequest.peek().litValue==1)
      b.wr(36,1);assert(d.dmaRequest.peek().litValue==0,"SOFTWARE_DMA_ACK")
      b.wr(48,0);b.wr(32,0);b.wr(64,1);b.wr(80,65535);b.wr(192,1);b.wr(20,1);b.wr(48,1)
      assert(b.rd(320)==0);d.clk.step(65500);assert(b.rd(320)==0)
      d.clk.step(64);assert(b.rd(320)==1,"MAX_PRESCALER")
      d.reset_n.poke(false.B)
      assert(d.pinsEnable.peek().litValue==0 && d.pinsOut.peek().litValue==0)
    }
  }
}
