package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib._
import deadhorse.bus.{BusFabric,BusRegion}
import deadhorse.bus_bridge.{BusBridge,DirectionPermit}
import deadhorse.mailbox.Mailbox
import deadhorse.uart.{Uart,UartWake}
import deadhorse.osc_ctrl.{OscCtrl,OscSleepTransfer}
import deadhorse.power_reset.PowerReset
import deadhorse.spi_host.SpiHost
import deadhorse.i2c_host.I2cHost
import deadhorse.usb.Usb
import deadhorse.gpio.Gpio
import deadhorse.timers.GeneralTimers
import deadhorse.aon_spi.AonSpi
import deadhorse.aon_gpio.AonGpio
import deadhorse.aon_timer.AonTimers
import deadhorse.dma.Dma
import deadhorse.pinmux.Pinmux
import deadhorse.lite_core.LiteHart
import deadhorse.watchdog.Watchdog
import deadhorse.boot_control.{BootControl,BootModeStrap}
import deadhorse.qspi.Qspi
import deadhorse.debug.{Debug,DebugSbaRouting}
import deadhorse.sram._

/** The production peripheral/bridge path, also tested at its CPU boundary.
  * All test-controller inputs are synchronous to their declared owning domain.
  */
class SocI1Peripherals(description: SocDescription, config: SocI1Config,
    sramTarget: SramTarget=SramTarget.Model,withRvfi: Boolean=true,sharedDomainReleases: Boolean=false,consolidatedOscillator: Boolean=false) extends RawModule {
  protected def testBusInjection: Boolean=false
  protected def wholeWatchdogReset(performance: Bool,lite: Bool): Bool=performance || lite
  protected def qspiServiceReset(main: Bool,aon: Bool): Bool=main
  val domainReleases=if(sharedDomainReleases) Some(IO(Input(new SocResetReleases))) else None
  val mainClock=IO(Input(Clock()));val coldReset_n=IO(Input(Bool()));val warmReset_n=IO(Input(Bool()))
  val mainServiceReset_n=IO(Input(Bool()));val main=IO(new LocalBus)
  val uartRx=IO(Input(Bool()));val uartTx=IO(Output(Bool()));val uartTxEnable=IO(Output(Bool()))
  val pins=IO(new SocI1Pins);val fastIrq=IO(Output(UInt(15.W)))
  val mainHold=IO(Output(Bool()))
  val performanceDebugMode=IO(Input(Bool()));val performanceReset_n=IO(Input(Bool()))
  val performanceHalt=IO(Output(Bool()));val performanceDebugGrant=IO(Output(Bool()));val performanceDebugFetch=IO(Output(Bool()))
  val debugReset=IO(Output(Bool()))
  val sramTest=IO(new SramPort(12));val sramOwn=IO(Output(Bool()));val sramReset_n=IO(Input(Bool()))
  val supervision=config.watchdog.map(_=>IO(Output(new Bundle {
    val performanceReset=Bool();val wholeReset=Bool();val warning=Bool()
  })))
  val performanceReady=config.watchdog.map(_=>IO(Input(Bool())))
  val performanceReleased=config.bootControl.map(_=>IO(Output(Bool())))
  val nativeXip=Some(IO(new LocalBus))
  val liteBootHeld=WireDefault(true.B);val liteBootDraining=WireDefault(false.B)
  val liteBootReleased=WireDefault(false.B);val liteBootQuiet=WireDefault(false.B)
  val performanceHold=WireDefault(false.B);val wholeHold=WireDefault(false.B);val usbWholeHold=WireDefault(false.B)
  val watchdogWarning=WireDefault(false.B);val watchdogDemand=WireDefault(false.B)
  val performancePause=WireDefault(true.B)
  val resetCauses=WireDefault(pins.resetReason);val crashCount=WireDefault(pins.crashCount)
  val dmaMemory=config.dma.map(_=>IO(Flipped(new LocalBus)))
  val inactivePads=Module(new SocInactivePads)
  inactivePads.pins<>pins.inactive
  for((name,width)<-Seq("qspi_dq"->4,"qspi_cs_n"->2,"qspi_sclk"->1,"actuator"->9,
      "imu_drdy"->1,"jtag_tck"->1,"jtag_tms"->1,"jtag_tdi"->1,"jtag_tdo"->1,
      "gpio"->3,"timer"->4))
    require(description.pinWidth(name)==width,s"I1 inactive port width differs: $name")
  require(description.origin("lite")==0 && description.origin("performance")==1)
  require(description.region("mailbox").base==BigInt("40001000",16))
  def release(clock: Clock, raw: Bool): Bool = {
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=raw;r.released
  }
  val debugger=Module(new Debug(description.region("retained_sram").base,description.region("retained_sram").size,Some(config.sram),qualifiedResets=true))
  val bist=Module(new SramBist(aonWords=(description.region("retained_sram").size/4).toInt,qualifiedResets=true,sharedPinFence=true))
  bist.cold_n:=coldReset_n
  bist.clk:=mainClock;bist.aonClock:=pins.aonClock;bist.epoch_n:=coldReset_n && warmReset_n
  bist.mainReset_n:=sramReset_n
  bist.start:=debugger.bist.get.start;bist.keyed:=debugger.bist.get.keyed
  bist.authorized:=debugger.active && debugger.ndmReset
  sramTest<>bist.main;sramOwn:=bist.mainOwn
  debugger.bist.get.epoch_n:=bist.commandOpen
  debugger.bist.get.busy:=bist.busy;debugger.bist.get.done:=bist.done
  debugger.bist.get.failed:=bist.failed;debugger.bist.get.rejected:=bist.rejected
  debugger.bist.get.resetAck:=bist.resetAck;debugger.bist.get.failAddress:=bist.failAddress
  debugger.bist.get.result:=bist.result
  debugger.clk:=mainClock;debugger.por_n:=coldReset_n
  debugger.tck:=pins.inactive.jtagTck.asClock;debugger.tms:=pins.inactive.jtagTms;debugger.tdi:=pins.inactive.jtagTdi
  pins.inactive.jtagTdo:=debugger.tdo;pins.inactive.jtagTdoEnable:=debugger.tdoEnable
  debugReset:=debugger.ndmReset || bist.resetHold
  val warmRaw=warmReset_n && !wholeHold && !debugger.ndmReset && !bist.resetHold
  val releases=domainReleases.getOrElse {
    val d=Module(new SocResetDomains)
    d.mainClock:=mainClock;d.aonClock:=pins.aonClock;d.sourceClock:=pins.usbClock
    d.scanClock:=pins.inactive.jtagTck.asClock;d.cold_n:=coldReset_n;d.warm_n:=warmRaw
    d.pin_n:=warmReset_n
    d.aonQualified:=pins.aonServiceReset_n;d.mainQualified:=mainServiceReset_n;d.released
  }
  val mainUp=releases.warmMain;val aonUp=releases.warmAon
  val coldUp=releases.coldAon;val debugMainUp=releases.coldMain
  bist.domainReset.get.main:=debugMainUp;bist.domainReset.get.aon:=coldUp
  bist.pinFence.get.main:=releases.pinMainOpen;bist.pinFence.get.aon:=releases.pinAonOpen
  debugger.domainReset.get.main:=debugMainUp;debugger.domainReset.get.scan:=releases.coldScan
  val mainRaw=coldReset_n && warmRaw
  val aonRaw=mainRaw
  // T19 incoming reset predicates intentionally retain their old sources.
  val usbWarm=warmReset_n && !usbWholeHold && !debugger.ndmReset && !bist.resetHold
  val usbMainRaw=coldReset_n && usbWarm && pins.usbServiceReset_n
  val usbAonRaw=coldReset_n && usbWarm && pins.aonServiceReset_n
  val usbRaw=coldReset_n && usbWarm && pins.usbServiceReset_n
  bist.aonReset_n:=aonUp
  val controllerUp=aonUp
  val bootStrap=Module(new BootModeStrap)
  bootStrap.clk:=pins.aonClock;bootStrap.wholeReset_n:=aonUp
  bootStrap.qualified:=controllerUp;bootStrap.pad:=pins.inactive.gpioIn(1)
  val pwmUp=mainUp
  val usbAppUp=release(mainClock,usbMainRaw && usbRaw)
  val usbSlotUp=release(mainClock,usbMainRaw)
  def syncMain(value: Bool): Bool = {
    val s=Module(new CdcSync(1));s.clk:=pins.aonClock;s.reset_n:=controllerUp;s.in:=value.asUInt;s.out.asBool
  }
  val mainNames=description.fabric("main");val aonNames=description.fabric("aon")
  val mainRemote=Seq("retained_sram","power_reset_timer")
  val aonRemote=Seq.empty[String]
  def fabric(names: Seq[String], remote: Seq[String], masters: Int, clock: Clock, reset: Bool): BusFabric = {
    val f=Module(new BusFabric(masters,names.map { n =>
      val r=description.aperture(n)
      require(r.base+r.size<=BigInt("ffffffff",16),"Route-error sentinel must be unmapped")
      BusRegion(r.base,r.size,if(remote.contains(n)) 131080 else 128)
    }))
    f.clk:=clock;f.reset_n:=reset
    f.allow.foreach(_:=true.B);f.admit.foreach(_:=true.B);f.quiescent.foreach(_:=false.B)
    f
  }
  val mf=fabric(mainNames,mainRemote,3,mainClock,mainUp)
  debugger.memoryReset_n:=mainUp
  val perfEpoch=mainUp
  val liteEntryAck=WireDefault(false.B);val liteEpoch=WireDefault(false.B)
  val liteRequestMain=withClockAndReset(mainClock,(!debugMainUp).asAsyncReset) {
    val pending=RegInit(false.B)
    when(debugger.halt(0)) {pending:=true.B}
    when(liteEntryAck && liteEpoch || !debugger.active) {pending:=false.B}
    pending || debugger.halt(0)
  }
  withClockAndReset(mainClock,(!debugMainUp).asAsyncReset) {
    val owned=RegInit(false.B);val pending=RegInit(false.B);val parked=RegInit(false.B)
    val entered=withReset((!perfEpoch).asAsyncReset) {RegInit(false.B)}
    when(performanceDebugMode) {entered:=true.B}
    when(perfEpoch) {parked:=performanceDebugMode}
    when(debugger.halt(1)) {pending:=true.B}
    when(performanceDebugMode) {pending:=false.B}
    when(!perfEpoch && parked) {pending:=true.B}
    when(debugger.active && (debugger.halt(1) || pending)) {owned:=true.B}
    when(!debugger.active) {owned:=false.B;pending:=false.B;parked:=false.B;entered:=false.B}
    performanceDebugGrant:=owned;performanceDebugFetch:=owned && entered
    performanceHalt:=debugger.halt(1) || pending
  }
  def debugSync(value: Bool,clock: Clock): Bool={
    val q=Module(new CdcSync(1));q.clk:=clock;q.reset_n:=(if(clock eq mainClock) debugMainUp else coldUp);q.in:=value.asUInt;q.out.asBool
  }
  val debugActiveAon=debugSync(debugger.active,pins.aonClock)
  val haltLite=debugSync(liteRequestMain,pins.aonClock)
  val debugWake=debugSync(debugger.pendingTck,pins.aonClock)
  val liteOwned=WireDefault(false.B);val litePending=WireDefault(false.B);val liteStop=WireDefault(false.B)
  val liteInitialize=WireDefault(true.B)
  val liteClientUp=aonUp && !liteInitialize
  // Warm assertion must win a same-edge debug command even with main stopped.
  // The shared release supplies immediate quarantine; the synchronized lite
  // status supplies the later local HOLD/initialization acknowledgement.
  val liteResetSeen=mainUp && debugSync(liteClientUp,mainClock)
  val perfResetSeen=perfEpoch
  liteEpoch:=liteResetSeen
  debugger.hartReset:=Cat(!perfResetSeen,!liteResetSeen)
  debugger.unavailable:=Cat(!perfResetSeen,!liteResetSeen)
  debugger.ndmAck:=debugger.ndmReset && !mainUp && !debugSync(aonUp,mainClock)
  val nativeArb=Module(new BusFabric(2,Seq(BusRegion(0,BigInt(1)<<32))))
  nativeArb.clk:=mainClock;nativeArb.reset_n:=mainUp
  nativeArb.allow.foreach(_:=true.B);nativeArb.admit.foreach(_:=true.B);nativeArb.quiescent.foreach(_:=false.B)
  dmaMemory.get<>nativeArb.target(0)
  val retainedSba=Wire(new LocalBus)
  DebugSbaRouting.connect(debugger.system,debugger.systemRetained,retainedSba,nativeArb.master(1))
  ingress(mf.master(2),retainedSba,Seq("retained_sram"),Some(description.origin("gateway_debug")))
  val af=fabric(aonNames,aonRemote,2,pins.aonClock,aonUp)
  def hits(addr: UInt, allowed: Seq[String]): Bool = allowed.flatMap(description.expanded).map(r =>
    addr>=r.base.U && addr<(r.base+r.size).U).reduce(_ || _)
  protected def routeAddress(address: UInt, allowed: Bool): UInt=Mux(allowed,address,"hffffffff".U)
  def ingress(target: LocalBus, source: LocalBus, allowed: Seq[String], owner: Option[Int]): Unit = {
    target.req:=source.req;target.bits:=source.bits
    target.bits.addr:=routeAddress(source.bits.addr,hits(source.bits.addr,allowed))
    owner.foreach(n=>target.bits.origin:=n.U)
    source.gnt:=target.gnt;source.rvalid:=target.rvalid;source.rdata:=target.rdata;source.err:=target.err
  }
  ingress(mf.master(0),main,mainNames,Some(description.origin("performance")))
  val debugLeafSource=Wire(new LocalBus);val debugLeafOffer=WireDefault(false.B);val liteRouteBusy=WireDefault(false.B)
  debugLeafSource.req:=false.B;debugLeafSource.bits:=0.U.asTypeOf(new BusPayload)
  val liteHart=Some(Module(new LiteHart(description.origin("lite"),withDebug=true,withRVFI=withRvfi,withInitialize=true)))
  liteHart.foreach { hart =>
      hart.clk:=pins.aonClock;hart.reset_n:=aonUp;hart.initialize.get:=liteInitialize;hart.irq:=pins.aonIrq
      hart.debug.get.request:=haltLite || litePending;hart.debug.get.allowEntry:=liteOwned;hart.debug.get.stop:=liteStop
      if(testBusInjection) {
        ingress(af.master(0),pins.lite,aonNames,Some(description.origin("lite")))
        hart.bus.gnt:=false.B;hart.bus.rvalid:=false.B;hart.bus.rdata:=0.U;hart.bus.err:=false.B
      } else {
        val route=Module(new SocDebugRoute(description.region("debug_mem").base,description.region("debug_mem").size))
        route.clk:=pins.aonClock;route.reset_n:=aonUp;route.bus<>hart.bus;liteRouteBusy:=route.busy
        ingress(af.master(0),route.ordinary,aonNames,Some(description.origin("lite")))
        debugLeafSource<>route.debug;debugLeafOffer:=route.debug.req
      }
      // The test-master port is inert in the real-hart profile, including its
      // claimed halted state. Only the core controls retained-memory ownership.
      if(!testBusInjection) {
        pins.lite.gnt:=false.B;pins.lite.rvalid:=false.B;pins.lite.rdata:=0.U;pins.lite.err:=false.B
      }
  }
  val liteMode=liteHart.get.debug.get.mode
  liteEntryAck:=debugSync(liteMode,mainClock)
  debugger.hartMode:=Cat(performanceDebugMode,liteEntryAck)
  val liteHalted=if(testBusInjection) pins.liteHalted else liteHart.get.halted
  val leaf=Module(new BusBridge(qualifiedResets=true))
  leaf.sourceClock:=pins.aonClock;leaf.targetClock:=mainClock
  leaf.sourceReset_n:=aonUp;leaf.targetReset_n:=mainUp
  leaf.source<>debugLeafSource;leaf.offer:=debugLeafOffer
  val leafPermit=Module(new DirectionPermit(qualifiedResets=true))
  leafPermit.aonClock:=pins.aonClock;leafPermit.mainClock:=mainClock
  leafPermit.aonReset_n:=aonUp;leafPermit.mainReset_n:=mainUp
  leafPermit.requestAon:=leaf.permitRequest;leafPermit.requestMain:=false.B;leaf.permit:=leafPermit.permitAon
  val dmArb=Module(new BusFabric(2,Seq(BusRegion(description.region("debug_mem").base,0x1000))))
  dmArb.clk:=mainClock;dmArb.reset_n:=mainUp
  dmArb.allow.foreach(_:=true.B);dmArb.admit.foreach(_:=true.B);dmArb.quiescent.foreach(_:=false.B)
  dmArb.master(0)<>leaf.target;debugger.memory<>dmArb.target(0)
  val nativeRoute=Module(new SocDebugRoute(description.region("debug_mem").base,0x1000))
  nativeRoute.clk:=mainClock;nativeRoute.reset_n:=mainUp;nativeRoute.bus<>nativeXip.get
  dmArb.master(1)<>nativeRoute.debug
  val toAon=Module(new BusBridge(qualifiedResets=true))
  toAon.sourceClock:=mainClock;toAon.targetClock:=pins.aonClock
  toAon.sourceReset_n:=mainUp;toAon.targetReset_n:=aonUp
  val permits=Module(new DirectionPermit(qualifiedResets=true))
  permits.aonClock:=pins.aonClock;permits.mainClock:=mainClock
  permits.aonReset_n:=aonUp;permits.mainReset_n:=mainUp
  permits.requestAon:=false.B;permits.requestMain:=toAon.permitRequest
  toAon.permit:=permits.permitMain
  ingress(af.master(1),toAon.target,Seq("retained_sram","power_reset_timer","future_bridge"),None)
  def remote(f: BusFabric,names: Seq[String],remoteNames: Seq[String],bridge: BusBridge,clock: Clock,reset: Bool): Unit = {
    val indices=remoteNames.map(names.indexOf);require(indices.forall(_>=0))
    val req=VecInit(indices.map(i=>f.target(i).req))
    bridge.source.req:=req.asUInt.orR
    // Every target payload is the root fabric's same captured request.
    bridge.source.bits:=f.target(indices.head).bits
    bridge.offer:=indices.map(i=>f.waiting(i)).reduce(_ || _)
    withClockAndReset(clock,(!reset).asAsyncReset) {
      val selected=RegInit(0.U(log2Ceil(indices.size).W))
      val pending=RegInit(false.B)
      val take=bridge.source.req && bridge.source.gnt
      when(take) {selected:=PriorityEncoder(req.asUInt);pending:=true.B}
      when(bridge.source.rvalid) {pending:=false.B}
      assert(PopCount(req)<=1.U)
      assert(!take || !pending)
      assert(!bridge.source.rvalid || pending)
      for((i,j)<-indices.zipWithIndex) {
        assert(f.target(i).bits.asUInt===bridge.source.bits.asUInt)
        f.admit(i):=bridge.admit
        f.target(i).gnt:=bridge.source.gnt
        f.target(i).rvalid:=bridge.source.rvalid && selected===j.U
        f.target(i).rdata:=bridge.source.rdata;f.target(i).err:=bridge.source.err
      }
    }
  }
  remote(mf,mainNames,mainRemote,toAon,mainClock,mainUp)
  def drain(f: BusFabric,children: Seq[BusFabric],bridge: BusBridge,clock: Clock,reset: Bool): Unit = {
    val credit=Module(new SocDrainCredit);credit.clk:=clock;credit.reset_n:=reset
    // BusFabric captures before publishing its registered grant. Peer reset
    // may withdraw req in between, but the committed beat must still drain.
    credit.accepted:=bridge.target.gnt;credit.response:=bridge.target.rvalid
    // An outer timeout is not a cancellation of a nested fabric/endpoint.
    // Its poison must drain too before acknowledging that no old work remains.
    val isolated=(Seq(f)++children).map(_.isolated.asUInt.orR).reduce(_||_)
    bridge.quiescent:=credit.empty && !bridge.target.rvalid && !isolated
  }
  def stub(bus: LocalBus,clock: Clock,reset: Bool): Unit = {
    val s=Module(new SocErrorTarget);s.clk:=clock;s.reset_n:=reset;s.bus<>bus
  }
  val serialNames=description.group("serial")
  val serial=fabric(serialNames,Seq.empty,1,mainClock,mainUp)
  serial.master(0)<>mf.target(mainNames.indexOf("serial"))
  val gatewayNames=description.group("gateway")
  val gateway=fabric(gatewayNames,Seq.empty,1,mainClock,mainUp)
  protected def nestedDrain(): SocNestedDrain=new SocNestedDrain
  def nestedQuiet(child: BusFabric,clock: Clock=mainClock,reset: Bool=mainUp): Bool = {
    val d=Module(nestedDrain());d.clk:=clock;d.reset_n:=reset
    d.request:=child.master(0).req;d.grant:=child.master(0).gnt;d.response:=child.master(0).rvalid
    d.waiting:=child.waiting.asUInt.orR;d.isolated:=child.isolated.asUInt.orR
    d.targetRequest:=child.target.map(_.req).reduce(_||_)
    d.targetResponse:=child.target.map(_.rvalid).reduce(_||_)
    d.quiescent
  }
  mf.quiescent(mainNames.indexOf("serial")):=nestedQuiet(serial)
  mf.quiescent(mainNames.indexOf("gateway")):=nestedQuiet(gateway)
  val ioFabric=config.io.map { _ =>
    val regions=Seq("gpio").map(description.ioRegion)++config.pinmux.map(_=>description.pinmuxRegion)
    val f=Module(new BusFabric(1,regions.map(r=>BusRegion(r.base,r.size,128))))
    f.clk:=mainClock;f.reset_n:=mainUp
    f.allow.foreach(_:=true.B);f.admit.foreach(_:=true.B);f.quiescent.foreach(_:=false.B)
    f.master(0)<>serial.target(serialNames.indexOf("gpio_pinmux"))
    serial.quiescent(serialNames.indexOf("gpio_pinmux")):=nestedQuiet(f)
    f
  }
  drain(dmArb,Seq.empty,leaf,mainClock,mainUp)
  debugger.systemUp:=mainUp
  debugger.systemQuiet:=mainUp && !nativeArb.waiting.asUInt.orR &&
    !nativeArb.isolated.asUInt.orR && !mf.waiting.asUInt.orR && !mf.isolated.asUInt.orR &&
    !debugger.system.rvalid && !toAon.clockRequest
  // Elaboration-only references for passive public-interface test monitors.
  // These accessors add no hardware ports, wires or behavior.
  private var constructedBoot=Option.empty[BootControl]
  def bootControlBlock: BootControl=constructedBoot.get
  private var constructedWatchdogs=Seq.empty[Watchdog]
  def watchdogBlocks: Seq[Watchdog]=constructedWatchdogs
  val powerFabric=config.watchdog.map {json=>
    val regions=Seq(description.ioRegion("aon_timer"))++(0 until 2).map(description.watchdogRegion)++
      config.bootControl.toSeq.map(_=>description.bootControlRegion)++Seq(description.oscControlRegion,description.powerResetRegion)
    val f=Module(new BusFabric(1,regions.map(r=>BusRegion(r.base,r.size,128))))
    f.clk:=pins.aonClock;f.reset_n:=aonUp
    f.allow.foreach(_:=true.B);f.admit.foreach(_:=true.B);f.quiescent.foreach(_:=false.B)
    f.master(0)<>af.target(aonNames.indexOf("power_reset_timer"))
    af.quiescent(aonNames.indexOf("power_reset_timer")):=nestedQuiet(f,pins.aonClock,aonUp)
    val channels=Seq("performance","lite").zipWithIndex.map {case(owner,index)=>
      val w=Module(new Watchdog(json,description.watchdogRegion(index).base,description.origin(owner),withPause=index==0))
      w.clk:=pins.aonClock;w.por_n:=coldUp;w.reset_n:=aonUp;w.bus<>f.target(index+1);w.pause.foreach(_:=performancePause);w
    }
    constructedWatchdogs=channels
    performanceHold:=channels(0).resetHold;wholeHold:=wholeWatchdogReset(channels(0).resetHold,channels(1).resetHold)
    usbWholeHold:=channels(1).resetHold
    watchdogWarning:=channels(0).warn
    watchdogDemand:=channels.map(w=>w.active || w.resetHold).reduce(_||_)
    resetCauses:=Cat(channels(1).cause,channels(0).cause)
    withClockAndReset(pins.aonClock,(!coldUp).asAsyncReset) {
      val sum=channels(0).crashes+&channels(1).crashes
      crashCount:=RegNext(Mux(sum(32),"hffffffff".U,sum(31,0)),0.U)
    }
    val nmi=Module(new CdcSync(1));nmi.clk:=mainClock;nmi.reset_n:=mainUp;nmi.in:=watchdogWarning.asUInt
    supervision.get.performanceReset:=performanceHold;supervision.get.wholeReset:=wholeHold
    supervision.get.warning:=nmi.out.asBool
    config.bootControl.foreach {path=>
      val boot=Module(new BootControl(path,description.bootControlRegion.base,description.origin("performance")))
      constructedBoot=Some(boot)
      boot.clk:=pins.aonClock;boot.epochReset_n:=coldUp;boot.reset_n:=aonUp
      boot.quiet:=liteBootQuiet
      // Pending reset-halt cannot block the release needed for debug acquisition.
      // It still inhibits application start; actual ownership blocks commands.
      boot.debugOwned:=liteOwned || (!liteBootHeld && (haltLite || litePending))
      boot.bootMode:=bootStrap.value;boot.warmHold:= !aonUp
      boot.warmReleasePending:=releases.warmAonPending
      boot.bus<>f.target(3)
      liteBootHeld:=boot.held;liteBootDraining:=boot.draining;liteBootReleased:=boot.released
      performanceReleased.get:=true.B
    }
    f
  }
  val powerReset=Module(new PowerReset(config.powerReset,description.powerResetRegion.base))
  powerReset.clk:=pins.aonClock;powerReset.reset_n:=aonUp
  powerReset.bus<>powerFabric.get.target(5)
  // Capture in the producer's clock domain before synchronization. A short
  // ndmreset episode must remain visible even if AON was stopped throughout.
  val debugResetHistory=withClockAndReset(mainClock,(!debugMainUp).asAsyncReset) {
    val seen=RegInit(false.B);when(debugger.ndmReset) {seen:=true.B};seen
  }
  powerReset.causes:=Cat(debugSync(debugResetHistory,pins.aonClock),resetCauses(1,0),pins.resetReason(2,0))
  pins.clockControl.threshold:=powerReset.threshold
  val oscillator=Module(new OscCtrl(config.oscCtrl,description.oscControlRegion.base,withWarmInitialize=consolidatedOscillator))
  oscillator.clk:=pins.aonClock
  oscillator.reset_n:=aonUp && pins.clockControl.reset_n
  if(consolidatedOscillator) {
    oscillator.epochReset_n:=releases.coldAon
    oscillator.initialize.get:=releases.warmInitialize
    oscillator.clearAck.get:=pins.clockControl.clearAck
    pins.clockControl.epochClear:=oscillator.epochClear.get
  } else {
    oscillator.epochReset_n:=release(pins.aonClock,coldReset_n && warmReset_n && pins.clockControl.reset_n)
    pins.clockControl.epochClear:=false.B
  }
  // OscCtrl resynchronizes the stretched reset as retained-policy data and
  // keeps MMIO closed until its synchronous configuration reset completes.
  oscillator.bus<>powerFabric.get.target(4)
  val oscillatorSafetyHold=WireDefault(false.B)
  oscillator.mainHold:=oscillatorSafetyHold
  oscillator.oscillatorHold:=pins.usbClockRequest
  oscillator.coreIdle:=syncMain(pins.clockControl.coreIdle)
  oscillator.gateClosed:=pins.clockControl.closed;oscillator.stable:=pins.clockControl.stable
  performancePause:= !oscillator.gateRequest
  pins.clockControl.oscillatorOn:=oscillator.oscillatorOn
  pins.clockControl.gateRequest:=oscillator.gateRequest
  pins.clockControl.authorized:=oscillator.authorized
  pins.clockControl.qualify:=oscillator.qualify;pins.clockControl.count:=oscillator.count
  pins.clockControl.fault:=oscillator.fault
  drain(af,powerFabric.toSeq,toAon,pins.aonClock,aonUp)
  gateway.master(0)<>mf.target(mainNames.indexOf("gateway"))
  stub(gateway.target(gatewayNames.indexOf("gateway_reserved")),mainClock,mainUp)
  val qspiHold=WireDefault(false.B)
  private var constructedQspi=Option.empty[Qspi]
  def qspiBlock: Option[Qspi]=constructedQspi
  config.qspi.foreach {json=>
    val flash=Module(new Qspi(json,description.qspiRegion.base,withXip=true))
    constructedQspi=Some(flash)
    flash.clk:=mainClock;flash.reset_n:=qspiServiceReset(mainUp,aonUp);flash.bus<>serial.target(serialNames.indexOf("qspi_control"))
    flash.dqIn:=pins.inactive.qspiDqIn
    pins.inactive.qspiDqOut:=flash.dqOut;pins.inactive.qspiDqEnable:=flash.dqEnable
    pins.inactive.qspiSclk:=flash.sclk;pins.inactive.qspiSclkEnable:=flash.sclkEnable
    pins.inactive.qspiCs_n:=flash.cs_n;pins.inactive.qspiCsEnable:=flash.csEnable
    qspiHold:=flash.clockHold
    flash.xip.foreach(_<>nativeRoute.ordinary)
  }
  val pwmIrq=WireDefault(false.B);val pwmHold=WireDefault(false.B)
  val pwmRequests=WireDefault(0.U(9.W));val pwmAck=WireDefault(0.U(9.W))
  val muxValues=WireDefault(VecInit(Seq.fill(3)(0.U(3.W))))
  val muxEnables=WireDefault(VecInit(Seq.fill(3)(0.U(3.W))))
  val pinmuxHold=WireDefault(false.B)
  val timers=Module(new GeneralTimers(config.io.get.timers,config.mainMHz,base=description.pwmRegion.base,watchdog=true))
  timers.clk:=mainClock;timers.reset_n:=mainUp;timers.owner:=description.origin("performance").U
  timers.watchdogReset_n.get:=pwmUp;timers.performanceReady.get:=performanceReady.get
  timers.bus<>mf.target(mainNames.indexOf("general_timers"));timers.dmaAck:=pwmAck;pwmRequests:=timers.dmaRequest
  pwmIrq:=timers.irq.orR;pwmHold:=timers.clockHold
  muxValues(1):=timers.pinsOut(2,0);muxEnables(1):=timers.pinsEnable(2,0)
  muxValues(2):=timers.pinsOut(2,0);muxEnables(2):=timers.pinsEnable(2,0)
  val mainPadValues=WireDefault(0.U(3.W));val mainPadEnables=WireDefault(0.U(3.W))
  val mainGpioInputs=WireDefault(pins.inactive.gpioIn)
  stub(mf.target(mainNames.indexOf("future_bridge")),mainClock,mainUp)
  for(n<-Seq("future_bridge"))
    stub(af.target(aonNames.indexOf(n)),pins.aonClock,aonUp)
  val ioMainHold=WireDefault(false.B);val ioAonHold=WireDefault(false.B)
  val ioWake=WireDefault(false.B);val ioAonIrq=WireDefault(false.B)
  val timerWake=WireDefault(false.B);val gpioWake=WireDefault(false.B)
  val gpioIrq=WireDefault(false.B);val timerIrq=WireDefault(false.B)
  val timeNow=WireDefault(timers.timeNow)
  config.io.foreach { c =>
    def toMainLevel(value: Bool): Bool = {
      val s=Module(new CdcSync(1));s.clk:=mainClock;s.reset_n:=mainUp;s.in:=value.asUInt;s.out.asBool
    }
    val gpio=Module(new Gpio(c.gpio,base=description.ioRegion("gpio").base,qualifiedResets=true))
    gpio.clk:=mainClock;gpio.aonClock:=pins.aonClock;gpio.reset_n:=mainUp;gpio.aonReset_n:=aonUp
    gpio.owner:=description.origin("performance").U;gpio.bus<>ioFabric.get.target(0)
    gpio.pinsIn:=mainGpioInputs;mainPadValues:=gpio.pinsOut;mainPadEnables:=gpio.pinsEnable
    muxValues(0):=gpio.pinsOut;muxEnables(0):=gpio.pinsEnable
    val aonTimer=Module(new AonTimers(c.aonTimer,base=description.ioRegion("aon_timer").base))
    aonTimer.clk:=pins.aonClock;aonTimer.reset_n:=aonUp;aonTimer.owner:=description.origin("lite").U
    aonTimer.bus<>powerFabric.get.target(0)
    gpioIrq:=gpio.irq;timerIrq:=toMainLevel(aonTimer.irq)
    ioMainHold:=gpio.clockHold || timers.clockHold || ioFabric.get.waiting.asUInt.orR
    ioAonHold:=aonTimer.clockHold
    ioWake:=aonTimer.wake || gpio.wake
    timerWake:=aonTimer.wake;gpioWake:=gpio.wake
    ioAonIrq:=aonTimer.irq || gpio.wake
  }
  config.pinmux.foreach {json=>
    val p=Module(new Pinmux(json,base=description.pinmuxRegion.base,watchdog=true))
    p.clk:=mainClock;p.reset_n:=mainUp;p.owner:=description.origin("performance").U
    p.watchdogReset_n.foreach(_:=pwmUp)
    p.bus<>ioFabric.get.target(1);p.values:=muxValues;p.enables:=muxEnables
    p.timerValues:=timers.pinsOut;p.timerEnables:=timers.pinsEnable;p.timerRunning:=timers.running
    p.timerInputs:=pins.inactive.timerIn;timers.captureIn:=p.captures;timers.captureValid:=p.captureValid
    pins.inactive.actuatorOut:=p.timerOut(8,0);pins.inactive.actuatorEnable:=p.timerEnable(8,0)
    pins.inactive.timerOut:=p.timerOut(12,9);pins.inactive.timerEnable:=p.timerEnable(12,9)
    mainPadValues:=p.pinsOut;mainPadEnables:=p.pinsEnable;pinmuxHold:=p.clockHold
  }
  val aonIoNames=description.group("aon_io")
  val aonIo=fabric(aonIoNames,Seq.empty,1,pins.aonClock,aonUp)
  aonIo.master(0)<>af.target(aonNames.indexOf("aon_io"))
  af.quiescent(aonNames.indexOf("aon_io")):=nestedQuiet(aonIo,pins.aonClock,aonUp)
  val aonSpi=Module(new AonSpi(config.aonSpi,description.region("aon_spi").base))
  aonSpi.clk:=pins.aonClock;aonSpi.reset_n:=aonUp;aonSpi.bus<>aonIo.target(aonIoNames.indexOf("aon_spi"))
  aonSpi.miso:=pins.inactive.gpioIn(2)
  val aonGpio=Module(new AonGpio(config.aonGpio,description.region("aon_gpio").base))
  aonGpio.clk:=pins.aonClock;aonGpio.reset_n:=aonUp;aonGpio.bus<>aonIo.target(aonIoNames.indexOf("aon_gpio"))
  aonGpio.pinsIn:=Cat(pins.aonExtraIn,pins.inactive.gpioIn)
  aonGpio.mainEnables:=mainPadEnables
  aonGpio.mainAvailable:= !pins.clockControl.closed && oscillator.authorized
  aonGpio.spiEnabled:=aonSpi.pinsEnable;aonGpio.spiBusy:= !aonSpi.cs_n
  val ownerSync=Module(new CdcSync(3));ownerSync.clk:=mainClock;ownerSync.reset_n:=mainUp;ownerSync.in:=aonGpio.ownerRequest
  val ownerAck=withClockAndReset(mainClock,(!mainUp).asAsyncReset) {
    val ack=RegInit(VecInit(Seq.fill(3)(false.B)))
    for(i<-0 until 3) {
      // Ownership changes only while the prior main producer is disabled.
      // A granted AON owner masks later main-enable writes until handback.
      when(!mainPadEnables(i)) {ack(i):=ownerSync.out(i)}
    }
    ack.asUInt
  }
  aonGpio.mainAck:=ownerAck
  val aonValues=(aonGpio.pinsOut & Mux(aonGpio.spiSelected,48.U(6.W),63.U(6.W))) | Mux(aonGpio.spiSelected && aonSpi.pinsEnable,
    Cat(0.U(2.W),aonSpi.cs_n,false.B,aonSpi.mosi,aonSpi.sclk),0.U(6.W))
  val aonEnables=aonGpio.pinsEnable | Mux(aonGpio.spiSelected && aonSpi.pinsEnable,11.U(6.W),0.U(6.W))
  val aonSelected=aonGpio.ownerActive
  pins.inactive.gpioOut:=(aonValues(2,0) & aonSelected) | (mainPadValues & ~aonSelected)
  pins.inactive.gpioEnable:=(aonEnables(2,0) & aonSelected) | (mainPadEnables & ~aonSelected & ~ownerAck)
  pins.aonExtraOut:=aonValues(5,3);pins.aonExtraEnable:=aonEnables(5,3)
  mainGpioInputs:=pins.inactive.gpioIn & ~aonSelected
  val mailbox=Module(new Mailbox(config.mailbox,qualifiedResets=true))
  mailbox.mainClock:=mainClock;mailbox.aonClock:=pins.aonClock
  mailbox.mainReset_n:=mainUp;mailbox.aonReset_n:=aonUp
  mailbox.main<>mf.target(mainNames.indexOf("mailbox"));mailbox.aon<>af.target(aonNames.indexOf("mailbox"))
  pins.aonIrq:=withClockAndReset(pins.aonClock,(!aonUp).asAsyncReset) {
    RegNext(mailbox.irq(0) || ioAonIrq || aonSpi.irq || aonGpio.irq,false.B)
  }
  val uartSleep=Module(new OscSleepTransfer(qualifiedResets=true))
  uartSleep.aon:=pins.aonClock;uartSleep.main:=mainClock
  uartSleep.aonReset_n:=aonUp;uartSleep.mainReset_n:=mainUp
  uartSleep.requested:=oscillator.sleepPreparing;uartSleep.modes:=oscillator.uartModes
  val uartWake=(0 until 3).map {i=>
    val monitor=Module(new UartWake(qualifiedReset=true))
    monitor.clk:=pins.aonClock;monitor.reset_n:=controllerUp
    monitor.rx:=(if(i==0) uartRx else pins.uartRx(i-1))
    monitor.invert:=oscillator.uartPolarity(i);monitor.armed:=oscillator.uartWakeArmed(i)
    monitor.clear:=oscillator.wakeClear;monitor.wake
  }
  val uarts=(0 until 3).map { i =>
    val name=s"uart$i";val u=Module(new Uart(config.uart,base=description.region(name).base))
    u.clk:=mainClock;u.reset_n:=mainUp;u.owner:=description.origin("performance").U
    u.bus<>serial.target(serialNames.indexOf(name));u.rx:=(if(i==0) uartRx else pins.uartRx(i-1))
    u.sleepRequest:=uartSleep.applied;u.sleepMode:=uartSleep.appliedModes(2*i+1,2*i)
    if(i==0) {uartTx:=u.tx;uartTxEnable:=u.txEnable}
    else {pins.uartTx(i-1):=u.tx;pins.uartTxEnable(i-1):=u.txEnable}
    u
  }
  val spi=Module(new SpiHost(config.spi,base=description.region("spi_host").base))
  spi.clk:=mainClock;spi.reset_n:=mainUp;spi.owner:=description.origin("performance").U
  spi.bus<>serial.target(serialNames.indexOf("spi_host"));spi.miso:=pins.spiMiso;spi.timeNow:=timeNow
  spi.sleepRequest:=false.B;spi.sleepEnable:=false.B
  pins.spiSclk:=spi.sclk;pins.spiMosi:=spi.mosi;pins.spiCs_n:=spi.cs_n;pins.spiEnable:=spi.pinsEnable
  val dmaIrq=WireDefault(false.B);val dmaHold=WireDefault(false.B)
  config.dma.foreach { json=>
    val ram=description.region("performance_sram")
    val dma=Module(new Dma(json,description.dmaEndpoints,ram.base,ram.size,description.region("dma").base))
    dma.clk:=mainClock;dma.reset_n:=mainUp;dma.owner:=description.origin("performance").U
    dma.bus<>serial.target(serialNames.indexOf("dma"));nativeArb.master(0)<>dma.memory
    ingress(mf.master(1),dma.peripheral,Seq("uart0","uart1","uart2","spi_host","general_timers"),Some(description.origin("performance")))
    dma.requests:=Cat(pwmRequests,spi.dmaRxRequest,spi.dmaTxRequest,
      VecInit(uarts.flatMap(u=>Seq(u.dmaTxRequest,u.dmaRxRequest))).asUInt)
    pwmAck:=dma.pwmAck;dmaIrq:=dma.irq;dmaHold:=dma.clockHold
  }
  val i2c=Module(new I2cHost(config.i2c,base=description.region("i2c_host").base))
  i2c.clk:=mainClock;i2c.reset_n:=mainUp;i2c.owner:=description.origin("performance").U
  i2c.bus<>serial.target(serialNames.indexOf("i2c_host"));i2c.sclIn:=pins.i2cSclIn;i2c.sdaIn:=pins.i2cSdaIn
  i2c.sleepRequest:=false.B;i2c.sleepEnable:=false.B
  pins.i2cSclLow:=i2c.sclLow;pins.i2cSdaLow:=i2c.sdaLow;pins.i2cEnable:=i2c.pinsEnable
  val acceptedLiteStart=withClockAndReset(pins.aonClock,(!aonUp).asAsyncReset) {
    val priorRelease=RegNext(liteBootReleased,false.B)
    val pending=RegInit(false.B)
    when(liteBootReleased && !priorRelease) {pending:=true.B}
    when(liteBootHeld || liteBootDraining) {pending:=false.B}
    val start=pending && liteClientUp && liteBootReleased && !liteBootDraining &&
      !liteOwned && !haltLite && !litePending
    when(start) {pending:=false.B}
    start
  }
  pins.liteStart:=acceptedLiteStart;pins.liteEntry:=description.region("retained_sram").base.U
  liteHart.foreach {hart=>
    hart.start:=(if(testBusInjection) false.B else acceptedLiteStart)
    hart.entry:=description.region("retained_sram").base.U
  }
  val retained=Module(new SocRetainedMemory(description,debugAccess=true,sramTarget=sramTarget,bistEnabled=true))
  retained.testPort.get<>bist.aon;retained.testOwn.get:=bist.aonOwn
  retained.clk:=pins.aonClock;retained.reset_n:=aonUp
  retained.bus<>af.target(aonNames.indexOf("retained_sram"))
  retained.debugWriteAllowed.get:=liteMode || liteBootHeld
  retained.bootHeld:=liteBootHeld && liteHart.get.initialized.get && !liteOwned
  liteBootQuiet:=liteHart.get.debugIdle.get && !retained.busy &&
    !af.waiting.asUInt.orR && !af.isolated.asUInt.orR && !debugLeafOffer && !liteRouteBusy &&
    !leaf.clockRequest && !leaf.source.rvalid && !af.target.map(p=>p.req || p.rvalid).reduce(_||_)
  withClockAndReset(pins.aonClock,(!coldUp).asAsyncReset) {
    val owned=RegInit(false.B);val resetting=RegInit(false.B)
    val pending=RegInit(false.B);val parked=RegInit(false.B)
    when(liteClientUp) {parked:=liteMode}
    when(haltLite) {pending:=true.B}
    when(liteMode) {pending:=false.B}
    when(!liteClientUp && parked) {pending:=true.B}
    when(!debugActiveAon) {pending:=false.B;parked:=false.B}
    litePending:=pending
    when(debugActiveAon && (haltLite || pending) && !liteBootHeld && !liteBootDraining && !retained.busy) {owned:=true.B}
    val tearDown=owned && !debugActiveAon && liteHalted
    liteStop:=tearDown || liteBootDraining
    when(tearDown && liteHart.get.debugIdle.get) {resetting:=true.B;owned:=false.B}
    when(resetting && liteHart.get.initialized.get) {resetting:=false.B}
    when(owned && !debugActiveAon && !liteHalted) {owned:=false.B}
    // Whole/service reset invalidates execution and transport ownership, but
    // preserves the pending halt needed after the new explicit boot release.
    when(!aonUp) {owned:=false.B;resetting:=false.B}
    liteOwned:=owned;liteInitialize:=resetting || liteBootHeld
  }
  val usbIrq=WireDefault(false.B)
  val usbTarget=gateway.target(gatewayNames.indexOf("usb"))
  if(config.realUsb) {
    val slot=Module(new SocResetSlot)
    slot.clk:=mainClock;slot.reset_n:=usbSlotUp;slot.endpointReset_n:=usbMainRaw && usbRaw;slot.endpointReady:=usbAppUp
    slot.bus<>usbTarget
    val usb=Module(new Usb(config.usb,base=description.region("usb").base))
    usb.appClock:=mainClock;usb.usbClock:=pins.usbClock;usb.aonClock:=pins.aonClock
    usb.appReset_n:=usbMainRaw;usb.usbReset_n:=usbRaw;usb.aonReset_n:=usbAonRaw
    usb.bus<>slot.target;usb.owner:=description.origin("performance").U
    usb.vbus:=pins.usbVbus;usb.dpRx:=pins.usbDpRx;usb.dnRx:=pins.usbDnRx
    pins.usbDpTx:=usb.dpTx;pins.usbDnTx:=usb.dnTx;pins.usbTxEnable:=usb.txEnable;pins.usbPullup:=usb.pullupEnable
    pins.usbWake:=usb.wake;pins.usbClockRequest:=usb.usbClockRequest;usbIrq:=usb.irq
    gateway.admit(gatewayNames.indexOf("usb")):=usbAppUp
    gateway.quiescent(gatewayNames.indexOf("usb")):=slot.quiescent
  } else {
    stub(usbTarget,mainClock,mainUp)
    pins.usbDpTx:=true.B;pins.usbDnTx:=false.B;pins.usbTxEnable:=false.B;pins.usbPullup:=false.B
    pins.usbWake:=false.B;pins.usbClockRequest:=false.B
  }
  protected def interruptIndex(name: String): Int=description.interrupt(name)
  val irq=WireDefault(0.U(15.W))
  val sources=(0 until 3).map(i=>s"uart$i"->uarts(i).irq) ++ Seq("spi_host"->spi.irq,"i2c_host"->i2c.irq,"mailbox"->mailbox.irq(1),"usb"->usbIrq,"general_timers"->timers.irq(0),"timer1"->timers.irq(1),"timer2"->timers.irq(2),"dma"->dmaIrq) ++
    Seq("gpio_pinmux"->gpioIrq,"power_reset_timer"->timerIrq)
  irq:=sources.map {case(n,v)=>v.asUInt<<interruptIndex(n)}.reduce(_|_)
  fastIrq:=irq
  val held=withClockAndReset(mainClock,(!mainUp).asAsyncReset) {
    RegNext(uarts.map(_.clockHold).reduce(_||_) || spi.clockHold || i2c.clockHold || ioMainHold || pwmHold || dmaHold || pinmuxHold || qspiHold ||
      debugger.hold || bist.busy || leaf.targetClockHold || dmArb.waiting.asUInt.orR || nativeRoute.busy ||
      mf.waiting.asUInt.orR || serial.waiting.asUInt.orR || gateway.waiting.asUInt.orR,false.B)
  }
  mainHold:=held
  val fromMain=syncMain(held || toAon.clockRequest || mailbox.wakePeer(1))
  oscillator.wake:=Cat(debugWake || pins.clockControl.jtagWake,mailbox.wakePeer(0),
    pins.usbWake,VecInit(uartWake).asUInt,gpioWake,timerWake)
  oscillatorSafetyHold:=aonGpio.ownershipBusy || !uartSleep.settled || fromMain || mailbox.wakePeer(0) ||
    watchdogWarning || performanceHold || wholeHold || debugWake || leaf.clockRequest || debugActiveAon
  withClockAndReset(pins.aonClock,(!coldUp).asAsyncReset) {
    pins.mainDemand:=RegNext(fromMain || mailbox.wakePeer(0) || pins.usbWake || ioWake ||
      watchdogWarning || performanceHold || wholeHold || debugWake || leaf.clockRequest || debugActiveAon,false.B)
    pins.aonDemand:=RegNext(fromMain || toAon.targetClockHold || af.waiting.asUInt.orR ||
      retained.busy || aonGpio.ownershipBusy || aonSpi.irq || aonGpio.irq || pins.usbWake || ioAonHold || ioWake ||
      liteHart.get.clockHold || watchdogDemand || debugWake || leaf.clockRequest || debugActiveAon,false.B)
  }
}
