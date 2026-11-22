package deadhorse.adc

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage

/** Observe the serial pins, reconstruct the sampled word, then check publication.
  * Inputs and reset are arbitrary after the initial reset sample. */
class AdcRawFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val allow=IO(Input(Bool()));val miso=IO(Input(Bool()))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val d=Module[ClockedSpiAdc](if(variant=="corrupt")
      new ClockedSpiAdc(AdcParameters(halfPeriodCycles=4),autonomous=false,rawOnly=true) {
        override protected def rawResult(v: UInt): UInt=v^1.U
      } else new ClockedSpiAdc(AdcParameters(halfPeriodCycles=4),autonomous=false,rawOnly=true))
    d.io.start:=start;d.io.allow:=allow;d.io.miso:=miso
    val past=RegNext(true.B,false.B)
    val oldClock=RegNext(d.io.sclk,false.B);val oldCs=RegNext(d.io.csN,true.B)
    val oldMiso=RegNext(miso,false.B);val oldDone=RegNext(d.io.done,false.B)
    val oldValue=RegNext(d.io.result.bits.value,0.U)
    val seen=RegInit(false.B);when(d.io.done) {seen:=true.B}
    val rises=RegInit(0.U(5.W));val history=RegInit(0.U(16.W))
    when(oldCs && !d.io.csN) {rises:=0.U;history:=0.U}
      .elsewhen(!oldClock && d.io.sclk) {rises:=rises+1.U;history:=Cat(history(14,0),oldMiso)}
    if(variant=="cover") {
      cover(d.io.done && !seen)
      cover(d.io.result.valid && d.io.result.bits.value===4095.U)
      cover(d.io.result.valid && d.io.result.bits.value===0.U)
    } else {
      assert(d.io.result.valid===(d.io.done && seen))
      assert(!d.io.result.bits.calibrated)
      when(d.io.done) {
        assert(!oldDone)
        assert(d.io.csN && !d.io.sclk && d.io.busy)
        assert(rises===16.U)
        assert(d.io.result.bits.value===history(11,0))
      }
      when(past && !d.io.done) {assert(d.io.result.bits.value===oldValue)}
    }
  }
}
object EmitAdcRawFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","corrupt","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new AdcRawFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
