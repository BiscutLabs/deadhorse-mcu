package deadhorse.pinmux
import chisel3._
import _root_.circt.stage.ChiselStage
import deadhorse.lib.LocalBus

class PinmuxPadFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val select=IO(Input(UInt(2.W)));val values=IO(Input(UInt(3.W)));val enables=IO(Input(UInt(3.W)))
  val d=Module[PinmuxPad](if(variant=="corrupt") new PinmuxPad {
    override protected def outputEnable(v: Bool): Bool=true.B
  } else new PinmuxPad)
  d.clk:=clock;d.reset_n:=reset_n;d.select:=select;d.values:=values;d.enables:=enables
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val last=RegNext(select,0.U);val older=RegNext(last,0.U)
    val oldValues=RegNext(values);val oldEnables=RegNext(enables)
    if(variant=="cover") {
      for(s<-1 to 3) cover(d.active===s.U && d.enable && d.value)
      cover(d.settling && !d.enable);cover(past && last===0.U && !d.enable)
    } else when(past) {
      assert(d.active===last);assert(d.settling===(last=/=older))
      when(last===0.U || last=/=older) {assert(!d.enable && !d.value)}
      for(s<-1 to 3) when(last===s.U && last===older) {
        assert(d.enable===oldEnables(s-1));assert(d.value===(oldEnables(s-1) && oldValues(s-1)))
      }
    }
  }
}
/** Explicit sampled reset-output check; inter-edge assertion is tested in simulation. */
class PinmuxResetFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val select=IO(Input(UInt(2.W)));val values=IO(Input(UInt(3.W)));val enables=IO(Input(UInt(3.W)))
  val d=Module[PinmuxPad](if(variant=="corrupt") new PinmuxPad {
    override protected def resetEnable: Bool=true.B
  } else new PinmuxPad)
  d.clk:=clock;d.reset_n:=reset_n;d.select:=select;d.values:=values;d.enables:=enables
  withClockAndReset(clock,false.B) {
    if(variant=="cover") {
      cover(!reset_n && !d.enable);cover(reset_n && d.enable && d.value)
    } else when(!reset_n) {
      assert(!d.enable);assert(!d.value);assert(d.active===0.U);assert(!d.settling)
    }
  }
}
class PinmuxDeniedFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val values=IO(Input(Vec(3,UInt(3.W))));val enables=IO(Input(Vec(3,UInt(3.W))))
  val d=Module[Pinmux](if(variant=="corrupt") new Pinmux("build/t24/pinmux/pinmux_regs.json") {
    override protected def allowed(origin: UInt): Bool=true.B
  } else new Pinmux("build/t24/pinmux/pinmux_regs.json"))
  d.clk:=clock;d.reset_n:=reset_n;d.owner:=1.U;d.values:=values;d.enables:=enables;d.bus<>bus
  d.bus.bits.origin:=Mux(bus.bits.origin===1.U,0.U,bus.bits.origin)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val accepted=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") cover(bus.rvalid && bus.err) else {
      assert(bus.rvalid===accepted)
      when(bus.rvalid) {assert(bus.err);assert(bus.rdata===0.U)}
      assert(d.pinsEnable===0.U);assert(d.pinsOut===0.U)
    }
  }
}
object EmitPinmuxFormal extends App {
  require(args.length==2)
  for(v<-Seq("correct","corrupt","cover")) {
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(args(0) match {
      case "pad"=>new PinmuxPadFormal(v)
      case "reset"=>new PinmuxResetFormal(v)
      case "denied"=>new PinmuxDeniedFormal(v)
    }),Array("--target-dir",s"${args(1)}/$v"),Array("--disable-all-randomization","--disable-opt",
      "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
