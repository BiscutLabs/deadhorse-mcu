package deadhorse.watchdog

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Absolute deadlines, independent of the implementation's down counters. */
class WatchdogReference {
  var now=0L;var deadline: Option[Long]=None;var earliest=0L
  var period=0L;var window=0L;var warning=0L;var resetUntil=0L
  var cause=false;var crashes=0L;var error=false
  def remaining: Long=deadline.map(_-now).getOrElse(0L)
  def held: Boolean=now<resetUntil
  def warned: Boolean=deadline.isDefined && warning>0 && remaining<=warning
  def step(p: Long,w: Long,n: Long,start: Boolean,feed: Boolean,epoch: Boolean,por: Boolean): Unit={
    val oldHeld=held;val oldRemaining=remaining
    now+=1;error=false
    if(por) {deadline=None;resetUntil=now;cause=false;crashes=0}
    else {
      if(epoch) deadline=None
      else if(oldHeld) error=start || feed
      else if(deadline.isDefined) {
        val early=feed && !start && now<earliest
        if(oldRemaining==1 || early) {
          deadline=None;resetUntil=now+4;cause=true;crashes=math.min(0xffffffffL,crashes+1)
        } else if(feed && !start) {deadline=Some(now+period);earliest=now+window}
        error=start
      } else if(start && !feed && p>0 && w<p && n<p) {
        period=p;window=w;warning=n;deadline=Some(now+p);earliest=now+w
      } else error=start || feed
    }
  }
}

class WatchdogSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t26/channel-simulation").toAbsolutePath
  }
  def exercise(d: WatchdogChannel): Unit={
    val m=new WatchdogReference
    def edge(p: Long=19,w: Long=4,n: Long=3,s: Boolean=false,f: Boolean=false,e: Boolean=false,r: Boolean=false): Unit={
      d.por_n.poke((!r).B);d.reset_n.poke((!e && !r).B)
      d.period.poke(p.U);d.window.poke(w.U);d.warning.poke(n.U);d.start.poke(s.B);d.feed.poke(f.B)
      m.step(p,w,n,s,f,e,r);d.clk.step()
      assert(d.active.peek().litToBoolean==m.deadline.isDefined,"WATCHDOG_ACTIVE")
      assert(d.remaining.peek().litValue==m.remaining,"WATCHDOG_DEADLINE")
      assert(d.warn.peek().litToBoolean==m.warned,"WATCHDOG_WARNING")
      assert(d.resetHold.peek().litToBoolean==m.held,"WATCHDOG_HOLD")
      assert(d.cause.peek().litToBoolean==m.cause,"WATCHDOG_CAUSE")
      assert(d.crashes.peek().litValue==m.crashes,"WATCHDOG_COUNT")
      assert(d.error.peek().litToBoolean==m.error,"WATCHDOG_COMMAND")
    }
    edge(r=true);edge(s=true)
    for(_<-0 until 5) edge();edge(f=true)
    // START/shadow changes cannot postpone the immutable active deadline.
    for(_<-0 until 20) edge(p=0xffffffffL,w=0,n=0,s=true)
    for(_<-0 until 5) edge(e=true)
    // A feed at the exact elapsed-edge window boundary is legal.
    edge(p=19,w=1,s=true);edge(f=true);edge(e=true)
    edge(p=19,w=4,s=true);for(_<-0 until 3) edge();edge(f=true);edge(e=true)
    edge(s=true);edge(f=true) // early feed resets
    for(_<-0 until 4) edge(e=true) // own reset cannot truncate hold/cause
    edge(p=2,w=0,n=1,s=true);edge();edge(f=true) // late feed loses to expiry
    for(_<-0 until 5) edge()
    edge(p=0xffffffffL,w=0,n=0xfffffffeL,s=true)
    for(_<-0 until 4) edge();edge(f=true);edge(e=true)
    val random=new scala.util.Random(0x26a0L)
    for(_<-0 until 3000) edge(random.nextInt(25),random.nextInt(10),random.nextInt(10),
      random.nextInt(6)==0,random.nextInt(5)==0,random.nextInt(113)==0,random.nextInt(997)==0)
  }
  test("absolute deadline oracle, immutable settings, feed windows and independent reset; seed 0x26a0") {
    simulateRaw(new WatchdogChannel) {d=>exercise(d)}
  }
  test("oracle rejects a watchdog that accepts an early feed") {
    val failed=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new WatchdogChannel {override protected def earlyViolation(v: Bool): Bool=false.B}) {d=>exercise(d)}
    }
    assert(failed.getMessage.contains("WATCHDOG_ACTIVE"))
  }
  private def retainedCause(d: WatchdogChannel): Unit={
    d.por_n.poke(false.B);d.reset_n.poke(false.B)
    d.period.poke(2.U);d.window.poke(0.U);d.warning.poke(0.U)
    d.start.poke(false.B);d.feed.poke(false.B);d.clk.step(2)
    d.por_n.poke(true.B);d.reset_n.poke(true.B)
    d.start.poke(true.B);d.clk.step();d.start.poke(false.B);d.clk.step(8)
    // Finish an actual expiry AND its hold before testing retention. A fault
    // during the first expiry could otherwise fail only a crash-count check.
    assert(d.cause.peek().litToBoolean && d.crashes.peek().litValue==1 &&
      !d.resetHold.peek().litToBoolean,"WATCHDOG_CAUSE_PRECONDITION")
    d.reset_n.poke(false.B)
    assert(d.cause.peek().litToBoolean,"WATCHDOG_WARM_CAUSE_LOST")
    d.clk.step(3);assert(d.cause.peek().litToBoolean,"WATCHDOG_WARM_CAUSE_LOST")
    d.reset_n.poke(true.B);d.clk.step()
    assert(d.cause.peek().litToBoolean && d.crashes.peek().litValue==1,"WATCHDOG_CAUSE_RELEASE")
    d.por_n.poke(false.B);assert(!d.cause.peek().litToBoolean,"WATCHDOG_COLD_CAUSE_CLEAR")
  }
  test("a latched cause survives warm assertion and release, and cold clears it") {
    simulateRaw(new WatchdogChannel)(retainedCause)
  }
  test("warm clearing an already latched cause is rejected specifically") {
    val failed=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new WatchdogChannel {
        override protected def retainedReset: Bool=por_n && reset_n
      })(retainedCause)
    }
    assert(failed.getMessage.contains("WATCHDOG_WARM_CAUSE_LOST"))
  }
}
