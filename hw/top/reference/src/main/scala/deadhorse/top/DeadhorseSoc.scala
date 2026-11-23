package deadhorse.top

import chisel3._
import chisel3.reflect.DataMirror
import deadhorse.lib._
import deadhorse.bus.{BusFabric, BusRegion}
import deadhorse.perf_core.IbexTop
import deadhorse.uart.Uart

/** Shared core/local-memory assembly, with optional complete I1 peripheral wiring. */
class SocCoreAssembly(config: String, uartJson: String, romImage: String,
                   gateTarget: ClockGateTarget = ClockGateTarget.Model,
                   readLatency: Int = 1, banks: Int = 4,
                   verificationFixture: Boolean = false, ramImages: Seq[String] = Seq.empty,
                   i1Config: Option[SocI1Config] = None) extends RawModule {
  protected def bootPermit(released: Bool): Bool=released
  protected def debugRequest(request: Bool): Bool=request
  require(verificationFixture || ramImages.isEmpty, "Preloaded SRAM is verification-only")
  require(!verificationFixture || i1Config.isEmpty,"QEMU fixture is the preserved I0 configuration")
  val mainClock = IO(Input(Clock()))
  val coldReset_n = IO(Input(Bool())); val warmReset_n = IO(Input(Bool()))
  val mainServiceReset_n = IO(Input(Bool())); val mainCoreReset_n = IO(Input(Bool()))
  val uartRx = IO(Input(Bool())); val uartTx = IO(Output(Bool()))
  // I0 uses an externally running main clock. This is UART demand only,
  // never permission to stop the complete SoC clock.
  val uartTxEnable = IO(Output(Bool())); val clockHold = IO(Output(Bool()))
  val coreReady = IO(Output(Bool())); val coreSleeping = IO(Output(Bool()))
  val description = new SocDescription(config)
  val i1 = i1Config.map(_=>IO(new SocI1Pins))
  val watchdogCoreReset=WireDefault(false.B);val watchdogWholeReset=WireDefault(false.B)
  val bootReleased=WireDefault(true.B)
  val debugGrant=WireDefault(false.B);val debugFetch=WireDefault(false.B);val debugHalt=WireDefault(false.B);val debugReset=WireDefault(false.B)
  require(!i1Config.exists(_.bootControl.isDefined) || i1Config.exists(_.liteCore),
    "Production boot release requires the real lite core")
  val serviceRelease = Module(new ResetRelease)
  serviceRelease.clk := mainClock
  serviceRelease.reset_n := coldReset_n && warmReset_n && mainServiceReset_n && !watchdogWholeReset && !debugReset
  val coreRelease = Module(new ResetRelease)
  coreRelease.clk := mainClock
  coreRelease.reset_n := coldReset_n && warmReset_n && mainServiceReset_n && mainCoreReset_n &&
    !watchdogWholeReset && !watchdogCoreReset && !debugReset && (bootPermit(bootReleased) || debugGrant)

  val memory = Module(new SocLocalMemory(description, romImage, banks, readLatency, ramImages,
    dmaEnabled=i1Config.exists(_.dma.isDefined),xipEnabled=i1Config.exists(_.xip),debugEnabled=i1Config.nonEmpty))
  memory.clk := mainClock; memory.serviceReset_n := serviceRelease.released
  memory.clientReset_n := coreRelease.released
  coreReady := memory.epochReady
  // Passive verification pins; absent from the production interface.
  val memoryTrace = if(verificationFixture) Some(IO(Output(new Bundle {
    val iReq=Bool(); val iGnt=Bool(); val iAddr=UInt(32.W); val iValid=Bool()
    val dReq=Bool(); val dGnt=Bool()
  }))) else None
  memoryTrace.foreach { t =>
    t.iReq:=memory.instruction.req; t.iGnt:=memory.instruction.gnt
    t.iAddr:=memory.instruction.bits.addr; t.iValid:=memory.instruction.rvalid
    t.dReq:=memory.data.req; t.dGnt:=memory.data.gnt
  }
  val core = Module(new IbexTop(gateTarget, WithRVFI=true, RegisteredExecution=false, WithF=true,
    DmHaltAddr=if(i1Config.nonEmpty) description.region("debug_mem").base+0x800 else BigInt("1a110800",16),
    DmExceptionAddr=if(i1Config.nonEmpty) description.region("debug_mem").base+0x810 else BigInt("1a110808",16)))
  core.clk_i := mainClock; core.rst_ni := coreRelease.released
  core.test_en_i := false.B; core.scan_rst_ni := true.B; core.ram_cfg_i := 0.U
  core.instr_rdata_intg_i := 0.U; core.data_rdata_intg_i := 0.U
  core.scramble_key_valid_i := false.B; core.scramble_key_i := 0.U; core.scramble_nonce_i := 0.U
  for((_, port) <- core.ports if DataMirror.directionOf(port) == ActualDirection.Input) {
    port := 0.U.asTypeOf(port)
  }
  core.ports("hart_id_i") := (if(verificationFixture) 0 else 1).U
  core.ports("boot_addr_i") := description.region("boot_rom").base.U
  core.ports("fetch_enable_i") := Mux(memory.epochReady && (bootPermit(bootReleased) || core.debug_mode_o || debugFetch), 5.U, 10.U)
  core.ports("debug_req_i"):=debugRequest(debugHalt)
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

  if(i1Config.nonEmpty) {
    val subsystem=Module(new SocI1Peripherals(description,i1Config.get))
    subsystem.performanceDebugMode:=core.debug_mode_o
    subsystem.performanceReset_n:=coreRelease.reset_n
    debugFetch:=subsystem.performanceDebugFetch;debugHalt:=subsystem.performanceHalt;debugGrant:=subsystem.performanceDebugGrant;debugReset:=subsystem.debugReset
    subsystem.mainClock:=mainClock;subsystem.coldReset_n:=coldReset_n
    subsystem.warmReset_n:=warmReset_n;subsystem.mainServiceReset_n:=mainServiceReset_n
    subsystem.main<>memory.peripheral;subsystem.pins<>i1.get
    subsystem.dmaMemory.foreach(port=>memory.dma.get<>port)
    subsystem.nativeXip.foreach(port=>memory.xip.get<>port)
    subsystem.uartRx:=uartRx
    uartTx:=subsystem.uartTx;uartTxEnable:=subsystem.uartTxEnable
    clockHold:=subsystem.mainHold
    core.ports("irq_fast_i"):=subsystem.fastIrq
    subsystem.supervision.foreach {w=>
      watchdogCoreReset:=w.performanceReset;watchdogWholeReset:=w.wholeReset
      core.ports("irq_nm_i"):=w.warning
    }
    subsystem.performanceReady.foreach(_:=memory.epochReady)
    subsystem.performanceReleased.foreach(bootReleased:=_)
  } else {
  val uartRegion = description.region("uart0")
  val fixtureRegions = if(verificationFixture) Seq(BigInt(0x100000),BigInt(0x2000000),BigInt(0x10000000)) else Seq.empty
  val fabric = Module(new BusFabric(1, Seq(BusRegion(uartRegion.base, uartRegion.size)) ++ fixtureRegions.map(BusRegion(_,16))))
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
  for((base,index) <- fixtureRegions.zipWithIndex) {
    val target=Module(new SocTestTarget(base,base==BigInt(0x2000000)))
    target.clk:=mainClock; target.reset_n:=serviceRelease.released
    target.bus<>fabric.target(index+1)
    fabric.admit(index+1):=true.B; fabric.quiescent(index+1):=false.B
    if(base==BigInt(0x2000000)) core.ports("irq_software_i"):=target.msip
  }
  }
}

