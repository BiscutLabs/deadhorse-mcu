package deadhorse.top

import chisel3._
import chisel3.reflect.DataMirror
import deadhorse.lib._
import deadhorse.bus.{BusFabric, BusRegion}
import deadhorse.perf_core.IbexTop
import deadhorse.uart.Uart

/** I0 assembly. Missing endpoints return fabric errors; I1 is not implemented. */
class DeadhorseSoc(config: String, uartJson: String, romImage: String,
                   gateTarget: ClockGateTarget = ClockGateTarget.Model,
                   readLatency: Int = 1, banks: Int = 4) extends RawModule {
  val mainClock = IO(Input(Clock()))
  val coldReset_n = IO(Input(Bool())); val warmReset_n = IO(Input(Bool()))
  val mainServiceReset_n = IO(Input(Bool())); val mainCoreReset_n = IO(Input(Bool()))
  val uartRx = IO(Input(Bool())); val uartTx = IO(Output(Bool()))
  // I0 uses an externally running main clock. This is UART demand only,
  // never permission to stop the complete SoC clock.
  val uartTxEnable = IO(Output(Bool())); val clockHold = IO(Output(Bool()))
  val coreReady = IO(Output(Bool())); val coreSleeping = IO(Output(Bool()))
  val description = new SocDescription(config)
  val serviceRelease = Module(new ResetRelease)
  serviceRelease.clk := mainClock
  serviceRelease.reset_n := coldReset_n && warmReset_n && mainServiceReset_n
  val coreRelease = Module(new ResetRelease)
  coreRelease.clk := mainClock
  coreRelease.reset_n := coldReset_n && warmReset_n && mainServiceReset_n && mainCoreReset_n

  val memory = Module(new SocLocalMemory(description, romImage, banks, readLatency))
  memory.clk := mainClock; memory.serviceReset_n := serviceRelease.released
  memory.clientReset_n := coreRelease.released
  coreReady := memory.epochReady
  val core = Module(new IbexTop(gateTarget, WithRVFI=true, RegisteredExecution=false, WithF=true))
  core.clk_i := mainClock; core.rst_ni := coreRelease.released
  core.test_en_i := false.B; core.scan_rst_ni := true.B; core.ram_cfg_i := 0.U
  core.instr_rdata_intg_i := 0.U; core.data_rdata_intg_i := 0.U
  core.scramble_key_valid_i := false.B; core.scramble_key_i := 0.U; core.scramble_nonce_i := 0.U
  for((_, port) <- core.ports if DataMirror.directionOf(port) == ActualDirection.Input) {
    port := 0.U.asTypeOf(port)
  }
  core.ports("hart_id_i") := 1.U
  core.ports("boot_addr_i") := description.region("boot_rom").base.U
  core.ports("fetch_enable_i") := Mux(memory.epochReady, 5.U, 10.U)
  coreSleeping := core.core_sleep_o
  val rvfi = core.ports.toSeq.filter(_._1.startsWith("rvfi_")).map { case(name, signal) =>
    val out = IO(chiselTypeOf(signal)).suggestName(name)
    out := signal; name -> out
  }.toMap
  def flag(name: String): Bool = core.ports(name).asUInt.asBool
  def word(name: String): UInt = core.ports(name).asUInt
  memory.instruction.req := flag("instr_req_o")
  memory.instruction.bits.addr := word("instr_addr_o")
  memory.instruction.bits.we := false.B; memory.instruction.bits.be := 15.U
  memory.instruction.bits.wdata := 0.U
  memory.instruction.bits.origin := description.origin("performance").U
  memory.data.req := flag("data_req_o")
  memory.data.bits.addr := word("data_addr_o"); memory.data.bits.we := flag("data_we_o")
  memory.data.bits.be := word("data_be_o"); memory.data.bits.wdata := word("data_wdata_o")
  memory.data.bits.origin := description.origin("performance").U
  for((prefix, bus) <- Seq(("instr", memory.instruction), ("data", memory.data))) {
    core.ports(prefix + "_gnt_i") := bus.gnt
    core.ports(prefix + "_rvalid_i") := bus.rvalid
    core.ports(prefix + "_rdata_i") := bus.rdata
    core.ports(prefix + "_err_i") := bus.err
  }

  val uartRegion = description.region("uart0")
  val fabric = Module(new BusFabric(1, Seq(BusRegion(uartRegion.base, uartRegion.size))))
  fabric.clk := mainClock; fabric.reset_n := serviceRelease.released
  fabric.master(0) <> memory.peripheral
  fabric.allow(0) := true.B; fabric.admit(0) := true.B
  // A retained endpoint is never reopened by a fictitious quiescent pulse.
  // A late response drains quarantine, or common service reset resets both.
  fabric.quiescent(0) := false.B
  val uart = Module(new Uart(uartJson, base=uartRegion.base))
  uart.clk := mainClock; uart.reset_n := serviceRelease.released
  uart.bus <> fabric.target(0); uart.owner := description.origin("performance").U
  uart.rx := uartRx; uart.sleepRequest := false.B; uart.sleepMode := 0.U
  uartTx := uart.tx; uartTxEnable := uart.txEnable; clockHold := uart.clockHold
  core.ports("irq_fast_i") := uart.irq.asUInt << description.interrupt("uart0")
}
