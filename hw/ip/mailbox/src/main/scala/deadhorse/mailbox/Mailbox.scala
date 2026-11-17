package deadhorse.mailbox

import chisel3._
import deadhorse.lib._

class MailboxEndpoint(json: String, owner: Int, base: BigInt = BigInt("40001000",16)) extends RawModule {
  protected def readHead(value: UInt): UInt = value
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new LocalBus)
  val txPush = IO(Output(Bool())); val txData = IO(Output(UInt(32.W)))
  val txReady = IO(Input(Bool())); val txUp = IO(Input(Bool()))
  val rxPop = IO(Output(Bool())); val rxData = IO(Input(UInt(32.W)))
  val rxValid = IO(Input(Bool())); val rxUp = IO(Input(Bool()))
  val irq = IO(Output(Bool()))
  val regs = Module(new RegBlock(json)); val adapter = Module(new BusRegAdapter(8,base,owner))
  regs.clk := clk; regs.rst_n := reset_n
  adapter.clk := clk; adapter.reset_n := reset_n; adapter.bus <> bus; regs.bus <> adapter.registers
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val staging = RegInit(0.U(32.W))
    when(regs.hw("tx_data_value_we").asBool) { staging := regs.hw("tx_data_value_wdata") }
    txData := staging; txPush := regs.hw("command_push_pulse").asBool
    rxPop := regs.hw("command_pop_pulse").asBool
    val ready = txUp && rxUp
    regs.hw("rx_data_value_d") := Mux(rxValid && ready, readHead(rxData), 0.U)
    regs.hw("status_tx_ready_d") := (txReady && ready).asUInt
    regs.hw("status_rx_valid_d") := (rxValid && ready).asUInt
    regs.hw("status_link_ready_d") := ready.asUInt
    regs.hw("events_overflow_set") := (regs.hw("command_push_pulse").asBool && (!txReady || !ready)).asUInt
    regs.hw("events_underflow_set") := (regs.hw("command_pop_pulse").asBool && (!rxValid || !ready)).asUInt
    val armed = RegInit(false.B)
    when(ready) { armed := true.B }
    when(!ready) { armed := false.B }
    regs.hw("events_peer_reset_set") := (armed && !ready).asUInt
    irq := rxValid // registered FIFO head-valid; reset flush clears it asynchronously
  }
}

class Mailbox(json: String) extends RawModule {
  protected def endpoint(owner: Int): MailboxEndpoint = new MailboxEndpoint(json,owner)
  val aonClock = IO(Input(Clock())); val mainClock = IO(Input(Clock()))
  val aonReset_n = IO(Input(Bool())); val mainReset_n = IO(Input(Bool()))
  val aon = IO(new LocalBus); val main = IO(new LocalBus)
  val irq = IO(Output(Vec(2,Bool()))); val wakePeer = IO(Output(Vec(2,Bool())))
  val ar = Module(new ResetRelease); val mr = Module(new ResetRelease)
  ar.clk := aonClock; mr.clk := mainClock; ar.reset_n := aonReset_n; mr.reset_n := mainReset_n
  val a = Module(endpoint(0)); val m = Module(endpoint(1))
  a.clk := aonClock; m.clk := mainClock; a.reset_n := ar.released; m.reset_n := mr.released
  a.bus <> aon; m.bus <> main
  val am = Module(new CdcFifo(32)); val ma = Module(new CdcFifo(32))
  am.writeClock := aonClock; am.readClock := mainClock; ma.writeClock := mainClock; ma.readClock := aonClock
  am.writeReset_n := aonReset_n; am.readReset_n := mainReset_n
  ma.writeReset_n := mainReset_n; ma.readReset_n := aonReset_n
  am.push := a.txPush; am.in := a.txData; a.txReady := am.ready; a.txUp := am.writeUp
  ma.push := m.txPush; ma.in := m.txData; m.txReady := ma.ready; m.txUp := ma.writeUp
  a.rxData := ma.out; a.rxValid := ma.valid; a.rxUp := ma.readUp; ma.pop := a.rxPop
  m.rxData := am.out; m.rxValid := am.valid; m.rxUp := am.readUp; am.pop := m.rxPop
  irq(0) := a.irq; irq(1) := m.irq; wakePeer(0) := am.writePending; wakePeer(1) := ma.writePending
}
