package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** An absent endpoint always answers with a registered error, without effects. */
class SocErrorTarget extends RawModule {
  protected def responseValid(value: Bool): Bool=value
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool())); val bus=IO(new LocalBus)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val grant=RegInit(false.B); val reply=RegInit(false.B)
    grant := bus.req && !grant && !reply
    reply := bus.req && grant
    bus.gnt:=grant; bus.rvalid:=responseValid(reply); bus.rdata:=0.U; bus.err:=true.B
  }
}

/** Credit reset is the destination fabric's service reset, never peer reset. */
class SocDrainCredit extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val accepted=IO(Input(Bool()));val response=IO(Input(Bool()))
  val empty=IO(Output(Bool()))
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val pending=RegInit(false.B)
    when(accepted) {pending:=true.B}
    when(response) {pending:=false.B}
    assert(!accepted || !pending)
    assert(!response || pending)
    empty:= !pending
  }
}

/** Surviving main-domain slot around an independently reset endpoint.
  * The endpoint reset cancels its entire bus adapter; no transaction is replayed.
  * A reset pulse is remembered even while the main clock is stopped.
  */
class SocResetSlot extends RawModule {
  protected def responseValid(value: Bool): Bool=value
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val endpointReset_n=IO(Input(Bool()));val endpointReady=IO(Input(Bool()))
  val bus=IO(new LocalBus);val target=IO(Flipped(new LocalBus));val quiescent=IO(Output(Bool()))
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: grant :: send :: waitReply :: reply :: Nil=Enum(5)
    val state=RegInit(idle);val gnt=RegInit(false.B);val valid=RegInit(false.B)
    val req=RegInit(false.B);val data=RegInit(0.U(32.W));val error=RegInit(false.B)
    val packet=Reg(new BusPayload)
    val alive=withReset((!(reset_n && endpointReset_n)).asAsyncReset) {RegInit(false.B)}
    when(state===idle && endpointReady) {alive:=true.B}
    gnt:=false.B;valid:=false.B
    bus.gnt:=gnt;bus.rvalid:=responseValid(valid);bus.rdata:=data;bus.err:=error
    target.req:=req;target.bits:=packet
    quiescent:=RegNext(state===idle && alive && !valid && !bus.req,false.B)
    def finish(value: UInt, bad: Bool): Unit = {
      data:=Mux(bad || packet.we,0.U,value);error:=bad;valid:=true.B;req:=false.B;state:=reply
    }
    when(state===idle && alive && endpointReady && bus.req) {
      packet:=bus.bits;gnt:=true.B;state:=grant
    }
    when(state===grant) {
      when(!bus.req) {state:=idle}
        .elsewhen(!alive) {finish(0.U,true.B)}.otherwise {req:=true.B;state:=send}
    }
    when(state===send || state===waitReply) {
      when(!alive) {finish(0.U,true.B)}
        .elsewhen(state===send && target.gnt) {req:=false.B;state:=waitReply}
        .elsewhen(state===waitReply && target.rvalid) {finish(target.rdata,target.err)}
    }
    when(state===reply) {state:=idle}
    assert(!req || state===send)
    assert(!gnt || state===grant)
    assert(!valid || state===reply)
    assert(!quiescent || state===idle && !req && !valid && !gnt)
  }
}

/** Retained SRAM: program writes require the performance-owned reset hold.
  * Reset flushes protocol state, never RAM. Debug cannot bypass program authority.
  */
