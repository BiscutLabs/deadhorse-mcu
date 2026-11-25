package deadhorse.top

import chisel3._
import chisel3.util.experimental.BoringUtils
import deadhorse.lib.LocalBus
import deadhorse.lite_core.Operation
import java.nio.file.Paths

/** Passive observations of the real client and register interfaces. */
class SocClientPhaseProbe(lite: Boolean) extends SocAnalogModelTest(
    "build/t20/map/soc.json",SocProduction.config().uart,
    Paths.get(s"build/t33/client-firmware/${if(lite) "boot-lite" else "boot"}.hex").toAbsolutePath.toString) {
  val monitorReset_n=IO(Input(Bool()))
  val trackRead=IO(Input(Bool()))
  val observe=IO(Output(new Bundle {
    val downstream=new SocResetPhaseBus
    val target=new SocResetPhaseBus
    val bridge=new SocResetPhaseBus
    val clientRequest=Bool();val clientReady=Bool();val clientBuffered=Bool()
    val clientEpoch=Bool();val invalidated=Bool();val clientAccepted=UInt(16.W);val clientConsumed=UInt(16.W)
    val downstreamAccepted=UInt(16.W);val clientData=UInt(32.W)
    val accessVisible=Bool();val committed=UInt(16.W);val registerResponse=Bool()
    val targetAccepted=UInt(16.W);val targetOrigin=UInt(3.W)
    val commitData=UInt(32.W);val commitMask=UInt(4.W)
    val lateReturns=UInt(16.W);val lateRetirements=UInt(16.W)
    val loadRetirements=UInt(16.W);val loadData=UInt(32.W);val sleeping=Bool();val trap=Bool()
    val phaseFlags=UInt(11.W)
    val shadow=UInt(32.W);val mainUp=Bool();val aonUp=Bool()
    val liteHalted=Bool();val liteHeld=Bool();val responseErrors=UInt(16.W);val rebootDataErrors=UInt(16.W)
  }))
  val peripherals=digital.subsystem.get
  val hart=peripherals.liteHart.get
  val regs=peripherals.watchdogBlocks(if(lite) 1 else 0).regs
  val downstream=if(lite) hart.bus else digital.memory.peripheral
  val target=peripherals.watchdogBlocks(if(lite) 1 else 0).bus
  val bridge=if(lite) peripherals.af.master(0) else peripherals.toAon.source
  val address=if(lite) BigInt("40000200",16) else BigInt("40000100",16)
  val offset=0
  def trace(source: LocalBus,dest: SocResetPhaseBus): Unit={
    dest.request:=BoringUtils.bore(source.req);dest.grant:=BoringUtils.bore(source.gnt)
    dest.response:=BoringUtils.bore(source.rvalid);dest.error:=BoringUtils.bore(source.err)
    dest.write:=BoringUtils.bore(source.bits.we);dest.address:=BoringUtils.bore(source.bits.addr)
    dest.data:=BoringUtils.bore(source.bits.wdata);dest.result:=BoringUtils.bore(source.rdata)
    dest.origin:=BoringUtils.bore(source.bits.origin);dest.mask:=BoringUtils.bore(source.bits.be)
  }
  trace(downstream,observe.downstream);trace(target,observe.target);trace(bridge,observe.bridge)
  observe.mainUp:=BoringUtils.bore(peripherals.mainUp);observe.aonUp:=BoringUtils.bore(peripherals.aonUp)
  observe.liteHalted:=BoringUtils.bore(hart.halted)
  observe.liteHeld:=BoringUtils.bore(peripherals.liteBootHeld)
  observe.shadow:=BoringUtils.bore(regs.hw("period_ticks_q"))

  val clientClock=if(lite) clocks.aonClock else clocks.mainClock
  val targetClock=clocks.aonClock
  // T41 shares AON reset; boot/debug HOLD initializes lite synchronously.
  // Client permission therefore requires both the domain release and no HOLD.
  val clientEpoch=if(lite) BoringUtils.bore(hart.reset_n) && !BoringUtils.bore(hart.initialize.get)
    else BoringUtils.bore(digital.memory.clientReset_n)
  val request=if(lite) BoringUtils.bore(hart.adapter.request.valid) &&
    BoringUtils.bore(hart.adapter.request.bits.operation)===Mux(trackRead,Operation.Read.U,Operation.Write.U) &&
    BoringUtils.bore(hart.adapter.request.bits.address)===address.U else
    BoringUtils.bore(digital.memory.data.req) && BoringUtils.bore(digital.memory.data.bits.we)=== !trackRead &&
    BoringUtils.bore(digital.memory.data.bits.addr)===address.U
  val ready=if(lite) BoringUtils.bore(hart.adapter.request.ready) else BoringUtils.bore(digital.memory.data.gnt)
  val reply=if(lite) BoringUtils.bore(hart.adapter.response.valid) else BoringUtils.bore(digital.memory.data.rvalid)
  val consume=if(lite) BoringUtils.bore(hart.adapter.response.ready) else true.B
  val retirement=if(lite) BoringUtils.bore(hart.rvfi.valid) else BoringUtils.bore(digital.rvfi("rvfi_valid").asInstanceOf[Bool])
  val loadMask=if(lite) BoringUtils.bore(hart.rvfi.mem_rmask) else BoringUtils.bore(digital.rvfi("rvfi_mem_rmask").asUInt)
  val loadAddress=if(lite) BoringUtils.bore(hart.rvfi.mem_addr) else BoringUtils.bore(digital.rvfi("rvfi_mem_addr").asUInt)
  val loadData=if(lite) BoringUtils.bore(hart.rvfi.mem_rdata) else BoringUtils.bore(digital.rvfi("rvfi_mem_rdata").asUInt)
  // The performance trace exposes a memory-size mask on non-loads too.
  // Identify this fixture's actual LW instruction, rather than counting its
  // preceding SW or an incidental stale address as another load retirement.
  val isLoad=if(lite) true.B else {
    val insn=BoringUtils.bore(digital.rvfi("rvfi_insn").asUInt)
    insn(6,0)==="b0000011".U && insn(14,12)===2.U
  }
  val allRequest=if(lite) BoringUtils.bore(hart.adapter.request.valid) else BoringUtils.bore(digital.memory.data.req)
  val insn=if(lite) BoringUtils.bore(hart.rvfi.insn) else BoringUtils.bore(digital.rvfi("rvfi_insn").asUInt)
  val memoryInstruction=insn(6,0)==="b0000011".U || insn(6,0)==="b0100011".U
  observe.trap:= (if(lite) BoringUtils.bore(hart.rvfi.trap) else BoringUtils.bore(digital.rvfi("rvfi_trap").asInstanceOf[Bool]))
  observe.sleeping:= (if(lite) BoringUtils.bore(hart.sleeping) else BoringUtils.bore(digital.coreSleeping))
  observe.clientData:= (if(lite) BoringUtils.bore(hart.adapter.response.bits.data) else BoringUtils.bore(digital.memory.data.rdata))
  observe.clientRequest:=request;observe.clientReady:=ready;observe.clientEpoch:=clientEpoch
  // A warm reset may stop main before a monitor edge, and lite later leaves
  // reset while still awaiting START. Preserve the board event asynchronously
  // until the test explicitly initializes the next epoch with clocks running.
  val invalidated=withClockAndReset(clientClock,(!externalReset_n).asAsyncReset) {
    val seen=RegInit(true.B);when(!monitorReset_n) {seen:=false.B};seen
  }
  observe.invalidated:=invalidated
  withClockAndReset(clientClock,(!monitorReset_n).asAsyncReset) {
    val pending=RegInit(false.B);val selected=RegInit(false.B);val accepted=RegInit(0.U(16.W));val consumed=RegInit(0.U(16.W))
    val lateReturns=RegInit(0.U(16.W));val lateRetirements=RegInit(0.U(16.W))
    val downstreamAccepted=RegInit(0.U(16.W));val loads=RegInit(0.U(16.W));val lastLoad=RegInit(0.U(32.W))
    val responseErrors=RegInit(0.U(16.W));val rebootDataErrors=RegInit(0.U(16.W))
    val tracking=RegInit(false.B);val freshAfterReset=RegInit(false.B)
    when(clientEpoch && allRequest && ready) {
      when(pending && (!invalidated || freshAfterReset)) {responseErrors:=responseErrors+1.U}
      tracking:=true.B;when(invalidated) {freshAfterReset:=true.B}
      pending:=true.B;selected:=request
      when(request) {accepted:=accepted+1.U}
    }
    when(reply && consume) {
      when(tracking && !pending) {responseErrors:=responseErrors+1.U}
      pending:=false.B
      when(pending && selected) {consumed:=consumed+1.U}
    }
    when((invalidated || !clientEpoch) && reply && (selected || !pending || lite.B)) {lateReturns:=lateReturns+1.U}
    when((invalidated || !clientEpoch) && retirement && (lite.B || memoryInstruction && loadAddress===address.U)) {lateRetirements:=lateRetirements+1.U}
    // Every post-reset GPIO poll must return the actual board value0. A stale
    // selected reply relabelled as this fresh request cannot pass unnoticed.
    when(invalidated && retirement && isLoad && loadAddress==="h40012008".U && loadData=/=0.U) {rebootDataErrors:=rebootDataErrors+1.U}
    observe.responseErrors:=responseErrors;observe.rebootDataErrors:=rebootDataErrors
    when(clientEpoch && observe.downstream.request && observe.downstream.grant &&
        observe.downstream.write=== !trackRead && observe.downstream.address===address.U) {downstreamAccepted:=downstreamAccepted+1.U}
    when(clientEpoch && retirement && isLoad && loadMask.orR && loadAddress===address.U) {loads:=loads+1.U;lastLoad:=loadData}
    observe.clientBuffered:=pending && selected && reply
    observe.clientAccepted:=accepted;observe.clientConsumed:=consumed
    observe.lateReturns:=lateReturns;observe.lateRetirements:=lateRetirements
    observe.downstreamAccepted:=downstreamAccepted;observe.loadRetirements:=loads;observe.loadData:=lastLoad
  }
  val endpointUp=BoringUtils.bore(regs.rst_n)
  val commit=endpointUp && BoringUtils.bore(regs.bus.req_valid) && BoringUtils.bore(regs.bus.req_ready) &&
    BoringUtils.bore(regs.bus.req_write) && BoringUtils.bore(regs.bus.req_addr)===offset.U
  val regReply=BoringUtils.bore(regs.bus.rsp_valid);val regReady=BoringUtils.bore(regs.bus.rsp_ready)
  val access=endpointUp && BoringUtils.bore(regs.bus.req_valid) && BoringUtils.bore(regs.bus.req_ready) &&
    BoringUtils.bore(regs.bus.req_write)=== !trackRead && BoringUtils.bore(regs.bus.req_addr)===offset.U
  observe.accessVisible:=access
  withClockAndReset(targetClock,(!monitorReset_n).asAsyncReset) {
    val accepted=RegInit(0.U(16.W));val origin=RegInit(0.U(3.W))
    val committed=RegInit(0.U(16.W));val data=RegInit(0.U(32.W));val mask=RegInit(0.U(4.W))
    val pending=RegInit(false.B)
    when(endpointUp && observe.target.request && observe.target.grant && observe.target.write=== !trackRead &&
        observe.target.address===address.U) {accepted:=accepted+1.U;origin:=observe.target.origin}
    when(commit) {
      committed:=committed+1.U;data:=BoringUtils.bore(regs.bus.req_wdata)
      mask:=BoringUtils.bore(regs.bus.req_wstrb)
    }
    when(access) {pending:=true.B}
    when(pending && regReply && regReady) {pending:=false.B}
    observe.registerResponse:=pending && regReply
    observe.targetAccepted:=accepted;observe.targetOrigin:=origin
    observe.committed:=committed;observe.commitData:=data;observe.commitMask:=mask
  }
  // Passive event encoding reduces simulator IPC; it drives no DUT signal.
  // Expected acceptance/commit counts remain in the independent test oracle.
  def selected(bus: SocResetPhaseBus): Bool=bus.address===address.U && bus.write=== !trackRead
  val accepted=observe.clientAccepted===1.U
  observe.phaseFlags:=VecInit(Seq(
    observe.clientRequest && observe.clientReady,
    accepted,
    accepted && observe.downstream.request && observe.downstream.grant && selected(observe.downstream),
    observe.downstreamAccepted===1.U,
    accepted && observe.target.request && observe.target.grant && selected(observe.target),
    accepted && observe.accessVisible,
    !trackRead && observe.committed===1.U,
    accepted && observe.target.response,
    accepted && observe.bridge.response,
    observe.clientBuffered,
    accepted && observe.registerResponse)).asUInt
}
