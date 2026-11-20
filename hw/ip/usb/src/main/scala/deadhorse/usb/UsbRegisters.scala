package deadhorse.usb

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Single application-domain endpoint. Gateway and CPU use the same checked
  * bus; no second consumer can silently race a software POP.
  */
class UsbRegisters(json: String, base: BigInt = 0x40040800L) extends RawModule {
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool())); val bus=IO(new LocalBus)
  val owner=IO(Input(UInt(3.W)))
  val txReady=IO(Input(Bool())); val txPush=IO(Output(Bool())); val txData=IO(Output(UInt(8.W)))
  val rxValid=IO(Input(Bool())); val rxData=IO(Input(UInt(8.W))); val rxPop=IO(Output(Bool()))
  val configured=IO(Input(Bool())); val connected=IO(Input(Bool())); val frame=IO(Input(UInt(11.W)))
  val sessionReset=IO(Input(Bool())); val resume=IO(Input(Bool()))
  val wakeAck=IO(Output(Bool())); val enabled=IO(Output(Bool())); val irq=IO(Output(Bool()))
  protected def allowed(origin: UInt, selected: UInt): Bool = origin === selected
  val regs=Module(new RegBlock(json)); val adapter=Module(new BusRegAdapter(8,base,0))
  regs.clk:=clk;regs.rst_n:=reset_n;adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(allowed(bus.bits.origin,owner),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val push=regs.hw("tx_data_value_we").asBool;val pop=regs.hw("command_rx_pop_pulse").asBool
  txPush:=push;txData:=regs.hw("tx_data_value_wdata");rxPop:=pop
  enabled:=regs.hw("control_enable_q").asBool;wakeAck:=regs.hw("command_wake_ack_pulse").asBool
  regs.hw("rx_data_value_d"):=Mux(rxValid,rxData,0.U)
  regs.hw("status_tx_ready_d"):=txReady.asUInt;regs.hw("status_rx_valid_d"):=rxValid.asUInt
  regs.hw("status_configured_d"):=configured.asUInt;regs.hw("status_connected_d"):=connected.asUInt
  regs.hw("frame_value_d"):=frame
  regs.hw("events_tx_overflow_set"):=(push && !txReady).asUInt
  regs.hw("events_rx_underflow_set"):=(pop && !rxValid).asUInt
  regs.hw("events_session_reset_set"):=sessionReset.asUInt
  regs.hw("events_host_resume_set"):=resume.asUInt
  val event=Seq("tx_overflow","rx_underflow","session_reset","host_resume")
    .map(n=>regs.hw(s"events_${n}_q").asBool).reduce(_||_)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    irq:=RegNext((regs.hw("irq_enable_rx_valid_q").asBool && rxValid) ||
      (regs.hw("irq_enable_events_q").asBool && event),false.B)
  }
}