class SocRetainedMemory(description: SocDescription,debugAccess: Boolean=false,
    sramTarget: deadhorse.sram.SramTarget=deadhorse.sram.SramTarget.Model,
    bistEnabled: Boolean=false) extends RawModule {
  val testPort=if(bistEnabled) Some(IO(Flipped(new deadhorse.sram.SramPort(12)))) else None
  val testOwn=if(bistEnabled) Some(IO(Input(Bool()))) else None
  val debugWriteAllowed=if(debugAccess) Some(IO(Input(Bool()))) else None
  private val region=description.region("retained_sram")
  require(region.size==2048 && description.retainedProgramBytes==1024)
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val bootHeld=IO(Input(Bool()));val busy=IO(Output(Bool()))
  protected def stored(value: UInt): UInt=value
  protected def programWriteAllowed(remote: Bool,held: Bool): Bool=remote && held
  testOwn.foreach {own=>withClockAndReset(clk,false.B) {
    assert(!own || !reset_n)
    assert(!testPort.get.enable || own && testPort.get.address<(region.size/4).U)
  }}
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: busGrant :: readReturn :: reply :: Nil=Enum(4)
    val state=RegInit(idle);val grant=RegInit(false.B);val valid=RegInit(false.B)
    val error=RegInit(false.B);val result=RegInit(0.U(32.W))
    val memory=Module(new deadhorse.sram.SramWordBank(512,sramTarget));memory.clk:=clk
    val offset=bus.bits.addr-region.base.U
    val inRange=bus.bits.addr>=region.base.U && bus.bits.addr<(region.base+region.size).U && !bus.bits.addr(1,0).orR
    val program=offset<description.retainedProgramBytes.U
    val local=bus.bits.origin===description.origin("lite").U
    val remote=bus.bits.origin===description.origin("performance").U
    val ordinaryPermitted=inRange && Mux(program,
      Mux(bus.bits.we,programWriteAllowed(remote,bootHeld),local || remote),local || remote && bootHeld)
    val debugOwner=if(debugAccess) bus.bits.origin===description.origin("gateway_debug").U else false.B
    val debugPermitted=inRange && debugOwner &&
      (!bus.bits.we || !program && debugWriteAllowed.getOrElse(false.B))
    val permitted=ordinaryPermitted || debugPermitted
    val take=state===busGrant && grant && bus.req
    val write=take && permitted && bus.bits.we
    val read=take && permitted && !bus.bits.we
    val testing=testOwn.getOrElse(false.B)
    val testAddress=testPort.map(_.address).getOrElse(0.U)
    memory.port.address:=Mux(testing,testAddress,offset>>2)
    memory.port.data:=Mux(testing,testPort.map(_.data).getOrElse(0.U),stored(bus.bits.wdata))
    memory.port.mask:=Mux(testing,testPort.map(_.mask).getOrElse(0.U),bus.bits.be)
    memory.port.write:=Mux(testing,testPort.map(_.write).getOrElse(false.B),write)
    memory.port.enable:=Mux(testing,testPort.map(p=>p.enable && p.address<(region.size/4).U).getOrElse(false.B),reset_n && (write || read))
    testPort.foreach(_.result:=memory.port.result)
    grant:=false.B;valid:=false.B
    when(state===idle && bus.req) {grant:=true.B;state:=busGrant}
    when(state===busGrant) {
      when(take) {
        result:=0.U;error:= !permitted
        when(read) {state:=readReturn}.otherwise {valid:=true.B;state:=reply}
      }.otherwise {state:=idle}
    }
    when(state===readReturn) {result:=memory.port.result;valid:=true.B;state:=reply}
    when(state===reply) {state:=idle}
    bus.gnt:=grant;bus.rvalid:=valid;bus.rdata:=result;bus.err:=error;busy:=state=/=idle
    assert(!write || !program || remote && bootHeld)
    assert(!write || !debugOwner || !program && debugWriteAllowed.getOrElse(false.B))
    assert(!read || permitted)
  }
}

case class SocIoConfig(gpio: String, timers: String, aonTimer: String, mainMHz: Int) {
  require(Set(8,9).contains(mainMHz))
}
/** Clock-boundary handshake. Internal to the production clock/reset wrapper. */
class SocClockControlPins extends Bundle {
  val reset_n=Input(Bool());val coreIdle=Input(Bool());val stable=Input(Bool())
  val closed=Input(Bool());val jtagWake=Input(Bool())
  val oscillatorOn=Output(Bool());val gateRequest=Output(Bool());val authorized=Output(Bool())
  val qualify=Output(Bool());val count=Output(UInt(16.W));val fault=Output(Bool())
  val threshold=Output(UInt(2.W))
}

/** Digital assembly boundary; production derives clocks/resets in its wrapper. */
class SocI1Pins extends Bundle {
  val aonExtraIn=Input(UInt(3.W));val aonExtraOut=Output(UInt(3.W));val aonExtraEnable=Output(UInt(3.W))
  val clockControl=new SocClockControlPins
  val inactive=new SocInactivePins
  val aonClock=Input(Clock());val usbClock=Input(Clock())
  val aonServiceReset_n=Input(Bool());val usbServiceReset_n=Input(Bool())
  val lite=new LocalBus
  val liteHalted=Input(Bool());val resetReason=Input(UInt(32.W));val crashCount=Input(UInt(32.W))
  val liteStart=Output(Bool());val liteEntry=Output(UInt(32.W));
  val aonIrq=Output(Bool())
  val uartRx=Input(Vec(2,Bool()));val uartTx=Output(Vec(2,Bool()));val uartTxEnable=Output(Vec(2,Bool()))
  val spiMiso=Input(Bool());val spiTimeNow=Input(UInt(32.W));val spiSclk=Output(Bool());val spiMosi=Output(Bool())
  val spiCs_n=Output(UInt(2.W));val spiEnable=Output(Bool())
  val i2cSclIn=Input(Bool());val i2cSdaIn=Input(Bool());val i2cSclLow=Output(Bool());val i2cSdaLow=Output(Bool());val i2cEnable=Output(Bool())

  val usbVbus=Input(Bool());val usbDpRx=Input(Bool());val usbDnRx=Input(Bool())
  val usbDpTx=Output(Bool());val usbDnTx=Output(Bool());val usbTxEnable=Output(Bool());val usbPullup=Output(Bool())
  val usbWake=Output(Bool());val usbClockRequest=Output(Bool())
  val mainDemand=Output(Bool());val aonDemand=Output(Bool());
}
