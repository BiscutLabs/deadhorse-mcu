package deadhorse.usb

import chisel3._
import chisel3.util._
import deadhorse.lib._

class Usb(json: String, base: BigInt = 0x40040800L, vid: Int = 0, pid: Int = 0,
          included: Boolean = true) extends RawModule {
  val appClock=IO(Input(Clock()));val usbClock=IO(Input(Clock()));val aonClock=IO(Input(Clock()))
  val appReset_n=IO(Input(Bool()));val usbReset_n=IO(Input(Bool()));val aonReset_n=IO(Input(Bool()))
  val bus=IO(new LocalBus);val owner=IO(Input(UInt(3.W)))
  val vbus=IO(Input(Bool()));val dpRx=IO(Input(Bool()));val dnRx=IO(Input(Bool()))
  val dpTx=IO(Output(Bool()));val dnTx=IO(Output(Bool()));val txEnable=IO(Output(Bool()))
  val pullupEnable=IO(Output(Bool()));val irq=IO(Output(Bool()))
  val wake=IO(Output(Bool()));val usbClockRequest=IO(Output(Bool()))
  val commonReset=appReset_n && usbReset_n
  def released(clock: Clock, raw: Bool): Bool={val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=raw;r.released}
  def sync(clock: Clock, reset: Bool, signal: Bool): Bool={
    val s=Module(new CdcSync(1));s.clk:=clock;s.reset_n:=reset;s.in:=signal.asUInt;s.out.asBool
  }
  val appUp=released(appClock,commonReset);val usbUp=released(usbClock,commonReset)
  val aonUp=released(aonClock,aonReset_n)
  val registers=Module(new UsbRegisters(json,base))
  registers.clk:=appClock;registers.reset_n:=appUp;registers.bus<>bus;registers.owner:=owner
  irq:=registers.irq
  if (!included) {
    registers.txReady:=false.B;registers.rxValid:=false.B;registers.rxData:=0.U
    registers.configured:=false.B;registers.connected:=false.B;registers.frame:=0.U
    registers.sessionReset:=false.B;registers.resume:=false.B
    dpTx:=true.B;dnTx:=false.B;txEnable:=false.B;pullupEnable:=false.B
    wake:=false.B;usbClockRequest:=false.B
  } else {
    val enabledUsb=sync(usbClock,usbUp,registers.enabled)
    // AON sees application demand before USB edges exist, avoiding startup deadlock.
    usbClockRequest:=sync(aonClock,aonUp,registers.enabled)
    val engine=Module(new UsbEngine(vid,pid))
    // Reset used by downstream data/safety logic comes from shared release.
    // usbUp still asserts asynchronously when either raw reset drops.
    engine.clk:=usbClock;engine.reset_n:=usbUp && enabledUsb
    engine.vbus:=vbus;engine.dpRx:=dpRx;engine.dnRx:=dnRx
    dpTx:=engine.dpTx;dnTx:=engine.dnTx;txEnable:=engine.txEnable;pullupEnable:=engine.pullup
    val tx=Module(new CdcFifo(8));val rx=Module(new CdcFifo(8))
    tx.writeClock:=appClock;tx.readClock:=usbClock;tx.writeReset_n:=appUp
    tx.readReset_n:=usbUp && !engine.txReset
    tx.push:=registers.txPush;tx.in:=registers.txData
    tx.pop:=engine.txReady;engine.txValid:=tx.valid;engine.txData:=tx.out
    registers.txReady:=tx.ready
    rx.writeClock:=usbClock;rx.readClock:=appClock;rx.writeReset_n:=usbUp && !engine.rxReset
    rx.readReset_n:=appUp;rx.push:=engine.rxValid;rx.in:=engine.rxData;engine.rxReady:=rx.ready
    rx.pop:=registers.rxPop;registers.rxValid:=rx.valid;registers.rxData:=rx.out
    registers.configured:=sync(appClock,appUp,engine.configured)
    registers.connected:=sync(appClock,appUp,engine.attached)

    val snapshot=Module(new CdcFifo(32))
    snapshot.writeClock:=usbClock;snapshot.readClock:=appClock
    snapshot.writeReset_n:=usbUp && !engine.sessionReset;snapshot.readReset_n:=appUp
    snapshot.in:=engine.frame;snapshot.push:=snapshot.ready;snapshot.pop:=snapshot.valid
    withClockAndReset(appClock,(!appUp).asAsyncReset) {
      val frame=RegInit(0.U(11.W))
      when(!snapshot.readUp) {frame:=0.U}.elsewhen(snapshot.valid) {frame:=snapshot.out(10,0)}
      registers.frame:=frame
    }
    val ackToggle=withClockAndReset(appClock,(!appUp).asAsyncReset) {
      val bit=RegInit(false.B);when(registers.wakeAck) {bit := !bit};bit
    }
    val ackUsb=sync(usbClock,usbUp,ackToggle)
    val resume=Module(new UsbResume)
    resume.clk:=usbClock;resume.reset_n:=usbUp
    resume.dp:=dpRx;resume.dn:=dnRx;resume.attached:=engine.attached;resume.driving:=engine.txEnable
    val events=Module(new CdcFifo(8))
    events.writeClock:=usbClock;events.readClock:=appClock
    events.writeReset_n:=usbUp;events.readReset_n:=appUp
    events.pop:=events.valid
    registers.sessionReset:=events.valid && events.out(0)
    registers.resume:=events.valid && events.out(1)
    val heldEvents=withClockAndReset(usbClock,(!usbUp).asAsyncReset) {
      val lastAck=RegNext(ackUsb,false.B);resume.clear:=ackUsb=/=lastAck
      val previousFlush=RegNext(engine.sessionReset,true.B)
      val previousResume=RegNext(resume.pending,false.B)
      val newEvents=Cat(resume.pending && !previousResume,engine.sessionReset && !previousFlush)
      val held=RegInit(0.U(2.W))
      events.push:=held.orR;events.in:=held
      held:=Mux(events.ready,0.U,held)|newEvents
      held.orR
    }
    val sourceWake=withClockAndReset(usbClock,(!usbUp).asAsyncReset) {
      RegNext(rx.writePending || events.writePending || heldEvents || resume.pending,false.B)
    }
    wake:=sync(aonClock,aonUp,sourceWake)
  }
}
