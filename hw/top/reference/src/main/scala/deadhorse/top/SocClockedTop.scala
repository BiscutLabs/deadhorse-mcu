package deadhorse.top

import chisel3._
import chisel3.experimental.{Analog,attach}
import deadhorse.lib._
import deadhorse.osc_ctrl._

/** Existing logical pad functions, before T38 physical pad-cell binding. */
class SocPhysicalPins extends Bundle {
  val aonExtraIn=Input(UInt(3.W));val aonExtraOut=Output(UInt(3.W));val aonExtraEnable=Output(UInt(3.W))
  val inactive=new SocInactivePins
  val uartRx=Input(Vec(3,Bool()));val uartTx=Output(Vec(3,Bool()));val uartTxEnable=Output(Vec(3,Bool()))
  val spiMiso=Input(Bool());val spiSclk=Output(Bool());val spiMosi=Output(Bool())
  val spiCs_n=Output(UInt(2.W));val spiEnable=Output(Bool())
  val i2cSclIn=Input(Bool());val i2cSdaIn=Input(Bool());val i2cSclLow=Output(Bool());val i2cSdaLow=Output(Bool());val i2cEnable=Output(Bool())

  val usbVbus=Input(Bool());val usbDpRx=Input(Bool());val usbDnRx=Input(Bool())
  val usbDpTx=Output(Bool());val usbDnTx=Output(Bool());val usbTxEnable=Output(Bool());val usbPullup=Output(Bool())
}
class SocAnalogSimulation extends Bundle {
  val lfClock=Input(Clock());val porReference=Input(Clock());val supplyMv=Input(UInt(12.W))
}
class SocClockStatus extends Bundle {
  val aonReleased=Bool();val servicesReleased=Bool();val mainLevel=Bool()
  val sourceStable=Bool();val fault=Bool();val coreReady=Bool();val coreSleeping=Bool()
  val resetCauses=UInt(3.W)
}

/** One production clock/reset architecture. analogModels is a named simulation
  * substitution only; it never changes the digital feature set or clock logic. */