/** Single production assembly. Test substitution may replace USB only. */
class DeadhorseSoc(config: String, uartJson: String, romImage: String,
    gateTarget: ClockGateTarget=ClockGateTarget.Model, readLatency: Int=1, banks: Int=4,
    i1Config: Option[SocI1Config]=Some(SocProduction.config()))
  extends SocCoreAssembly(config,uartJson,romImage,gateTarget,readLatency,banks,i1Config=i1Config) {
  require(i1Config.exists(c => c.io.nonEmpty && c.pwm.nonEmpty && c.dma.nonEmpty &&
    c.pinmux.nonEmpty && c.liteCore && c.watchdog.nonEmpty && c.bootControl.nonEmpty &&
    c.qspi.nonEmpty && c.xip), "DeadhorseSoc requires every production feature")
}

/** Named minimal boot/performance fixture; never a production feature profile. */
class SocMinimalI0(config: String, uartJson: String, romImage: String,
    gateTarget: ClockGateTarget=ClockGateTarget.Model, readLatency: Int=1, banks: Int=4,
    verificationFixture: Boolean=false, ramImages: Seq[String]=Seq.empty)
  extends SocCoreAssembly(config,uartJson,romImage,gateTarget,readLatency,banks,
    verificationFixture,ramImages,None)
