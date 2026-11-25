package deadhorse.sram
import chisel3._
import chisel3.util._
import deadhorse.lib.{ResetRelease,CdcEpoch}

/** Full production sizes, actual independent clocks and reset release cells.
  * Memory read data is arbitrary: ownership must not depend on a passing test. */
class SramOwnershipFormal(fault: Boolean=false) extends RawModule {
  val mainClock=IO(Input(Clock()));val aonClock=IO(Input(Clock()));val observeClock=IO(Input(Clock()))
  val epoch_n=IO(Input(Bool()));val ndm=IO(Input(Bool()));val active=IO(Input(Bool()))
  val cold_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val keyed=IO(Input(Bool()))
  val mainData=IO(Input(UInt(32.W)));val aonData=IO(Input(UInt(32.W)))
  val coldMain=Module(new ResetRelease);val coldAon=Module(new ResetRelease)
  coldMain.clk:=mainClock;coldAon.clk:=aonClock
  coldMain.reset_n:=cold_n;coldAon.reset_n:=cold_n
  val pin=Module(new CdcEpoch(rawCapture=true))
  pin.aClock:=mainClock;pin.bClock:=aonClock
  pin.aReset_n:=coldMain.released;pin.bReset_n:=coldAon.released;pin.cancel_n:=cold_n && epoch_n
  val d=Module(new SramBist(aonWords=512,qualifiedResets=true,sharedPinFence=true))
  d.domainReset.get.main:=coldMain.released;d.domainReset.get.aon:=coldAon.released
  d.pinFence.get.main:=pin.aOpen;d.pinFence.get.aon:=pin.bOpen
  d.clk:=mainClock;d.aonClock:=aonClock;d.epoch_n:=epoch_n;d.cold_n:=cold_n
  d.start:=start;d.keyed:=keyed;d.authorized:=ndm && active
  val main=Module(new ResetRelease);val aon=Module(new ResetRelease)
  main.clk:=mainClock;aon.clk:=aonClock
  val raw=cold_n && epoch_n && !ndm && (if(fault) true.B else !d.resetHold)
  main.reset_n:=raw;aon.reset_n:=raw
  d.mainReset_n:=main.released;d.aonReset_n:=aon.released
  d.main.result:=mainData;d.aon.result:=aonData
  withClockAndReset(observeClock,(!epoch_n).asAsyncReset) {
    assert(!d.resetHold || !main.released && !aon.released)
    assert(!d.main.enable || d.mainOwn && !main.released && d.resetHold)
    assert(!d.aon.enable || d.aonOwn && !aon.released && d.resetHold)
    assert(!d.done || !d.busy && !d.mainOwn && !d.aonOwn)
    cover(d.busy && d.main.enable)
    cover(d.busy && d.aon.enable && !ndm)
  }
}
object EmitSramOwnership extends App {
  for(fault<-Seq(false,true)) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new SramOwnershipFormal(fault)),
    Array("--target-dir",s"${args(0)}/${if(fault) "fault" else "correct"}"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
