package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib._
import deadhorse.bus.{BusFabric,BusRegion}
import deadhorse.bus_bridge.{BusBridge,DirectionPermit}
import deadhorse.mailbox.Mailbox
import deadhorse.uart.Uart
import deadhorse.spi_host.SpiHost
import deadhorse.i2c_host.I2cHost
import deadhorse.i2c_recovery_loader.RecoveryLoader
import deadhorse.usb.Usb
import deadhorse.gpio.Gpio
import deadhorse.timers.MainTimers
import deadhorse.aon_timer.AonTimers
import deadhorse.pwm.Pwm
import deadhorse.dma.Dma
import deadhorse.pinmux.Pinmux
import deadhorse.lite_core.LiteHart
import deadhorse.watchdog.Watchdog
import deadhorse.boot_control.BootControl
import deadhorse.qspi.Qspi

/** The production peripheral/bridge path, also tested at its CPU boundary.
  * All test-controller inputs are synchronous to their declared owning domain.
  */
class SocI1Peripherals(description: SocDescription, config: SocI1Config) extends RawModule {
  protected def testBusInjection: Boolean=false
  protected def loaderHalted(halted: Bool,starting: Bool): Bool=halted && !starting
  protected def wholeWatchdogReset(performance: Bool,lite: Bool): Bool=lite
  protected def qspiServiceReset(main: Bool,aon: Bool): Bool=main
  val mainClock=IO(Input(Clock()));val coldReset_n=IO(Input(Bool()));val warmReset_n=IO(Input(Bool()))
  val mainServiceReset_n=IO(Input(Bool()));val main=IO(new LocalBus)
  val uartRx=IO(Input(Bool()));val uartTx=IO(Output(Bool()));val uartTxEnable=IO(Output(Bool()))
  val pins=IO(new SocI1Pins);val fastIrq=IO(Output(UInt(15.W)))
  val mainHold=IO(Output(Bool()))
  val supervision=config.watchdog.map(_=>IO(Output(new Bundle {
    val performanceReset=Bool();val wholeReset=Bool();val warning=Bool()
  })))
  val performanceReady=config.watchdog.map(_=>IO(Input(Bool())))
  val performanceReleased=config.bootControl.map(_=>IO(Output(Bool())))
  val nativeXip=Some(IO(new LocalBus))
  val validatedStart=WireDefault(false.B)
  val performanceHold=WireDefault(false.B);val wholeHold=WireDefault(false.B)
  val watchdogWarning=WireDefault(false.B);val watchdogDemand=WireDefault(false.B)
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
  val warmRaw=warmReset_n && !wholeHold
  val mainRaw=coldReset_n && warmRaw && mainServiceReset_n
  val aonRaw=coldReset_n && warmRaw && pins.aonServiceReset_n
  val usbRaw=coldReset_n && warmRaw && pins.usbServiceReset_n
  val mainUp=release(mainClock,mainRaw);val aonUp=release(pins.aonClock,aonRaw)
  // Demand collection belongs to the external controller's whole-chip reset
  // cohort; AON service reset must not erase surviving main orphan demand.
  val controllerUp=release(pins.aonClock,coldReset_n && warmRaw)
  val coldUp=release(pins.aonClock,coldReset_n)
  val pwmUp=release(mainClock,mainRaw && !performanceHold)
  val usbAppUp=release(mainClock,mainRaw && usbRaw)
  def syncMain(value: Bool): Bool = {
    val s=Module(new CdcSync(1));s.clk:=pins.aonClock;s.reset_n:=controllerUp;s.in:=value.asUInt;s.out.asBool
  }
  val mainNames=description.fabric("main");val aonNames=description.fabric("aon")
  val mainRemote=Seq("retained_sram","power_reset_timer","unassigned_aon")
  val aonRemote=Seq("serial","actuator","gateway")
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
  val liteHart=Some(Module(new LiteHart(description.origin("lite"))))
  liteHart.foreach { hart =>
      hart.clk:=pins.aonClock;hart.reset_n:=aonUp;hart.irq:=pins.aonIrq
      if(testBusInjection) {
        ingress(af.master(0),pins.lite,aonNames,Some(description.origin("lite")))
        hart.bus.gnt:=false.B;hart.bus.rvalid:=false.B;hart.bus.rdata:=0.U;hart.bus.err:=false.B
      } else ingress(af.master(0),hart.bus,aonNames,Some(description.origin("lite")))
      // The test-master port is inert in the real-hart profile, including its
      // claimed halted state. Only the core controls retained-memory ownership.
      if(!testBusInjection) {
        pins.lite.gnt:=false.B;pins.lite.rvalid:=false.B;pins.lite.rdata:=0.U;pins.lite.err:=false.B
      }
  }
  val liteHalted=if(testBusInjection) pins.liteHalted else liteHart.get.halted
  val toAon=Module(new BusBridge);val toMain=Module(new BusBridge)
  toAon.sourceClock:=mainClock;toAon.targetClock:=pins.aonClock
  toAon.sourceReset_n:=mainRaw;toAon.targetReset_n:=aonRaw
  toMain.sourceClock:=pins.aonClock;toMain.targetClock:=mainClock
  toMain.sourceReset_n:=aonRaw;toMain.targetReset_n:=mainRaw
  val permits=Module(new DirectionPermit)
  permits.aonClock:=pins.aonClock;permits.mainClock:=mainClock
  permits.aonReset_n:=aonRaw;permits.mainReset_n:=mainRaw
  permits.requestAon:=toMain.permitRequest;permits.requestMain:=toAon.permitRequest
  toMain.permit:=permits.permitAon;toAon.permit:=permits.permitMain
  ingress(mf.master(1),toMain.target,Seq("serial","actuator","gateway","future_bridge"),None)
  ingress(af.master(1),toAon.target,Seq("retained_sram","power_reset_timer","unassigned_aon","future_bridge"),None)
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
  remote(af,aonNames,aonRemote,toMain,pins.aonClock,aonUp)
  def drain(f: BusFabric,children: Seq[BusFabric],bridge: BusBridge,clock: Clock,reset: Bool): Unit = {
    val credit=Module(new SocDrainCredit);credit.clk:=clock;credit.reset_n:=reset
    credit.accepted:=bridge.target.req && bridge.target.gnt;credit.response:=bridge.target.rvalid
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
    val regions=Seq("gpio","timers").map(description.ioRegion)++config.pinmux.map(_=>description.pinmuxRegion)
    val f=Module(new BusFabric(1,regions.map(r=>BusRegion(r.base,r.size,128))))
    f.clk:=mainClock;f.reset_n:=mainUp
    f.allow.foreach(_:=true.B);f.admit.foreach(_:=true.B);f.quiescent.foreach(_:=false.B)
    f.master(0)<>serial.target(serialNames.indexOf("gpio_pinmux"))
    serial.quiescent(serialNames.indexOf("gpio_pinmux")):=nestedQuiet(f)
    f
  }
  drain(mf,Seq(serial,gateway)++ioFabric.toSeq,toMain,mainClock,mainUp)
  val powerFabric=config.watchdog.map {json=>
    val regions=Seq(description.ioRegion("aon_timer"))++(0 until 2).map(description.watchdogRegion)++
      config.bootControl.toSeq.map(_=>description.bootControlRegion)
    val f=Module(new BusFabric(1,regions.map(r=>BusRegion(r.base,r.size,128))))
    f.clk:=pins.aonClock;f.reset_n:=aonUp
    f.allow.foreach(_:=true.B);f.admit.foreach(_:=true.B);f.quiescent.foreach(_:=false.B)
    f.master(0)<>af.target(aonNames.indexOf("power_reset_timer"))
    af.quiescent(aonNames.indexOf("power_reset_timer")):=nestedQuiet(f,pins.aonClock,aonUp)
    val channels=Seq("performance","lite").zipWithIndex.map {case(owner,index)=>
      val w=Module(new Watchdog(json,description.watchdogRegion(index).base,description.origin(owner)))
      w.clk:=pins.aonClock;w.por_n:=coldUp;w.reset_n:=aonUp;w.bus<>f.target(index+1);w
    }
    performanceHold:=channels(0).resetHold;wholeHold:=wholeWatchdogReset(channels(0).resetHold,channels(1).resetHold)
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
      val boot=Module(new BootControl(path,description.bootControlRegion.base,description.origin("lite")))
      boot.clk:=pins.aonClock;boot.epochReset_n:=controllerUp;boot.reset_n:=aonUp
      boot.startAccepted:=validatedStart;boot.bus<>f.target(3)
      performanceReleased.get:=boot.released
    }
    f
  }
  drain(af,powerFabric.toSeq,toAon,pins.aonClock,aonUp)
  gateway.master(0)<>mf.target(mainNames.indexOf("gateway"))
  stub(gateway.target(gatewayNames.indexOf("gateway_reserved")),mainClock,mainUp)
  val qspiHold=WireDefault(false.B)
  config.qspi.foreach {json=>
    val flash=Module(new Qspi(json,description.qspiRegion.base,withXip=true))
    flash.clk:=mainClock;flash.reset_n:=qspiServiceReset(mainUp,aonUp);flash.bus<>serial.target(serialNames.indexOf("qspi_control"))
    flash.dqIn:=pins.inactive.qspiDqIn
    pins.inactive.qspiDqOut:=flash.dqOut;pins.inactive.qspiDqEnable:=flash.dqEnable
    pins.inactive.qspiSclk:=flash.sclk;pins.inactive.qspiSclkEnable:=flash.sclkEnable
    pins.inactive.qspiCs_n:=flash.cs_n;pins.inactive.qspiCsEnable:=flash.csEnable
    qspiHold:=flash.clockHold
    flash.xip.foreach(_<>nativeXip.get)
  }
  val pwmIrq=WireDefault(false.B);val pwmHold=WireDefault(false.B)
  val pwmRequests=WireDefault(0.U(9.W));val pwmAck=WireDefault(0.U(9.W))
  val muxValues=WireDefault(VecInit(Seq.fill(3)(0.U(3.W))))
  val muxEnables=WireDefault(VecInit(Seq.fill(3)(0.U(3.W))))
  val pinmuxHold=WireDefault(false.B)
  config.pwm.foreach { json =>
      val p=Module(new Pwm(json,base=description.pwmRegion.base,watchdog=true))
      p.clk:=mainClock;p.reset_n:=mainUp;p.owner:=description.origin("performance").U
      p.watchdogReset_n.foreach(_:=pwmUp)
      p.performanceReady.foreach(_:=performanceReady.get)
      p.bus<>mf.target(mainNames.indexOf("actuator"));p.dmaAck:=pwmAck;pwmRequests:=p.dmaRequest
      pins.inactive.actuatorOut:=p.pinsOut;pins.inactive.actuatorEnable:=p.pinsEnable
      muxValues(2):=p.pinsOut(2,0);muxEnables(2):=p.pinsEnable(2,0)
      pwmIrq:=p.irq;pwmHold:=p.clockHold
  }
  stub(mf.target(mainNames.indexOf("future_bridge")),mainClock,mainUp)
  for(n<-Seq("future_bridge","unassigned_aon"))
    stub(af.target(aonNames.indexOf(n)),pins.aonClock,aonUp)
  val ioMainHold=WireDefault(false.B);val ioAonHold=WireDefault(false.B)
  val ioWake=WireDefault(false.B);val ioAonIrq=WireDefault(false.B)
  val gpioIrq=WireDefault(false.B);val timerIrq=WireDefault(false.B)
  val timeNow=WireDefault(pins.spiTimeNow)
  config.io.foreach { c =>
    def toMainLevel(value: Bool): Bool = {
      val s=Module(new CdcSync(1));s.clk:=mainClock;s.reset_n:=mainUp;s.in:=value.asUInt;s.out.asBool
    }
    val gpio=Module(new Gpio(c.gpio,base=description.ioRegion("gpio").base))
    gpio.clk:=mainClock;gpio.aonClock:=pins.aonClock;gpio.reset_n:=mainUp;gpio.aonReset_n:=aonUp
    gpio.owner:=description.origin("performance").U;gpio.bus<>ioFabric.get.target(0)
    gpio.pinsIn:=pins.inactive.gpioIn;pins.inactive.gpioOut:=gpio.pinsOut;pins.inactive.gpioEnable:=gpio.pinsEnable
    muxValues(0):=gpio.pinsOut;muxEnables(0):=gpio.pinsEnable
    val timers=Module(new MainTimers(c.timers,c.mainMHz,base=description.ioRegion("timers").base))
    timers.clk:=mainClock;timers.reset_n:=mainUp;timers.owner:=description.origin("performance").U
    timers.bus<>ioFabric.get.target(1);timers.captureIn:=pins.inactive.timerIn;timers.imuDrdy:=pins.inactive.imuDrdy
    pins.inactive.timerOut:=timers.compareOut;pins.inactive.timerEnable:=timers.pinsEnable;timeNow:=timers.timeNow
    muxValues(1):=timers.compareOut(2,0);muxEnables(1):=timers.pinsEnable(2,0)
    val aonTimer=Module(new AonTimers(c.aonTimer,base=description.ioRegion("aon_timer").base))
    aonTimer.clk:=pins.aonClock;aonTimer.reset_n:=aonUp;aonTimer.owner:=description.origin("lite").U
    aonTimer.bus<>powerFabric.get.target(0)
    gpioIrq:=gpio.irq;timerIrq:=timers.irq || toMainLevel(aonTimer.irq)
    ioMainHold:=gpio.clockHold || timers.clockHold || ioFabric.get.waiting.asUInt.orR
    ioAonHold:=aonTimer.clockHold
    ioWake:=aonTimer.wake || gpio.wake
    ioAonIrq:=aonTimer.irq || gpio.wake
  }
  config.pinmux.foreach {json=>
    val p=Module(new Pinmux(json,base=description.pinmuxRegion.base,watchdog=true))
    p.clk:=mainClock;p.reset_n:=mainUp;p.owner:=description.origin("performance").U
    p.watchdogReset_n.foreach(_:=pwmUp)
    p.bus<>ioFabric.get.target(2);p.values:=muxValues;p.enables:=muxEnables
    pins.inactive.gpioOut:=p.pinsOut;pins.inactive.gpioEnable:=p.pinsEnable;pinmuxHold:=p.clockHold
  }
  val mailbox=Module(new Mailbox(config.mailbox))
  mailbox.mainClock:=mainClock;mailbox.aonClock:=pins.aonClock
  mailbox.mainReset_n:=mainRaw;mailbox.aonReset_n:=aonRaw
  mailbox.main<>mf.target(mainNames.indexOf("mailbox"));mailbox.aon<>af.target(aonNames.indexOf("mailbox"))
  pins.aonIrq:=withClockAndReset(pins.aonClock,(!aonUp).asAsyncReset) {
    RegNext(mailbox.irq(0) || ioAonIrq,false.B)
  }
  val uarts=(0 until 3).map { i =>
    val name=s"uart$i";val u=Module(new Uart(config.uart,base=description.region(name).base))
    u.clk:=mainClock;u.reset_n:=mainUp;u.owner:=description.origin("performance").U
    u.bus<>serial.target(serialNames.indexOf(name));u.rx:=(if(i==0) uartRx else pins.uartRx(i-1))
    u.sleepRequest:=false.B;u.sleepMode:=0.U
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
    dma.bus<>serial.target(serialNames.indexOf("dma"));dmaMemory.get<>dma.memory
    ingress(mf.master(2),dma.peripheral,Seq("uart0","uart1","uart2","spi_host","actuator"),Some(description.origin("performance")))
    dma.requests:=Cat(pwmRequests,spi.dmaRxRequest,spi.dmaTxRequest,
      VecInit(uarts.flatMap(u=>Seq(u.dmaTxRequest,u.dmaRxRequest))).asUInt)
    pwmAck:=dma.pwmAck;dmaIrq:=dma.irq;dmaHold:=dma.clockHold
  }
  val i2c=Module(new I2cHost(config.i2c,base=description.region("i2c_host").base))
  i2c.clk:=mainClock;i2c.reset_n:=mainUp;i2c.owner:=description.origin("performance").U
  i2c.bus<>serial.target(serialNames.indexOf("i2c_host"));i2c.sclIn:=pins.i2cSclIn;i2c.sdaIn:=pins.i2cSdaIn
  i2c.sleepRequest:=false.B;i2c.sleepEnable:=false.B
  pins.i2cSclLow:=i2c.sclLow;pins.i2cSdaLow:=i2c.sdaLow;pins.i2cEnable:=i2c.pinsEnable
  val loader=Module(new RecoveryLoader)
  loader.clk:=pins.aonClock;loader.por_n:=coldUp;loader.reset_n:=aonUp
  loader.sclIn:=pins.recoveryScl;loader.sdaIn:=pins.recoverySda
  loader.resetReason:=resetCauses;loader.crashCount:=crashCount
  pins.recoverySdaLow:=loader.sdaLow;pins.liteStart:=loader.start;pins.liteEntry:=loader.entry
  pins.loaderLocked:=loader.locked;pins.loaderBusy:=loader.busy;pins.loaderProgrammed:=loader.programmed
  val acceptedLiteStart=loader.start && loader.programmed && !loader.busy && liteHalted &&
    !loader.entry(1,0).orR && loader.entry<2048.U
  // START is registered by the loader and consumed by the hart on the next
  // edge. Do not report that one handoff edge as a later halt to the loader.
  validatedStart:=acceptedLiteStart
  loader.halted:=loaderHalted(liteHalted,acceptedLiteStart)
  liteHart.foreach {hart=>
    hart.start:=(if(testBusInjection) false.B else acceptedLiteStart)
    hart.entry:=description.region("retained_sram").base.U+loader.entry
  }
  val retained=Module(new SocRetainedMemory(description))
  retained.clk:=pins.aonClock;retained.reset_n:=aonUp
  retained.bus<>af.target(aonNames.indexOf("retained_sram"))
  retained.halted:=liteHalted;retained.locked:=loader.locked;retained.loaderBusy:=loader.busy
  retained.started:=withClockAndReset(pins.aonClock,(!aonUp).asAsyncReset) {
    val started=RegInit(false.B)
    when(acceptedLiteStart) {started:=true.B};started
  }
  retained.memValid:=loader.memValid;retained.memOffset:=loader.memOffset;retained.memWord:=loader.memWord
  loader.memReady:=retained.memReady;loader.memDone:=retained.memDone
  val usbIrq=WireDefault(false.B)
  val usbTarget=gateway.target(gatewayNames.indexOf("usb"))
  if(config.realUsb) {
    val slot=Module(new SocResetSlot)
    slot.clk:=mainClock;slot.reset_n:=mainUp;slot.endpointReset_n:=mainRaw && usbRaw;slot.endpointReady:=usbAppUp
    slot.bus<>usbTarget
    val usb=Module(new Usb(config.usb,base=description.region("usb").base))
    usb.appClock:=mainClock;usb.usbClock:=pins.usbClock;usb.aonClock:=pins.aonClock
    usb.appReset_n:=mainRaw;usb.usbReset_n:=usbRaw;usb.aonReset_n:=aonRaw
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
  val sources=(0 until 3).map(i=>s"uart$i"->uarts(i).irq) ++ Seq("spi_host"->spi.irq,"i2c_host"->i2c.irq,"mailbox"->mailbox.irq(1),"usb"->usbIrq,"actuator"->pwmIrq,"dma"->dmaIrq) ++
    Seq("gpio_pinmux"->gpioIrq,"power_reset_timer"->timerIrq)
  irq:=sources.map {case(n,v)=>v.asUInt<<interruptIndex(n)}.reduce(_|_)
  fastIrq:=irq
  val held=withClockAndReset(mainClock,(!mainUp).asAsyncReset) {
    RegNext(uarts.map(_.clockHold).reduce(_||_) || spi.clockHold || i2c.clockHold || ioMainHold || pwmHold || dmaHold || pinmuxHold || qspiHold ||
      mf.waiting.asUInt.orR || serial.waiting.asUInt.orR || gateway.waiting.asUInt.orR,false.B)
  }
  mainHold:=held
  val fromMain=syncMain(held || toMain.targetClockHold || toAon.clockRequest || mailbox.wakePeer(1))
  val loaderWake=withClockAndReset(pins.aonClock,(!aonUp).asAsyncReset) {
    val wake=RegInit(false.B);when(loader.wake) {wake:=true.B}
    wake
  }
  pins.loaderWake:=loaderWake
  withClockAndReset(pins.aonClock,(!coldUp).asAsyncReset) {
    pins.mainDemand:=RegNext(fromMain || toMain.clockRequest || mailbox.wakePeer(0) || pins.usbWake || ioWake ||
      watchdogWarning || performanceHold || wholeHold,false.B)
    pins.aonDemand:=RegNext(fromMain || toAon.targetClockHold || af.waiting.asUInt.orR ||
      loader.clockHold || retained.busy || loaderWake || pins.usbWake || ioAonHold || ioWake ||
      liteHart.get.clockHold || watchdogDemand,false.B)
  }
}
