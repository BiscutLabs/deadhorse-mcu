package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** T34 port-level checks. Time and voltages are model assumptions, not silicon. */
class AnalogContractSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t34/contract-simulation").toAbsolutePath
  }
  def lfTimeline(d: LfRcModel): Unit={
    for(code<-0 until 64;testMode<-Seq(false,true)) {
      d.trim.poke(code.U);d.test.poke(testMode.B)
      d.enable.poke(false.B);d.power_n.poke(false.B);d.source.step(2)
      assert(!d.ready.peek().litToBoolean,"LF_EARLY_READY")
      d.power_n.poke(true.B);d.source.step(5);d.ready.expect(false.B)
      d.enable.poke(true.B)
      for(_<-0 until 3) {d.source.step();assert(!d.ready.peek().litToBoolean,"LF_EARLY_READY")}
      d.source.step();d.ready.expect(true.B)
      // External simulation source stops low, then restarts. enable is not a gate.
      d.enable.poke(false.B);d.source.step();d.ready.expect(false.B)
      // step() ends low; leave source idle here (no synthetic gate).
      d.enable.poke(true.B);d.ready.expect(false.B) // no source edges: no readiness
      for(_<-0 until 3) {d.source.step();d.ready.expect(false.B)}
      d.source.step();d.ready.expect(true.B)
      d.power_n.poke(false.B);d.ready.expect(false.B) // loss between source edges
    }
  }
  test("LF startup restart and every reserved trim code preserve qualification") {
    simulateRaw(new LfRcModel)(lfTimeline)
  }
  test("wrong-ready fault is rejected by the LF timeline") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new LfRcModel {
        override protected def qualifiedReady(value: Bool): Bool=true.B
      })(lfTimeline)
    }
    assert(failure.getMessage.contains("LF_EARLY_READY"))
  }

  // Independent specification oracle: collect consecutive valid observations.
  // This is intentionally a history of samples, not the implementation counter.
  def porTimeline(d: PorBrownoutModel,edges: Int): Unit={
    val random=new scala.util.Random(340087L)
    var history=Vector.empty[Int];var released=false;var powered=false;var brown=false
    var previous=0;var activeMv=0
    d.threshold.poke(0.U);d.test.poke(false.B);d.supplyMv.poke(0.U);d.reference.step(2)
    def sample(mv: Int,code: Int,mode: Boolean): Unit={
      val limits=if(code==1) (3200,3300) else (3100,3200)
      def asynchronous(voltage: Int): Unit={
        if(voltage<limits._1) {released=false;history=Vector.empty;previous=0}
        if(voltage<100) {powered=false;brown=false}
      }
      d.test.poke(mode.B);d.threshold.poke(code.U);asynchronous(activeMv)
      assert(d.supplyReset_n.peek().litToBoolean==released,
        s"POR_ASYNC_SELECTION voltage=$activeMv code=$code")
      d.supplyMv.poke(mv.U);asynchronous(mv);activeMv=mv
      assert(d.supplyReset_n.peek().litToBoolean==released,s"POR_ASYNC_ASSERTION voltage=$mv code=$code")
      // power/brown registers sample the pre-edge release state.
      val wasReleased=released
      if(mv>=100) {if(powered && !wasReleased) brown=true;if(wasReleased) powered=true}
      if(mv>=limits._1 && !released) {
        if(mv<limits._2) history=Vector.empty
        else {if(code!=previous) history=Vector.empty;history=history:+code}
        if(history.size>=edges) released=true
      }
      if(mv>=limits._1) previous=code
      d.reference.step()
      assert(d.supplyReset_n.peek().litToBoolean==released,"POR_RELEASE_TIMELINE")
      d.powerOn_n.expect(powered.B);d.brownout.expect(brown.B)
    }
    for(code<-0 until 4;mode<-Seq(false,true)) {
      sample(0,code,mode)
      val rise=if(code==1)3300 else 3200
      val fall=rise-100
      // Noisy ramp never accumulates non-consecutive valid samples.
      for(_<-0 until 3) {for(_<-0 until edges-1) sample(rise,code,mode);sample(rise-1,code,mode)}
      for(_<-0 until edges+2) sample(rise,code,mode)
      sample(fall,code,mode);sample(fall+1,code,mode);sample(fall-1,code,mode)
      for(_<-0 until edges+2) sample(rise,code,mode)
    }
    for(_<-0 until 500) {
      val code=random.nextInt(4)
      sample(Vector(0,99,100,3099,3100,3199,3200,3299,3300,3400)(random.nextInt(10)),code,random.nextBoolean())
    }
    println(s"T34_POR_TIMELINE seed=340087 releaseEdges=$edges")
  }
  for(edges<-Seq(1,8,1000)) test(s"POR independent timeline and reserved inputs releaseEdges=$edges") {
    simulateRaw(new PorBrownoutModel(edges))(d=>porTimeline(d,edges))
  }
  test("early-release fault is rejected by the independent POR timeline") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new PorBrownoutModel(7))(d=>porTimeline(d,8))
    }
    assert(failure.getMessage.contains("POR_RELEASE_TIMELINE"))
  }
  test("sub-reference pulse asserts reset and restarts release without promising cause capture") {
    simulateRaw(new PorBrownoutModel(8)) {d=>
      d.test.poke(false.B);d.threshold.poke(0.U);d.supplyMv.poke(0.U);d.reference.step(2)
      d.supplyMv.poke(3300.U);d.reference.step(10);d.powerOn_n.expect(true.B)
      d.supplyMv.poke(3099.U);d.supplyReset_n.expect(false.B)
      d.supplyMv.poke(3300.U);d.supplyReset_n.expect(false.B)
      // No reference edge during the dip; reset remains held so the next edge
      // observes it. Below the initial-power threshold, cause state clears.
      d.reference.step();d.brownout.expect(true.B)
      d.reference.step(6);d.supplyReset_n.expect(false.B)
      d.reference.step();d.supplyReset_n.expect(true.B)
      d.supplyMv.poke(99.U);d.powerOn_n.expect(false.B);d.brownout.expect(false.B)
    }
  }
}
