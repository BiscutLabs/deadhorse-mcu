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
  private val aonJson="build/t21/aon_timer/aon_timer_regs.json"
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
