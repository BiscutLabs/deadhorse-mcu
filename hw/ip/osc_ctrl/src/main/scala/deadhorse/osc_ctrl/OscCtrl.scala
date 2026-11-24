package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Lite-owned AON register boundary. Existing peripheral maps are untouched. */
class OscCtrl(json: String,base: BigInt=BigInt("40000400",16)) extends RawModule {
  protected def configurationReset(value: Bool): Bool=value
  protected def delayValue(value: UInt): UInt=value
  protected def timeoutValue(value: UInt): UInt=value
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val epochReset_n=IO(Input(Bool()))
  val mainHold=IO(Input(Bool()));val oscillatorHold=IO(Input(Bool()))
  val coreIdle=IO(Input(Bool()));val gateClosed=IO(Input(Bool()));val stable=IO(Input(Bool()))
  val wake=IO(Input(UInt(8.W)))
  val oscillatorOn=IO(Output(Bool()));val gateRequest=IO(Output(Bool()))
  val qualify=IO(Output(Bool()));val count=IO(Output(UInt(16.W)))
  val authorized=IO(Output(Bool()))
  val sleepPreparing=IO(Output(Bool()));val uartModes=IO(Output(UInt(6.W)))
  val uartPolarity=IO(Output(UInt(3.W)));val uartWakeArmed=IO(Output(UInt(3.W)))
  val wakeClear=IO(Output(Bool()));val fault=IO(Output(Bool()))
  // reset_n is the shared, stretched service release in production. The policy
  // survives that reset, so neither its reset request nor its multi-bit config
  // may change asynchronously at a policy data input. Cold/pin epoch reset is
  // still common to policy, this sampler and configuration storage.
  val serviceReset=Module(new CdcSync(1))
  serviceReset.clk:=clk;serviceReset.reset_n:=epochReset_n;serviceReset.in:=(!reset_n).asUInt
  val forceRun=serviceReset.out.asBool
  val configUp=epochReset_n && !forceRun
  val configReady=withClockAndReset(clk,(!(epochReset_n && reset_n)).asAsyncReset) {RegNext(configUp,false.B)}
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=configurationReset(configUp)
  val adapter=Module(new BusRegAdapter(8,base,0))
  adapter.clk:=clk;adapter.reset_n:=reset_n && configUp && configReady
  adapter.bus<>bus;regs.bus<>adapter.registers
  val control=Module(new OscSequencer)
  // Transport/configuration flush with service reset; clock policy survives
  // internal watchdog/debug reset so the DM can clear ndmreset on main.
  control.clk:=clk;control.reset_n:=epochReset_n;control.forceRun:=forceRun
  control.sleep:=regs.hw("sleep_request_pulse").asBool
  control.deep:=regs.hw("policy_deep_q").asBool
  control.wakeEnable:=regs.hw("wake_enable_sources_q")
  control.delayTicks:=delayValue(Mux(forceRun,512.U,regs.hw("startup_delay_ticks_q")))
  control.timeoutTicks:=timeoutValue(Mux(forceRun,4096.U,regs.hw("startup_timeout_ticks_q")))
  control.stableEdges:=Mux(forceRun,256.U,regs.hw("stable_count_edges_q"))
  control.mainHold:=mainHold;control.oscillatorHold:=oscillatorHold
  control.coreIdle:=coreIdle;control.gateClosed:=gateClosed;control.stable:=stable;control.wake:=wake
  regs.hw("status_state_d"):=control.state
  regs.hw("status_oscillator_on_d"):=control.oscillatorOn
  regs.hw("status_gate_requested_d"):=control.gateRequest
  regs.hw("last_wake_sources_d"):=control.lastWake
  withClockAndReset(clk,(!configUp).asAsyncReset) {
    regs.hw("events_startup_fault_set"):=control.fault && !RegNext(control.fault,false.B)
  }
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val modes=RegInit(0.U(6.W))
    when(control.sleep && control.state===0.U) {modes:=regs.hw("uart_mode_modes_q")}
    uartModes:=modes
    // Configuration remains AON-local. Software disarms before changing polarity.
    uartPolarity:=RegNext(regs.hw("uart_polarity_inverted_q"),0.U)
    uartWakeArmed:=RegNext(regs.hw("wake_enable_sources_q")(4,2),0.U)
    wakeClear:=RegNext(!control.preparing && control.state===0.U,false.B)
  }
  oscillatorOn:=control.oscillatorOn;gateRequest:=control.gateRequest
  authorized:=control.authorized
  qualify:=control.qualify;count:=control.count;sleepPreparing:=control.preparing;fault:=control.fault
}

object EmitOscCtrl extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new OscCtrl(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
