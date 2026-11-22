package deadhorse.adc

import chisel3._
import chisel3.util._
import deadhorse.lib._

class Adc(json: String,p: AdcParameters=AdcParameters(),base: BigInt=0) extends RawModule {
  require(p.halfPeriodCycles>=4,"Shared MISO synchronizer and registered pads require at least four half-period edges")
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val owner=IO(Input(UInt(3.W)));val miso=IO(Input(Bool()))
  val sclk=IO(Output(Bool()));val cs_n=IO(Output(Bool()));val pinsEnable=IO(Output(Bool()))
  val irq=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  protected def rawValue(value: UInt): UInt=value
  protected def accessAllowed(origin: UInt,selected: UInt): Bool=origin===selected
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(accessAllowed(bus.bits.origin,owner),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val sync=Module(new CdcSync(1));sync.clk:=clk;sync.reset_n:=reset_n;sync.in:=miso.asUInt
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val engine=Module(new ClockedSpiAdc(p,autonomous=false,rawOnly=true))
    engine.io.miso:=sync.out.asBool
    val enabled=RegInit(false.B);val continuous=RegInit(false.B)
    val gap=RegInit(100000.U(32.W));val remaining=RegInit(0.U(32.W));val launch=RegInit(false.B)
    val apply=regs.hw("command_apply_pulse").asBool;val start=regs.hw("command_start_pulse").asBool
    val readAck=regs.hw("command_read_ack_pulse").asBool
    val busy=engine.io.busy || launch
    val configBad=apply && (start || busy || regs.hw("idle_gap_cycles_q")<=(40*p.halfPeriodCycles).U)
    val applied=apply && !configBad
    val startBad=start && !apply && (!enabled || continuous || busy)
    val manual=start && !apply && !startBad
    val automatic=enabled && continuous && !busy && remaining===0.U && !apply
    launch:=false.B
    when(applied) {
      enabled:=regs.hw("configuration_enable_q").asBool
      continuous:=regs.hw("configuration_continuous_q").asBool
      gap:=regs.hw("idle_gap_cycles_q");remaining:=0.U
    }.elsewhen(!busy && enabled && continuous && remaining=/=0.U) {remaining:=remaining-1.U}
    when(manual || automatic) {launch:=true.B;remaining:=gap-1.U}
    engine.io.start:=launch;engine.io.allow:=enabled
    sclk:=RegNext(engine.io.sclk,false.B);cs_n:=RegNext(engine.io.csN,true.B)
    pinsEnable:=RegNext(enabled,false.B)
    val sample=engine.io.result.valid
    val samples=Module(new AdcSampleState)
    samples.io.sample:=sample;samples.io.readAck:=readAck
    samples.io.value:=rawValue(engine.io.result.bits.value(11,0))
    regs.hw("status_busy_d"):=RegNext(busy,false.B).asUInt
    regs.hw("status_enabled_d"):=enabled.asUInt;regs.hw("status_continuous_d"):=continuous.asUInt
    regs.hw("status_primed_d"):=engine.io.primed.asUInt;regs.hw("status_unread_d"):=samples.io.unread.asUInt
    regs.hw("raw_sample_value_d"):=samples.io.raw;regs.hw("sample_count_value_d"):=samples.io.count
    regs.hw("events_sample_set"):=sample.asUInt
    regs.hw("events_overrun_set"):=samples.io.overrun.asUInt
    regs.hw("events_config_error_set"):=configBad.asUInt
    regs.hw("events_command_error_set"):=startBad.asUInt
    val events=Cat(regs.hw("events_command_error_q"),regs.hw("events_config_error_q"),
      regs.hw("events_overrun_q"),regs.hw("events_sample_q"))
    irq:=RegNext((events & regs.hw("irq_enable_events_q")).orR,false.B)
    clockHold:=RegNext(busy || manual || automatic || (enabled && continuous) ||
      (applied && regs.hw("configuration_enable_q").asBool && regs.hw("configuration_continuous_q").asBool),false.B)
  }
}
