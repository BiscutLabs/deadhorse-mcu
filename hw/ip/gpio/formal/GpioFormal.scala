package deadhorse.gpio
import chisel3._
import chisel3.util._

class GpioWakeFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val inputs=IO(Input(UInt(3.W)));val command=IO(Input(UInt(9.W)));val valid=IO(Input(Bool()))
  val d=Module[GpioWakeState](if(variant=="corrupt") new GpioWakeState {
    override protected def pendingValue(v: Bool): Bool= !v
  } else new GpioWakeState)
  d.clk:=clock;d.reset_n:=reset_n;d.inputs:=inputs;d.command:=command;d.valid:=valid
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val wasValid=RegNext(valid,false.B)
    val tag=RegNext(command(6),false.B);val oldAck=RegNext(d.ack,false.B)
    val oldPending=RegNext(d.pending,false.B);val cleared=RegNext(valid && command(7),false.B)
    val disarm=RegNext(valid && command(8) && command(7) && command(5,3)===0.U,false.B)
    val applyMatch=RegNext(valid && command(8) && ((~(inputs^command(2,0)))&command(5,3)).orR,false.B)
    if(variant=="cover") {cover(d.pending && d.armed);cover(disarm && !d.pending)}
    else when(past) {
      assert(d.ack===Mux(wasValid,tag,oldAck))
      when(oldPending && !cleared) {assert(d.pending)}
      when(disarm) {assert(!d.pending)}
      when(applyMatch) {assert(d.pending)}
    }
  }
}

class GpioDeniedFormal(json: String,variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new deadhorse.lib.LocalBus)
  val pins=IO(Input(UInt(3.W)))
  val d=Module[Gpio](if(variant=="corrupt") new Gpio(json) {
    override protected def accessAllowed(o: UInt,s: UInt): Bool=true.B
  } else new Gpio(json))
  d.clk:=clock;d.aonClock:=clock;d.reset_n:=reset_n;d.aonReset_n:=reset_n;d.owner:=0.U;d.pinsIn:=pins
  d.bus<>bus;d.bus.bits.origin:=Mux(bus.bits.origin===0.U,1.U,bus.bits.origin)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val accepted=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") {cover(bus.rvalid && bus.err)}
    else {
      assert(bus.rvalid===accepted);when(bus.rvalid) {assert(bus.err);assert(bus.rdata===0.U)}
      assert(d.pinsOut===0.U);assert(d.pinsEnable===0.U);assert(!d.irq);assert(!d.wake)
    }
  }
}
