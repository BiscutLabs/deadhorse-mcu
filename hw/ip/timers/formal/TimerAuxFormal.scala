package deadhorse.timers

import chisel3._
import _root_.circt.stage.ChiselStage
import deadhorse.lib.LocalBus

class TimerDmaFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val events=IO(Input(UInt(9.W)));val mask=IO(Input(UInt(9.W)));val ack=IO(Input(UInt(9.W)))
  val d=Module[TimerDmaRequests](if(variant=="corrupt") new TimerDmaRequests {
    override protected def requestValue(v: UInt): UInt=v ^ 1.U
  } else new TimerDmaRequests)
  d.clk:=clock;d.reset_n:=reset_n;d.events:=events;d.mask:=mask;d.acknowledge:=ack
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val oldEvents=RegNext(events);val oldMask=RegNext(mask)
    val oldAck=RegNext(ack);val oldPending=RegNext(d.request)
    if(variant=="cover") {cover(d.request.orR);cover(d.overrun.orR);cover(oldAck.orR && d.request.orR)}
    else when(past) {
      assert((d.request & ~oldMask)===0.U)
      assert((d.request & oldEvents & oldMask)===(oldEvents & oldMask))
      assert((d.request & oldAck & ~oldEvents)===0.U)
      assert((d.request & ~oldAck & oldMask & ~oldEvents)===(oldPending & ~oldAck & oldMask & ~oldEvents))
      assert(d.overrun===(oldEvents & oldPending & ~oldAck & oldMask))
    }
  }
}

class TimerDeniedFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val d=Module[GeneralTimers](if(variant=="corrupt") new GeneralTimers("build/t21/timers/timers_regs.json") {
    override protected def allowed(origin: UInt): Bool=true.B
  } else new GeneralTimers("build/t21/timers/timers_regs.json"))
  d.clk:=clock;d.reset_n:=reset_n;d.owner:=0.U;d.dmaAck:=0.U;d.bus<>bus;d.captureIn:=0.U;d.captureValid:=0.U
  d.bus.bits.origin:=Mux(bus.bits.origin===0.U,1.U,bus.bits.origin)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val accepted=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") {cover(bus.rvalid && bus.err)}
    else {
      assert(bus.rvalid===accepted)
      when(bus.rvalid) {assert(bus.err);assert(bus.rdata===0.U)}
      assert(d.pinsEnable===0.U);assert(d.pinsOut===0.U);assert(d.irq===0.U);assert(d.dmaRequest===0.U)
    }
  }
}
object EmitTimerAuxFormal extends App {
  require(args.length==2)
  for(v<-Seq("correct","corrupt","cover")) {
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(args(0) match {
      case "dma"=>new TimerDmaFormal(v)
      case "denied"=>new TimerDeniedFormal(v)
    }),Array("--target-dir",s"${args(1)}/$v"),Array("--disable-all-randomization","--disable-opt",
      "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
