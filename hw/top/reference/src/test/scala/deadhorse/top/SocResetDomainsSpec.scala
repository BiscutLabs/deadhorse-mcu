package deadhorse.top

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.boot_control.BootResetContext
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** The real release owner and metadata recorder, with independent clocks. */
class SocResetHistoryBench(lateArm: Boolean=false) extends RawModule {
  val aon=IO(Input(Clock()));val main=IO(Input(Clock()))
  val cold=IO(Input(Bool()));val warm=IO(Input(Bool()))
  val aonQualified=IO(Input(Bool()));val mainQualified=IO(Input(Bool()))
  val commit=IO(Input(Bool()))
  val aonUp=IO(Output(Bool()));val mainUp=IO(Output(Bool()))
  val coldUp=IO(Output(Bool()));val fresh=IO(Output(Bool()));val ready=IO(Output(Bool()))
  val initialize=IO(Output(Bool()))
  val d=Module(new SocResetDomains)
  d.aonClock:=aon;d.mainClock:=main;d.sourceClock:=main;d.scanClock:=main
  d.cold_n:=cold;d.warm_n:=warm;d.pin_n:=true.B;d.aonQualified:=aonQualified;d.mainQualified:=mainQualified
  val context=Module(new BootResetContext)
  context.clk:=aon;context.epochReset_n:=d.released.coldAon
  context.warmHold:= !d.released.warmAon
  context.warmReleasePending:=(if(lateArm) false.B else d.released.warmAonPending)
  context.commit:=commit;context.commitKey:=true.B
  aonUp:=d.released.warmAon;mainUp:=d.released.warmMain;coldUp:=d.released.coldAon
  fresh:=context.freshWarmReset;ready:=context.contextReady
  initialize:=d.released.warmInitialize
}

class SocResetDomainsSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/domain-release-simulation").toAbsolutePath
  }
  def exercise(d: SocResetHistoryBench): Unit={
    d.cold.poke(false.B);d.warm.poke(false.B);d.aonQualified.poke(false.B)
    d.mainQualified.poke(false.B);d.commit.poke(false.B)
    d.aon.step(3);d.main.step(3);d.fresh.expect(false.B)
    d.cold.poke(true.B);d.warm.poke(true.B)
    d.aon.step(5);d.main.step(5);d.coldUp.expect(true.B)
    d.aonUp.expect(false.B);d.mainUp.expect(false.B);d.fresh.expect(false.B)
    d.commit.poke(true.B);d.aon.step();d.commit.poke(false.B);d.ready.expect(true.B)
    d.aonQualified.poke(true.B);d.aon.step();d.aonUp.expect(false.B)
    d.aon.step();d.aonUp.expect(true.B);d.fresh.expect(false.B)
    // Pulse immediately after the FIRST release edge, then stop AON. The old
    // output-sampling recorder had not armed yet and lost this warm episode.
    d.mainQualified.poke(true.B);d.main.step(3);d.mainUp.expect(true.B)
    d.warm.poke(false.B);d.aonUp.expect(false.B);d.mainUp.expect(false.B)
    d.warm.poke(true.B);d.main.step(12);d.mainUp.expect(false.B)
    d.aon.step();d.fresh.expect(true.B,"WARM_RELEASE_EDGE_HISTORY_LOST")
    d.ready.expect(true.B);d.aonUp.expect(false.B)
    d.mainQualified.poke(false.B)
    // A new warm episode waits for the cold-owned controller's clear edge,
    // even though the previous episode had already been serviced.
    var n=0
    while(!d.initialize.peek().litToBoolean && n<8) {d.aonUp.expect(false.B);d.aon.step();n+=1}
    assert(n<8,"WARM_ENTRY_CLEAR_LOST")
    d.aon.step();d.aonUp.expect(false.B)
    d.aon.step();d.aonUp.expect(false.B)
    d.aon.step();d.aonUp.expect(true.B)
    d.main.step(6);d.mainUp.expect(false.B,"MAIN_QUALIFICATION_BYPASSED")
    d.mainQualified.poke(true.B);d.main.step();d.mainUp.expect(false.B)
    d.main.step();d.mainUp.expect(true.B)
    d.cold.poke(false.B);d.mainUp.expect(false.B);d.aonUp.expect(false.B)
    d.fresh.expect(false.B);d.ready.expect(false.B)
  }
  test("shared warm release waits for clocks and records the first post-release pulse") {
    simulateRaw(new SocResetHistoryBench)(exercise)
  }
  test("one-edge-late reset-history arming is rejected") {
    val e=intercept[Throwable] {simulateRaw(new SocResetHistoryBench(lateArm=true))(exercise)}
    assert(Iterator.iterate(e)(_.getCause).takeWhile(_!=null)
      .exists(x=>Option(x.getMessage).exists(_.contains("WARM_RELEASE_EDGE_HISTORY_LOST"))))
  }
}