class DeadhorseSoc(config: String,uartJson: String,romImage: String,
    gateTarget: ClockGateTarget=ClockGateTarget.Model,readLatency: Int=1,banks: Int=4,
    i1Config: Option[SocI1Config]=Some(SocProduction.config()),analogModels: Boolean=false)
  extends RawModule {
  require(i1Config.exists(_.mainMHz==8),"Production main clock is OSC_IN / 6 at 8 MHz")
  val oscIn=IO(Input(Clock()));val oscEn=IO(Output(Bool()))
  val aonClockIn=IO(Input(Clock()));val aonClockSelect=IO(Input(Bool()));val porBypass=IO(Input(Bool()))
  val externalReset_n=IO(Input(Bool()));val pins=IO(new SocPhysicalPins)
  val status=IO(Output(new SocClockStatus))
  val model=if(analogModels) Some(IO(new SocAnalogSimulation)) else None
  val vdd=if(!analogModels) Some(IO(Analog(1.W))) else None
  val vss=if(!analogModels) Some(IO(Analog(1.W))) else None
  val rc=Wire(Clock());val supplyReset=Wire(Bool());val brownout=Wire(Bool())
  val threshold=Wire(UInt(2.W))
  if(analogModels) {
    val lf=Module(new LfRcModel);lf.source:=model.get.lfClock
    lf.power_n:=model.get.supplyMv>=100.U;lf.enable:=true.B
    lf.trim:=0.U;lf.test:=false.B;rc:=lf.out
    val por=Module(new PorBrownoutModel)
    por.reference:=model.get.porReference;por.supplyMv:=model.get.supplyMv;por.threshold:=threshold;por.test:=false.B
    supplyReset:=por.supplyReset_n;brownout:=por.brownout
  } else {
    val lf=Module(new LfRcMacro);attach(lf.io.vdd,vdd.get);attach(lf.io.vss,vss.get)
    lf.io.enable:=true.B;lf.io.trim:=0.U;lf.io.test:=false.B;rc:=lf.io.clock
    val por=Module(new PorBrownoutMacro);attach(por.io.vdd,vdd.get);attach(por.io.vss,vss.get)
    por.io.threshold:=threshold;por.io.test:=false.B;supplyReset:=por.io.supplyReset_n;brownout:=por.io.brownout
  }
  val clocks=Module(new OscClockReset(gateTarget,consolidated=true))
  clocks.oscIn:=oscIn;clocks.rcClock:=rc;clocks.aonClockIn:=aonClockIn
  clocks.externalReset_n:=externalReset_n;clocks.supplyReset_n:=supplyReset
  clocks.aonClockSelect:=aonClockSelect;clocks.porBypass:=porBypass
  val digital=Module(new SocDigitalAssembly(config,uartJson,romImage,gateTarget,readLatency,banks,i1Config,withRvfi=analogModels,externalResetDomains=true))
  val resetDomains=Module(new SocResetDomains)
  resetDomains.mainClock:=clocks.ungatedClock;resetDomains.aonClock:=clocks.aonClock
  resetDomains.sourceClock:=oscIn;resetDomains.scanClock:=pins.inactive.jtagTck.asClock
  resetDomains.cold_n:=clocks.coldReset_n;resetDomains.pin_n:=externalReset_n
  resetDomains.warm_n:=digital.requestedWarm_n
  resetDomains.aonQualified:=clocks.aonReset_n;resetDomains.mainQualified:=clocks.serviceReset_n
  digital.resetDomains.get:=resetDomains.released
  clocks.shared.get.coldAon:=resetDomains.released.coldAon
  clocks.shared.get.coldMain:=resetDomains.released.coldMain
  clocks.shared.get.coldSource:=resetDomains.released.coldSource
  clocks.shared.get.pinAon:=resetDomains.released.pinAon
  clocks.shared.get.initialize:=resetDomains.released.warmInitialize
  digital.mainClock:=clocks.mainClock;digital.coldReset_n:=clocks.coldReset_n
  digital.warmReset_n:=clocks.warmReset_n;digital.mainServiceReset_n:=clocks.serviceReset_n
  digital.mainCoreReset_n:=true.B
  val p=digital.i1.get
  p.aonClock:=clocks.aonClock;p.usbClock:=oscIn
  p.aonServiceReset_n:=clocks.aonReset_n;p.usbServiceReset_n:=clocks.usbServiceReset_n
  clocks.epochClear.get:=p.clockControl.epochClear;p.clockControl.clearAck:=clocks.clearAck.get
  p.clockControl.reset_n:=clocks.aonReset_n
  p.clockControl.coreIdle:=digital.coreReady && digital.coreSleeping
  p.clockControl.stable:=clocks.stable;p.clockControl.closed:=clocks.closed
  // T32 supplies the actual pending-TCK wake in the digital assembly.
  p.clockControl.jtagWake:=false.B
  clocks.oscillatorOn:=p.clockControl.oscillatorOn;oscEn:=p.clockControl.oscillatorOn
  clocks.gateRequest:=p.clockControl.gateRequest;clocks.authorized:=p.clockControl.authorized
  clocks.qualify:=p.clockControl.qualify;clocks.count:=p.clockControl.count
  clocks.localHold:=digital.clockHold;clocks.coreIdle:=digital.coreReady && digital.coreSleeping
  // The real lite core owns this interface. External bus injection is absent.
  p.lite.req:=false.B;p.lite.bits:=0.U.asTypeOf(p.lite.bits)
  p.liteHalted:=false.B;p.crashCount:=0.U;p.spiTimeNow:=0.U
  threshold:=p.clockControl.threshold
  p.inactive<>pins.inactive
  p.aonExtraIn:=pins.aonExtraIn;pins.aonExtraOut:=p.aonExtraOut;pins.aonExtraEnable:=p.aonExtraEnable
  digital.uartRx:=pins.uartRx(0);pins.uartTx(0):=digital.uartTx;pins.uartTxEnable(0):=digital.uartTxEnable
  for(i<-0 until 2) {p.uartRx(i):=pins.uartRx(i+1);pins.uartTx(i+1):=p.uartTx(i);pins.uartTxEnable(i+1):=p.uartTxEnable(i)}
  p.spiMiso:=pins.spiMiso;pins.spiSclk:=p.spiSclk;pins.spiMosi:=p.spiMosi
  pins.spiCs_n:=p.spiCs_n;pins.spiEnable:=p.spiEnable
  p.i2cSclIn:=pins.i2cSclIn;p.i2cSdaIn:=pins.i2cSdaIn
  pins.i2cSclLow:=p.i2cSclLow;pins.i2cSdaLow:=p.i2cSdaLow;pins.i2cEnable:=p.i2cEnable
  p.usbVbus:=pins.usbVbus;p.usbDpRx:=pins.usbDpRx;p.usbDnRx:=pins.usbDnRx
  pins.usbDpTx:=p.usbDpTx;pins.usbDnTx:=p.usbDnTx;pins.usbTxEnable:=p.usbTxEnable;pins.usbPullup:=p.usbPullup
  status.aonReleased:=clocks.aonReset_n;status.servicesReleased:=clocks.serviceReset_n
  status.mainLevel:=clocks.mainClock.asBool;status.sourceStable:=clocks.stable;status.fault:=p.clockControl.fault
  status.coreReady:=digital.coreReady;status.coreSleeping:=digital.coreSleeping
  val causes=Module(new ResetCauses(qualifiedResets=true))
  causes.releases.get.cold:=resetDomains.released.coldAon;causes.releases.get.pin:=resetDomains.released.pinAon
  causes.clk:=clocks.aonClock;causes.coldReset_n:=clocks.coldReset_n
  causes.externalReset_n:=externalReset_n;causes.bypass:=porBypass;causes.brownout:=brownout
  status.resetCauses:=causes.causes
  p.resetReason:=causes.causes
}

/** Digital analog models replace only macros; production clock/reset logic stays. */
class SocAnalogModelTest(config: String,uartJson: String,romImage: String,
    i1Config: Option[SocI1Config]=Some(SocProduction.config()))
  extends DeadhorseSoc(config,uartJson,romImage,i1Config=i1Config,analogModels=true)
