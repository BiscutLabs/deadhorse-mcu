package deadhorse.sram
import chisel3._
import chisel3.util._
import deadhorse.lib.ResetRelease

/** Full production sizes, actual independent clocks and reset release cells.
  * Memory read data is arbitrary: ownership must not depend on a passing test. */
class SramOwnershipFormal(fault: Boolean=false) extends RawModule {
  val mainClock=IO(Input(Clock()));val aonClock=IO(Input(Clock()));val observeClock=IO(Input(Clock()))
  val epoch_n=IO(Input(Bool()));val ndm=IO(Input(Bool()));val active=IO(Input(Bool()))
  val start=IO(Input(Bool()));val keyed=IO(Input(Bool()))
  val mainData=IO(Input(UInt(32.W)));val aonData=IO(Input(UInt(32.W)))
  val d=Module(new SramBist)
  d.clk:=mainClock;d.aonClock:=aonClock;d.epoch_n:=epoch_n
  d.start:=start;d.keyed:=keyed;d.authorized:=ndm && active
  val main=Module(new ResetRelease);val aon=Module(new ResetRelease)
  main.clk:=mainClock;aon.clk:=aonClock
  val raw=epoch_n && !ndm && (if(fault) true.B else !d.resetHold)
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
