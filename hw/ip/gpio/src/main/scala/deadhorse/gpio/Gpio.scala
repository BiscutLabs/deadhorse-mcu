package deadhorse.gpio

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Local AON state; its command port is fed only by the shared FIFO. */
class GpioWakeState extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val inputs=IO(Input(UInt(3.W)));val command=IO(Input(UInt(9.W)));val valid=IO(Input(Bool()))
  val ack=IO(Output(Bool()));val armed=IO(Output(Bool()));val pending=IO(Output(Bool()))
  protected def pendingValue(value: Bool): Bool=value
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val mask=RegInit(0.U(3.W));val polarity=RegInit(0.U(3.W))
    val ackTag=RegInit(false.B);val configured=RegInit(false.B);val wake=RegInit(false.B)
    val apply=valid && command(8);val clear=valid && command(7)
    val useMask=Mux(apply,command(5,3),mask);val usePol=Mux(apply,command(2,0),polarity)
    val matched=((~(inputs ^ usePol)).asUInt & useMask).orR
    when(valid) {ackTag:=command(6);configured:=true.B}
    when(apply) {mask:=command(5,3);polarity:=command(2,0)}
    when(clear) {wake:=false.B}
    when(matched) {wake:=true.B}
    ack:=ackTag;armed:=configured;pending:=pendingValue(wake)
  }
}

/** Atomic wake commands; ACK is a sequence bit, never a bitwise data transfer. */
class GpioWake(qualifiedResets: Boolean=false) extends RawModule {
  val mainClock=IO(Input(Clock()));val aonClock=IO(Input(Clock()))
  val mainReset_n=IO(Input(Bool()));val aonReset_n=IO(Input(Bool()))
  val pins=IO(Input(UInt(3.W)));val mask=IO(Input(UInt(3.W)));val polarity=IO(Input(UInt(3.W)))
  val apply=IO(Input(Bool()));val clear=IO(Input(Bool()))
  val busy=IO(Output(Bool()));val error=IO(Output(Bool()));val ready=IO(Output(Bool()))
  val armed=IO(Output(Bool()));val pendingMain=IO(Output(Bool()));val wake=IO(Output(Bool()))
  val common=mainReset_n && aonReset_n
  def localRelease(clock: Clock,reset: Bool): Bool = if(qualifiedResets) reset else {
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=common;r.released
  }
  val mainUp=localRelease(mainClock,mainReset_n);val aonUp=localRelease(aonClock,aonReset_n)
  val f=Module(new CdcFifo(9,2,qualifiedResets=qualifiedResets));f.writeClock:=mainClock;f.readClock:=aonClock
  f.writeReset_n:=(if(qualifiedResets) mainReset_n else common)
  f.readReset_n:=(if(qualifiedResets) aonReset_n else common);f.pop:=true.B
  val inputSync=Module(new CdcSync(3));inputSync.clk:=aonClock;inputSync.reset_n:=aonUp;inputSync.in:=pins
  val state=Module(new GpioWakeState);state.clk:=aonClock;state.reset_n:=aonUp
  state.inputs:=inputSync.out;state.command:=f.out;state.valid:=f.valid
  def mainSync(value: Bool): Bool = {
    val s=Module(new CdcSync(1));s.clk:=mainClock;s.reset_n:=mainUp;s.in:=value.asUInt;s.out.asBool
  }
  val peerUp=mainSync(f.readUp);val ack=mainSync(state.ack)
  val ackValid=mainSync(state.armed);val pending=mainSync(state.pending)
  wake:=state.pending;armed:=ackValid;pendingMain:=pending
  val reject=WireDefault(false.B)
  // Main MMIO survives peer reset; rejected commands must survive it too.
  error:=withClockAndReset(mainClock,(!mainReset_n).asAsyncReset) {RegNext(reject,false.B)}
  withClockAndReset(mainClock,(!mainUp).asAsyncReset) {
    val waiting=RegInit(false.B);val offer=RegInit(false.B);val tag=RegInit(false.B)
    val packet=RegInit(0.U(9.W));val transportReady=RegInit(false.B)
    val available=f.writeUp && peerUp
    transportReady:=available
    reject:=(apply || clear) && (waiting || !available || !mainUp)
    when(offer && f.ready) {offer:=false.B}
    when(waiting && !offer && ackValid && ack===tag) {waiting:=false.B}
    when(apply || clear) {
      when(!waiting && available) {
        packet:=Cat(apply,clear,!tag,mask,polarity);tag:= !tag;offer:=true.B;waiting:=true.B
      }
    }
    f.push:=offer;f.in:=packet
    busy:=waiting;ready:=transportReady
  }
}

class Gpio(json: String,base: BigInt=0,qualifiedResets: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val aonClock=IO(Input(Clock()))
  val reset_n=IO(Input(Bool()));val aonReset_n=IO(Input(Bool()))
  val bus=IO(new LocalBus);val owner=IO(Input(UInt(3.W)))
  val pinsIn=IO(Input(UInt(3.W)));val pinsOut=IO(Output(UInt(3.W)));val pinsEnable=IO(Output(UInt(3.W)))
  val irq=IO(Output(Bool()));val wake=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  protected def outputValue(value: UInt): UInt=value
  protected def accessAllowed(origin: UInt,selected: UInt): Bool=origin===selected
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(accessAllowed(bus.bits.origin,owner),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val sync=Module(new CdcSync(3));sync.clk:=clk;sync.reset_n:=reset_n;sync.in:=pinsIn
  val w=Module(new GpioWake(qualifiedResets));w.mainClock:=clk;w.aonClock:=aonClock
  w.mainReset_n:=reset_n;w.aonReset_n:=aonReset_n;w.pins:=pinsIn
  w.mask:=regs.hw("wake_mask_pins_q");w.polarity:=regs.hw("wake_polarity_pins_q")
  w.apply:=regs.hw("command_apply_pulse").asBool;w.clear:=regs.hw("command_clear_wake_pulse").asBool
  pinsOut:=outputValue(regs.hw("output_value_pins_q"));pinsEnable:=regs.hw("output_enable_pins_q")
  regs.hw("input_value_pins_d"):=sync.out
  regs.hw("events_command_error_set"):=w.error.asUInt
  regs.hw("status_busy_d"):=w.busy.asUInt;regs.hw("status_armed_d"):=w.armed.asUInt
  regs.hw("status_pending_d"):=w.pendingMain.asUInt;regs.hw("status_ready_d"):=w.ready.asUInt
  wake:=w.wake;clockHold:=w.busy
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val previous=RegNext(sync.out,0.U)
    regs.hw("events_edges_set"):=((sync.out & ~previous)&regs.hw("rise_enable_pins_q")) |
      ((~sync.out & previous)&regs.hw("fall_enable_pins_q"))
    irq:=RegNext((regs.hw("events_edges_q") & regs.hw("irq_enable_edges_q")).orR ||
      (w.pendingMain && regs.hw("irq_enable_wake_q").asBool),false.B)
  }
}
