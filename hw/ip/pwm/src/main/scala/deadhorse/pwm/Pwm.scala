package deadhorse.pwm

import chisel3._
import chisel3.util._
import deadhorse.lib._

class Pwm(json: String,base: BigInt=0,watchdog: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val owner=IO(Input(UInt(3.W)));val dmaAck=IO(Input(UInt(9.W)))
  val pinsOut=IO(Output(UInt(9.W)));val pinsEnable=IO(Output(UInt(9.W)))
  val dmaRequest=IO(Output(UInt(9.W)));val irq=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  val watchdogReset_n=if(watchdog) Some(IO(Input(Bool()))) else None
  val performanceReady=if(watchdog) Some(IO(Input(Bool()))) else None
  protected def allowed(origin: UInt): Bool=origin===owner
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(allowed(bus.bits.origin),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val executionReset=reset_n && watchdogReset_n.getOrElse(true.B)
  val permitted=if(watchdog) {
    val b=Module(new PwmBreak);b.clk:=clk;b.reset_n:=executionReset
    b.epochReady:=performanceReady.get
    // Drain any already accepted local command before a STOP can acknowledge
    // the break. Surviving DMA only emits APPLY, so cannot clear this latch.
    b.idle:=bus.gnt && !bus.req && !adapter.registers.req_valid &&
      !regs.hw("apply_channels_pulse").orR && !regs.hw("stop_channels_pulse").orR
    b.stop:=regs.hw("stop_channels_pulse");b.permit
  } else 511.U(9.W)
  val channels=(0 until 9).map { i =>
    val c=Module(new PwmChannel);c.clk:=clk;c.reset_n:=executionReset
    c.settings.period:=regs.hw(s"period${i}_value_q")
    c.settings.divider:=regs.hw(s"divider${i}_value_q")
    c.settings.high:=regs.hw(s"high_time${i}_value_q")
    c.apply:=regs.hw("apply_channels_pulse")(i) && permitted(i);c.stop:=regs.hw("stop_channels_pulse")(i)
    c
  }
  pinsOut:=VecInit(channels.map(_.pinOut)).asUInt
  pinsEnable:=VecInit(channels.map(_.enabled)).asUInt
  regs.hw("running_channels_d"):=pinsEnable
  regs.hw("pending_channels_d"):=VecInit(channels.map(_.pending)).asUInt
  val events=VecInit(channels.map(_.rollover)).asUInt
  regs.hw("events_rollover_set"):=events
  regs.hw("events_config_error_set"):=VecInit(channels.map(_.error)).asUInt |
    (regs.hw("apply_channels_pulse") & ~permitted)
  val dma=Module(new PwmDmaRequests);dma.clk:=clk;dma.reset_n:=reset_n
  dma.events:=events;dma.acknowledge:=dmaAck | regs.hw("dma_ack_channels_pulse")
  dma.mask:=regs.hw("dma_enable_channels_q") & pinsEnable & ~regs.hw("stop_channels_pulse")
  dmaRequest:=dma.request;regs.hw("dma_pending_channels_d"):=dma.request
  regs.hw("events_overrun_set"):=dma.overrun
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val sticky=Cat(regs.hw("events_overrun_q"),regs.hw("events_config_error_q"),regs.hw("events_rollover_q"))
    irq:=RegNext((sticky & regs.hw("irq_enable_events_q")).orR,false.B)
    clockHold:=RegNext(pinsEnable.orR || dma.request.orR,false.B)
  }
}
