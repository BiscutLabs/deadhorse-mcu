package deadhorse.top

import chisel3._
import chisel3.util.experimental.BoringUtils
import deadhorse.lib.LocalBus
import java.nio.file.Paths

class SocResetPhaseBus extends Bundle {
  val request=Bool();val grant=Bool();val response=Bool();val error=Bool()
  val write=Bool();val address=UInt(32.W);val data=UInt(32.W);val result=UInt(32.W)
  val origin=UInt(3.W);val mask=UInt(4.W)
}
class SocResetPhaseWrite extends Bundle {
  val address=UInt(32.W);val data=UInt(32.W);val origin=UInt(3.W);val mask=UInt(4.W)
}

/** Passive public-bus observations and independent event counters. The test
  * drives only real serial/pad interfaces; monitors cannot drive functional RTL. */
class SocResetPhaseProbe extends SocAnalogModelTest("build/t20/map/soc.json",SocProduction.config().uart,
    Paths.get("build/t20/i0-firmware/boot.hex").toAbsolutePath.toString) {
  val monitorReset_n=IO(Input(Bool()))
  val observe=IO(Output(new Bundle {
    val source=new SocResetPhaseBus
    val native=new SocResetPhaseBus
    val retained=new SocResetPhaseBus
    val bridgeSource=new SocResetPhaseBus
    val bridgeTarget=new SocResetPhaseBus
    val mainUp=Bool();val aonUp=Bool()
    val nativeWrites=UInt(16.W);val retainedWrites=UInt(16.W)
    val nativeLast=new SocResetPhaseWrite;val retainedLast=new SocResetPhaseWrite
    val sourceGrants=UInt(16.W);val dmGrants=UInt(16.W);val dmReturns=UInt(16.W)
    val dmErrors=UInt(16.W);val dmLast=UInt(32.W)
  }))
  val peripherals=digital.subsystem.get
  def trace(source: LocalBus,dest: SocResetPhaseBus): Unit={
    dest.request:=BoringUtils.bore(source.req);dest.grant:=BoringUtils.bore(source.gnt)
    dest.response:=BoringUtils.bore(source.rvalid);dest.error:=BoringUtils.bore(source.err)
    dest.write:=BoringUtils.bore(source.bits.we);dest.address:=BoringUtils.bore(source.bits.addr)
    dest.data:=BoringUtils.bore(source.bits.wdata);dest.result:=BoringUtils.bore(source.rdata)
    dest.origin:=BoringUtils.bore(source.bits.origin);dest.mask:=BoringUtils.bore(source.bits.be)
  }
  trace(peripherals.debugger.system,observe.source)
  trace(digital.memory.dma.get,observe.native)
  trace(peripherals.retained.bus,observe.retained)
  trace(peripherals.toAon.source,observe.bridgeSource)
  trace(peripherals.toAon.target,observe.bridgeTarget)
  observe.mainUp:=BoringUtils.bore(peripherals.mainUp)
  observe.aonUp:=BoringUtils.bore(peripherals.aonUp)
  val retainedPermission=BoringUtils.bore(peripherals.retained.debugWriteAllowed.get)
  val loaderBusy=BoringUtils.bore(peripherals.retained.loaderBusy)
  val sba=peripherals.debugger.sba
  val dmUp=BoringUtils.bore(sba.reset_n)
  val dmRequest=BoringUtils.bore(sba.req);val dmGrant=BoringUtils.bore(sba.grant)
  val dmReturn=BoringUtils.bore(sba.valid);val dmError=BoringUtils.bore(sba.error)
  val dmResult=BoringUtils.bore(sba.result)
  def record(bus: SocResetPhaseBus,last: SocResetPhaseWrite): Unit={
    last.address:=bus.address;last.data:=bus.data;last.origin:=bus.origin;last.mask:=bus.mask
  }
  // All test writes use aligned legal RAM addresses and full byte enables.
  // Count each committing target handshake, independent of readback contents.
  withClockAndReset(clocks.mainClock,(!monitorReset_n).asAsyncReset) {
    val count=RegInit(0.U(16.W))
    val last=RegInit(0.U.asTypeOf(new SocResetPhaseWrite))
    when(observe.mainUp && observe.native.request && observe.native.grant && observe.native.write) {
      count:=count+1.U;record(observe.native,last)
    }
    observe.nativeWrites:=count;observe.nativeLast:=last
    val sourceGrants=RegInit(0.U(16.W));val grants=RegInit(0.U(16.W))
    val returns=RegInit(0.U(16.W));val errors=RegInit(0.U(16.W));val result=RegInit(0.U(32.W))
    when(observe.mainUp && observe.source.request && observe.source.grant) {sourceGrants:=sourceGrants+1.U}
    when(dmUp && dmRequest && dmGrant) {grants:=grants+1.U}
    when(dmUp && dmReturn) {returns:=returns+1.U;result:=dmResult;when(dmError) {errors:=errors+1.U}}
    observe.sourceGrants:=sourceGrants;observe.dmGrants:=grants;observe.dmReturns:=returns
    observe.dmErrors:=errors;observe.dmLast:=result
  }
  withClockAndReset(clocks.aonClock,(!monitorReset_n).asAsyncReset) {
    val count=RegInit(0.U(16.W))
    val last=RegInit(0.U.asTypeOf(new SocResetPhaseWrite))
    when(observe.aonUp && observe.retained.request && observe.retained.grant &&
        observe.retained.write && retainedPermission && !loaderBusy) {
      count:=count+1.U;record(observe.retained,last)
    }
    observe.retainedWrites:=count;observe.retainedLast:=last
  }
}
