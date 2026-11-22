package deadhorse.pwm

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Duration-based oracle: time remaining in whole main-clock edges, not RTL counters. */
class PwmReference {
  case class Settings(period: Int, divider: Int, high: Int) {
    def duration: Long=(period.toLong+1)*(divider.toLong+1)
    def highDuration: Long=high.toLong*(divider.toLong+1)
  }
  var active: Option[Settings]=None
  var queued: Option[Settings]=None
  var remaining=0L
  var highRemaining=0L
  var rollover=false
  var error=false
  def start(s: Settings): Unit={active=Some(s);remaining=s.duration;highRemaining=s.highDuration}
  def step(p: Int,div: Int,h: Int,apply: Boolean,stop: Boolean,reset: Boolean=false): Unit={
    rollover=false;error=false
    if(reset || stop) {active=None;queued=None;remaining=0;highRemaining=0}
    else {
      val wasRunning=active.isDefined
      val wasPending=queued.isDefined
      if(wasRunning) {
        remaining-=1;highRemaining=math.max(0L,highRemaining-1)
        if(remaining==0) {rollover=true;start(queued.getOrElse(active.get));queued=None}
      }
      if(apply) {
        if(h>p+1 || wasPending) error=true
        else if(wasRunning) queued=Some(Settings(p,div,h))
        else start(Settings(p,div,h))
      }
    }
  }
}

class PwmChannelSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t22/channel-simulation").toAbsolutePath
  }
  def exercise(d: PwmChannel): Unit={
    val model=new PwmReference
    def edge(p: Int=7,div: Int=1,h: Int=3,apply: Boolean=false,stop: Boolean=false,rst: Boolean=false): Unit={
      d.reset_n.poke((!rst).B);d.settings.period.poke(p.U);d.settings.divider.poke(div.U)
      d.settings.high.poke(h.U);d.apply.poke(apply.B);d.stop.poke(stop.B)
      model.step(p,div,h,apply,stop,rst);d.clk.step()
      assert(d.enabled.peek().litToBoolean==model.active.isDefined,"PWM_ENABLE")
      assert(d.pinOut.peek().litToBoolean==(model.highRemaining>0),"PWM_WAVEFORM")
      assert(d.pending.peek().litToBoolean==model.queued.isDefined,"PWM_PENDING")
      assert(d.rollover.peek().litToBoolean==model.rollover,"PWM_PERIOD")
      assert(d.error.peek().litToBoolean==model.error,"PWM_REJECT")
    }
    edge(rst=true);edge(apply=true)
    edge(p=2,div=2,h=3,apply=true)
    // A queued snapshot must survive unrelated changing input values and busy APPLY.
    for(i<-0 until 40) edge(p=i%11,div=i%3,h=i%14,apply=i<17)
    edge(stop=true,apply=true);edge(p=0,div=0,h=1,apply=true)
    edge(p=1,div=0,h=0,apply=true);edge(p=4,div=0,h=2,apply=true)
    for(_<-0 until 12) edge()
    val random=new scala.util.Random(0x22b00fL)
    for(_<-0 until 4000) edge(random.nextInt(20),random.nextInt(5),random.nextInt(24),
      random.nextInt(7)==0,random.nextInt(79)==0,random.nextInt(257)==0)
    edge(stop=true)
    for(h<-Seq(0,65535,65536,65537)) {
      edge(65535,0,h,apply=true)
      // Bulk stepping is checked against the independent duration oracle at endpoints.
      for(_<-0 until 65535) model.step(0,0,0,false,false)
      d.apply.poke(false.B);d.clk.step(65535)
      assert(d.pinOut.peek().litToBoolean==(model.highRemaining>0),"PWM_MAX_HIGH")
      edge(0,0,0);edge(stop=true)
    }
    edge(0,65535,1,apply=true)
    for(_<-0 until 65535) model.step(0,0,0,false,false)
    d.apply.poke(false.B);d.clk.step(65535);edge(0,0,0)
    edge(rst=true)
  }
  test("independent duration model, updates, collisions, resets and width endpoints; seed 0x22b00f") {
    simulateRaw(new PwmChannel) {d=>exercise(d)}
  }
  test("the duration oracle rejects an actual pinOut fault") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new PwmChannel {override protected def outputValue(v: Bool): Bool= !v}) {d=>exercise(d)}
    }
    assert(failure.getMessage.contains("PWM_WAVEFORM"))
  }
}
