package deadhorse.timers

import chisel3._
import chisel3.simulator.{ChiselSim,PeekPokeAPI}
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import deadhorse.aon_timer.AonTimers
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class TimerBus(clock: Clock,bus: LocalBus,tag: Int) extends PeekPokeAPI {
  def access(a: Int,w: Boolean=false,v: BigInt=0,be: Int=15,origin: Int=tag): (BigInt,Boolean) = {
    bus.req.poke(true.B);bus.bits.addr.poke(a.U);bus.bits.we.poke(w.B)
    bus.bits.wdata.poke(v.U);bus.bits.be.poke(be.U);bus.bits.origin.poke(origin.U)
    var n=0
    while(!bus.gnt.peek().litToBoolean) {clock.step();n+=1;assert(n<64,"TIMER_GRANT")}
    clock.step();bus.req.poke(false.B)
    while(!bus.rvalid.peek().litToBoolean) {clock.step();n+=1;assert(n<64,"TIMER_REPLY")}
    val r=(bus.rdata.peek().litValue,bus.err.peek().litToBoolean);clock.step(2);r
  }
  def wr(a: Int,v: BigInt,be: Int=15): Unit=assert(!access(a,true,v,be)._2)
  def rd(a: Int): BigInt={val(v,e)=access(a);assert(!e);v}
}
class TimersSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t21/timers/simulation").toAbsolutePath
  }
  private val mainJson="build/t21/timers/timers_regs.json"
  private val aonJson="build/t21/aon_timer/aon_timer_regs.json"
  def init(d: MainTimers): TimerBus = {
    d.reset_n.poke(false.B);d.owner.poke(1.U);d.captureIn.poke(0.U);d.imuDrdy.poke(false.B)
    d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(4)
    d.reset_n.poke(true.B);d.clk.step(4);new TimerBus(d.clk,d.bus,1)
  }
  for(mhz<-Seq(8,9)) test(s"main timer modulo time, compare, capture and stopped-clock contract at $mhz MHz") {
    simulateRaw(new MainTimers(mainJson,mhz)) { d =>
      val b=init(d);assert(d.timeNow.peek().litValue==0 && d.pinsEnable.peek().litValue==0)
      b.wr(4,BigInt("ffffffe0",16));b.wr(8,16);assert(d.timeNow.peek().litValue==BigInt("ffffffe0",16))
      b.wr(0,1);assert(d.clockHold.peek().litToBoolean)
      val before=d.timeNow.peek().litValue;d.clk.step(mhz*7)
      assert(d.timeNow.peek().litValue==((before+7)&BigInt("ffffffff",16)),"TIMER_RATE")
      b.wr(0x20,7);b.wr(0x40,20);b.wr(0x14,1);b.wr(8,1)
      assert(d.pinsEnable.peek().litValue==1 && d.compareOut.peek().litValue==0)
      var edges=0
      while(d.compareOut.peek().litValue==0) {d.clk.step();edges+=1;assert(edges<mhz*60)}
      assert(d.timeNow.peek().litValue==20,"TIMER_WRAP_COMPARE")
      d.clk.step(3);assert(d.irq.peek().litToBoolean && (b.rd(0x10)&1)==1)
      assert((b.rd(0x70)&1)==0);b.wr(0x10,1);d.clk.step(3);assert(!d.irq.peek().litToBoolean)
      // Old/ambiguous targets must reject and leave the held compare output intact.
      b.wr(0x40,0);b.wr(8,1);assert((b.rd(0x10)&0x100)==0x100 && d.compareOut.peek().litValue==1)
      b.wr(0x24,1);b.wr(8,2);d.captureIn.poke(2.U);d.clk.step(6)
      val first=b.rd(0x64);assert(first>20 && (b.rd(0x10)&2)==2)
      d.captureIn.poke(0.U);d.clk.step(6);d.captureIn.poke(2.U);d.clk.step(6)
      assert(b.rd(0x64)>first && (b.rd(0x10)&0x20)==0x20,"TIMER_CAPTURE_OVERRUN")
      d.imuDrdy.poke(true.B);d.clk.step(6);assert(b.rd(0x18)>0 && (b.rd(0x10)&0x1000)==0x1000)
      b.wr(8,16);assert((b.rd(0x10)&0x2000)==0x2000,"TIMER_LIVE_LOAD_REJECTED")
      b.wr(0,0);val stopped=d.timeNow.peek().litValue;d.clk.step(30)
      assert(d.timeNow.peek().litValue==stopped && !d.clockHold.peek().litToBoolean)
      assert(d.pinsEnable.peek().litValue==0 && d.compareOut.peek().litValue==0)
      assert(b.access(0,true,1,origin=0)._2);assert(b.rd(0)==0)
      b.wr(0,1,2);assert(b.rd(0)==0)
      assert(b.access(0x100)._2 && b.access(3)._2 && b.access(0x74)._2)
      d.reset_n.poke(false.B);assert(d.timeNow.peek().litValue==0 && d.pinsEnable.peek().litValue==0)
    }
  }
  test("AON relative deadlines, cancellation, masks, invalid arm and reset") {
    simulateRaw(new AonTimers(aonJson)) { d =>
      d.reset_n.poke(false.B);d.owner.poke(0.U);d.bus.req.poke(false.B)
      d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(4);d.reset_n.poke(true.B);d.clk.step(4)
      val b=new TimerBus(d.clk,d.bus,0)
      b.wr(8,1);b.wr(12,1);b.wr(0x20,100);b.wr(0,1)
      assert((b.rd(16)&1)==1 && d.clockHold.peek().litToBoolean && !d.wake.peek().litToBoolean)
      val remaining=b.rd(0x40);assert(remaining>0 && remaining<100)
      d.clk.step(100);assert(d.wake.peek().litToBoolean && d.irq.peek().litToBoolean)
      assert(b.rd(0x40)==0 && (b.rd(4)&1)==1)
      b.wr(4,1);d.clk.step(3);assert(!d.wake.peek().litToBoolean && !d.clockHold.peek().litToBoolean)
      b.wr(0x24,1000);b.wr(0,2);b.wr(0x24,0);b.wr(0,2)
      assert((b.rd(4)&0x20)==0x20 && b.rd(0x44)>0,"AON_INVALID_ARM_RETAINS_WORK")
      b.wr(0,0x22);assert(b.rd(0x44)==0,"AON_CANCEL_WINS_ARM")
      assert(b.access(0,true,1,origin=1)._2 && b.access(0x100)._2 && b.access(3)._2)
      b.wr(0x28,1);b.wr(0,4);assert((b.rd(4)&4)==4,"AON_ONE_EDGE_DURATION")
      b.wr(0x20,1000);b.wr(0,1);d.reset_n.poke(false.B);d.clk.step()
      assert(!d.wake.peek().litToBoolean && !d.irq.peek().litToBoolean && !d.clockHold.peek().litToBoolean)
    }
  }
  test("time oracle rejects actual counter-output corruption") {
    simulateRaw(new MainTimers(mainJson,8) {override protected def timeValue(v: UInt): UInt=v^1.U}) { d =>
      init(d);intercept[org.scalatest.exceptions.TestFailedException] {assert(d.timeNow.peek().litValue==0,"TIMER_TIME_ORACLE")}
    }
  }
  for(mhz<-Seq(8,9)) test(s"timer APPLY at tick, invalid APPLY at expiry, W1C capture collision at $mhz MHz") {
    simulateRaw(new MainTimers(mainJson,mhz)) { d =>
      val b=init(d);b.wr(0,1);b.wr(0x20,7)
      // Find a public timestamp transition, then place the command's effect
      // on the next tick using the qualified adapter's three-edge write path.
      def tickBoundary(): Unit = {
        val t=d.timeNow.peek().litValue
        while(d.timeNow.peek().litValue==t) d.clk.step()
      }
      var now=d.timeNow.peek().litValue;b.wr(0x40,now+20);b.wr(8,1)
      val target=now+20
      b.wr(0x40,0) // invalid replacement must not cancel the live comparison
      while(d.timeNow.peek().litValue<target-1) d.clk.step()
      // We just reached target-1 on its tick edge.
      d.clk.step(mhz-3);b.wr(8,1)
      assert(d.compareOut.peek().litValue==1 && (b.rd(0x10)&0x101)==0x101,"INVALID_APPLY_ON_EXPIRY")
      b.wr(0x10,0x3fff);b.wr(0x20,0);b.wr(8,1);b.wr(0x20,7)
      // Preload a target, stop one tick before it, and apply on that tick.
      now=d.timeNow.peek().litValue;b.wr(0x40,now+20)
      while(d.timeNow.peek().litValue<now+19) d.clk.step()
      d.clk.step(mhz-3);b.wr(8,1)
      assert(d.pinsEnable.peek().litValue==0 && (b.rd(0x10)&0x100)!=0,"APPLY_USES_TICK_TIMESTAMP")
      b.wr(0x24,1);b.wr(8,2);d.captureIn.poke(2.U);d.clk.step(6)
      assert((b.rd(0x10)&2)!=0);d.captureIn.poke(0.U);d.clk.step(6)
      d.captureIn.poke(2.U);d.clk.step();b.wr(0x10,2)
      assert((b.rd(0x10)&0x22)==0x22,"CAPTURE_WINS_W1C_WITH_OVERRUN")
      b.wr(0,0);b.wr(0,1);d.clk.step(mhz*4)
      assert(d.compareOut.peek().litValue==0 && d.pinsEnable.peek().litValue==0,"RUN_RESTART_NO_REARM")
    }
  }
  test("AON ARM and CANCEL collide with exact expiry edge") {
    simulateRaw(new AonTimers(aonJson)) { d =>
      d.reset_n.poke(false.B);d.owner.poke(0.U);d.bus.req.poke(false.B)
      d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(4);d.reset_n.poke(true.B);d.clk.step(4)
      val b=new TimerBus(d.clk,d.bus,0);b.wr(0x20,8)
      def command(v: Int): Unit = {
        assert(d.bus.gnt.peek().litToBoolean)
        d.bus.req.poke(true.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(true.B)
        d.bus.bits.wdata.poke(v.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
        d.clk.step();d.bus.req.poke(false.B);d.clk.step(2)
        assert(d.bus.rvalid.peek().litToBoolean && !d.bus.err.peek().litToBoolean)
      }
      command(1);d.clk.step(5);command(1) // rearm at expiry: no event
      d.clk.step(5);command(0x11) // cancel+arm at next expiry: cancellation wins
      d.clk.step(2);assert(b.rd(0x40)==0 && (b.rd(4)&1)==0,"AON_EXPIRY_PRIORITY")
    }
  }
}
