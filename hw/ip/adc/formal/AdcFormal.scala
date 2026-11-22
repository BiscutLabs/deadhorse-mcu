package deadhorse.adc
import chisel3._
import chisel3.util._

/** A single arbitrary sample, captured at start, checked after twelve steps. */
class AdcScaleFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val sample=IO(Input(UInt(12.W)))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val d=Module[ClockedSampleScaler](if(variant=="corrupt") new ClockedSampleScaler(25300,4095) {
      override protected def resultValue(v: UInt): UInt=v^1.U
    } else new ClockedSampleScaler(25300,4095))
    val age=RegInit(0.U(5.W));when(age=/=31.U) {age:=age+1.U}
    val captured=RegEnable(sample,0.U,age===0.U)
    d.io.start:=age===0.U;d.io.raw:=sample
    if(variant=="cover") {cover(d.io.done && captured===4095.U)}
    else {
      assert(d.io.done===(age===12.U))
      when(d.io.done) {assert(d.io.value===(captured*25300.U)/4095.U)}
    }
  }
}
class AdcDeniedFormal(json: String,variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new deadhorse.lib.LocalBus)
  val miso=IO(Input(Bool()))
  val d=Module[Adc](if(variant=="corrupt") new Adc(json) {
    override protected def accessAllowed(o: UInt,s: UInt): Bool=true.B
  } else new Adc(json))
  d.clk:=clock;d.reset_n:=reset_n;d.owner:=0.U;d.miso:=miso;d.bus<>bus
  d.bus.bits.origin:=Mux(bus.bits.origin===0.U,1.U,bus.bits.origin)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val accepted=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") {cover(bus.rvalid && bus.err)}
    else {
      assert(bus.rvalid===accepted);when(bus.rvalid) {assert(bus.err);assert(bus.rdata===0.U)}
      assert(!d.pinsEnable);assert(d.cs_n);assert(!d.sclk);assert(!d.irq)
    }
  }
}
