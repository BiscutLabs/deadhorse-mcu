package deadhorse.top

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Read-only observations; the production block and clock connections stay intact. */
class SocOscSleepProbe(boot: String="boot") extends SocAnalogModelTest("build/t20/map/soc.json",SocProduction.config().uart,
    Paths.get(s"build/plan04/sleep-firmware/$boot.hex").toAbsolutePath.toString) {
  val observe=IO(Output(new Bundle {
    val liteHeld=Bool();val hold=Bool();val gate=Bool();val qualify=Bool()
    val pc=UInt(32.W);val retire=Bool();val ndmReset=Bool();val serviceUp=Bool()
    val fetch=UInt(4.W);val instruction=UInt(32.W);val instructionError=Bool()
    val firstPc=Vec(16,UInt(32.W));val firstInsn=Vec(16,UInt(32.W));val retired=UInt(5.W)
  }))
  observe.liteHeld:=BoringUtils.bore(digital.subsystem.get.liteBootHeld)
  observe.hold:=digital.clockHold;observe.gate:=digital.i1.get.clockControl.gateRequest
  observe.qualify:=digital.i1.get.clockControl.qualify
  observe.ndmReset:=BoringUtils.bore(digital.debugReset)
  observe.serviceUp:=BoringUtils.bore(digital.serviceUp)
  observe.pc:=digital.rvfi("rvfi_pc_rdata").asUInt;observe.retire:=digital.rvfi("rvfi_valid").asUInt.asBool
  observe.fetch:=BoringUtils.bore(digital.core.ports("fetch_enable_i")).asUInt
  observe.instruction:=BoringUtils.bore(digital.core.ports("instr_addr_o")).asUInt
  observe.instructionError:=BoringUtils.bore(digital.core.ports("instr_err_i")).asUInt.asBool
  withClockAndReset(clocks.mainClock,(!clocks.coldReset_n).asAsyncReset) {
    val retired=RegInit(0.U(5.W));val pcs=RegInit(VecInit(Seq.fill(16)(0.U(32.W))))
    val insns=RegInit(VecInit(Seq.fill(16)(0.U(32.W))))
    when(observe.retire && retired<16.U) {
      pcs(retired(3,0)):=observe.pc;insns(retired(3,0)):=digital.rvfi("rvfi_insn").asUInt
      retired:=retired+1.U
    }
    observe.retired:=retired;observe.firstPc:=pcs;observe.firstInsn:=insns
  }
}

/** Real production clock/reset wrapper and unchanged complete block assembly.
  * Only analog macros are represented by their specified digital models. */
class SocClockResetSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/production-clock-simulation").toAbsolutePath
  }
  // Preserve loadMemoryFromFileInline ROM images, as in SocBootReleaseSpec;
  // register randomization remains enabled.
  private val settings=Settings.defaultRaw[SocAnalogModelTest].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
    "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gate=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  def design=new SocAnalogModelTest("build/t20/map/soc.json",SocProduction.config().uart,
    Paths.get("build/t20/i0-firmware/boot.hex").toAbsolutePath.toString)
  def pins(d: SocAnalogModelTest): Unit={
    d.pins.aonExtraIn.poke(0.U);d.pins.uartRx.foreach(_.poke(true.B));d.pins.spiMiso.poke(false.B)
    d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)

    d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
    val p=d.pins.inactive
    p.qspiDqIn.poke(0.U);p.jtagTck.poke(false.B);p.jtagTms.poke(true.B);p.jtagTdi.poke(false.B)
    p.imuDrdy.poke(false.B);p.gpioIn.poke(0.U);p.timerIn.poke(0.U)
  }
  test("manufacturing entry uses stopped functional clocks and exits through reset") {
    simulateRaw(design,settings=settings,firtoolOpts=gate) {d=>
      pins(d);d.porBypass.poke(true.B);d.aonClockSelect.poke(true.B)
      d.externalReset_n.poke(false.B);d.pins.uartRx(1).poke(false.B)
      d.model.get.supplyMv.poke(3300.U);d.model.get.porReference.step(3)
      val p=d.pins.inactive
      def tap(bit: Boolean): Unit={
        p.jtagTck.poke(false.B);p.jtagTdi.poke(bit.B);p.jtagTdoEnable.peek()
        p.jtagTck.poke(true.B);p.jtagTdoEnable.peek()
        p.jtagTck.poke(false.B);p.jtagTdoEnable.peek()
      }
      for(_<-0 until 3) tap(false)
      d.externalReset_n.poke(true.B);for(_<-0 until 2) tap(false)
      val bits="11010011011110100110110010010101"
      for((bit,index)<-bits.zipWithIndex) {
        tap(bit=='1');p.jtagTdoEnable.expect((index==31).B,"PRODUCTION_TEST_ENTRY")
      }
      p.jtagTdo.expect(true.B)
      for(shift<-Seq(false,true,false)) {
        d.pins.uartRx(2).poke(shift.B);d.pins.uartRx(1).poke(shift.B)
        p.jtagTdo.expect(true.B);p.jtagTdoEnable.expect(true.B)
        d.oscEn.expect(true.B);d.status.aonReleased.expect(false.B);d.status.servicesReleased.expect(false.B)
        d.pins.usbTxEnable.expect(false.B);d.pins.usbPullup.expect(false.B)
        d.pins.spiEnable.expect(false.B);d.pins.i2cEnable.expect(false.B)
        p.qspiCsEnable.expect(0.U);p.qspiDqEnable.expect(0.U)
        p.gpioEnable.expect(0.U);p.timerEnable.expect(0.U)
        p.actuatorEnable.expect(15.U);p.actuatorOut.expect(0.U)
        d.pins.uartTxEnable.foreach(_.expect(true.B));d.pins.uartTx.foreach(_.expect(false.B))
      }
      d.pins.uartRx(1).poke(false.B);d.externalReset_n.poke(false.B)
      p.jtagTdoEnable.expect(false.B);p.actuatorEnable.expect(0.U)
      d.pins.uartTxEnable.foreach(_.expect(false.B))
    }
  }
  for(external<-Seq(false,true);bypass<-Seq(false,true)) test(s"production POR boot AON external=$external bypass=$bypass") {
    simulateRaw(design,settings=settings,firtoolOpts=gate) {d=>
      pins(d);d.porBypass.poke(bypass.B);d.aonClockSelect.poke(external.B)
      d.externalReset_n.poke((!bypass).B)
      val m=d.model.get;m.supplyMv.poke(0.U);m.porReference.step(3)
      def aon(n: Int): Unit=if(external) d.aonClockIn.step(n) else m.lfClock.step(n)
      def tick(n: Int): Unit=for(_<-0 until n) {
        d.oscIn.step(1500);m.porReference.step(31);aon(1)
      }
      tick(4);d.oscEn.expect(true.B);d.status.aonReleased.expect(false.B)
      d.pins.inactive.jtagTdoEnable.expect(false.B,"POR_MUST_INITIALIZE_TEST_MODE")
      // One normal case uses a slow ramp; the others jump to valid supply.
      if(!external && !bypass) for(mv<-100 to 3190 by 10) {
        m.supplyMv.poke(mv.U);m.porReference.step(1);d.status.aonReleased.expect(false.B)
      }
      m.supplyMv.poke(3300.U);m.porReference.step(1002)
      d.externalReset_n.poke(true.B);tick(16)
      d.status.aonReleased.expect(true.B);d.status.servicesReleased.expect(false.B);d.oscEn.expect(true.B)
      tick(550);d.status.servicesReleased.expect(true.B);d.status.sourceStable.expect(true.B)
      d.status.fault.expect(false.B);d.oscEn.expect(true.B)
      d.status.resetCauses.expect((if(bypass) 4 else 1).U)
      m.supplyMv.poke(3150.U);m.porReference.step(5)
      d.status.servicesReleased.expect(true.B)
      m.supplyMv.poke(3050.U);m.porReference.step(2)
      d.status.servicesReleased.expect(bypass.B)
      if(!bypass) {
        d.status.aonReleased.expect(false.B)
        m.supplyMv.poke(3300.U);m.porReference.step(1002);tick(16)
        d.status.resetCauses.expect(2.U)
      }
      // A pin pulse between AON edges must assert reset and survive as a cause.
      d.externalReset_n.poke(false.B);d.status.aonReleased.expect(false.B)
      d.externalReset_n.poke(true.B);tick(16)
      assert((d.status.resetCauses.peek().litValue & 4)!=0,"PIN_RESET_CAUSE_LOST")
    }
  }
  test("production never-starting oscillator faults with main held and OSC_EN high") {
    simulateRaw(design,settings=settings,firtoolOpts=gate) {d=>
      pins(d);d.porBypass.poke(false.B);d.aonClockSelect.poke(false.B);d.externalReset_n.poke(true.B)
      val m=d.model.get;m.supplyMv.poke(0.U);m.porReference.step(3);m.lfClock.step(4)
      m.supplyMv.poke(3300.U);m.porReference.step(1002)
      m.lfClock.step(4700)
      d.status.aonReleased.expect(true.B);d.status.servicesReleased.expect(false.B)
      d.status.fault.expect(true.B);d.oscEn.expect(true.B)
      // A late source cannot bypass the latched failed-start state.
      for(_<-0 until 20) {d.oscIn.step(1500);m.lfClock.step()}
      d.status.servicesReleased.expect(false.B);d.status.mainLevel.expect(false.B);d.oscEn.expect(true.B)
    }
  }
  test("real JTAG ndmreset preserves debug and requalifies its clock before warm release") {
    val probeSettings=Settings.defaultRaw[SocOscSleepProbe].copy(
      randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
    simulateRaw(new SocOscSleepProbe,settings=probeSettings,firtoolOpts=gate) {d=>
      pins(d);d.porBypass.poke(false.B);d.aonClockSelect.poke(false.B);d.externalReset_n.poke(true.B)
      val m=d.model.get;m.supplyMv.poke(0.U);m.porReference.step(3);m.lfClock.step(4)
      m.supplyMv.poke(3300.U);m.porReference.step(1002)
      var aonTicks=0;var warmAt= -1
      def tick(n: Int=1): Unit=for(_<-0 until n) {
        d.oscIn.step(1500);m.porReference.step(31);m.lfClock.step();aonTicks+=1
        if(d.observe.ndmReset.peek().litToBoolean && warmAt<0) warmAt=aonTicks
      }
      tick(580);d.status.sourceStable.expect(true.B);d.observe.serviceUp.expect(true.B)
      def tap(tms: Boolean,tdi: Boolean=false): Boolean={
        val p=d.pins.inactive
        p.jtagTck.poke(false.B);p.jtagTms.poke(tms.B);p.jtagTdi.poke(tdi.B);tick()
        val bit=p.jtagTdo.peek().litToBoolean
        p.jtagTck.poke(true.B);tick();p.jtagTck.poke(false.B);bit
      }
      for(_<-0 until 16) tap(true);tap(false)
      tap(true);tap(true);tap(false);tap(false)
      for(i<-0 until 5) tap(i==4,((0x11>>i)&1)!=0)
      tap(true);tap(false);for(_<-0 until 16) tap(false)
      def scan(value: BigInt): BigInt={
        tap(true);tap(false);tap(false)
        var result=BigInt(0)
        for(i<-0 until 41) if(tap(i==40,value.testBit(i))) result=result.setBit(i)
        tap(true);tap(false);for(_<-0 until 16) tap(false)
        result
      }
      def writeControl(value: Int): Unit={
        scan((BigInt(0x10)<<34)|(BigInt(value)<<2)|2)
        val response=scan(0)
        assert((response&3)==0,"T33_DMI_RESET_RESPONSE")
      }
      writeControl(1) // dmactive, without halt or a firmware test path.
      for(duration<-Seq(1,4,16)) {
        warmAt= -1
        writeControl(3);d.observe.ndmReset.expect(true.B)
        d.observe.serviceUp.expect(false.B)
        tick(duration);d.oscEn.expect(true.B);d.observe.gate.expect(false.B)
        d.status.sourceStable.expect(false.B);d.status.fault.expect(false.B)
        // T41 replaces the preserved policy epoch with a fresh warm epoch.
        // Use the existing POR startup bound; ndmreset remains asserted while
        // cold-owned execution restores the debug clock independently of warm.
        assert(warmAt>=0 && aonTicks-warmAt<550,"WARM_START_OBSERVATION_BOUND")
        while(aonTicks-warmAt<550) {
          d.oscEn.expect(true.B);d.status.fault.expect(false.B)
          d.observe.ndmReset.expect(true.B);d.observe.serviceUp.expect(false.B);tick()
        }
        d.observe.gate.expect(true.B);d.status.sourceStable.expect(true.B)
        d.status.fault.expect(false.B)
        // The write that releases reset must work while all ordinary clients
        // are held reset. A dead DM clock cannot complete this transaction.
        writeControl(1);d.observe.ndmReset.expect(false.B);tick(24)
        d.observe.serviceUp.expect(true.B);d.observe.gate.expect(true.B)
        d.status.sourceStable.expect(true.B);d.status.fault.expect(false.B)
      }
    }
  }
  for((imageName,wakes,label)<-Seq(
      ("lite",Seq(2,3,4),"three oscillator-off UART wakes"),
      ("lite-reset",Seq(8),"oscillator-off lite-watchdog service reset"),
      ("lite-extra",Seq(0,6),"oscillator-off timer and lite-mailbox wakes"),
      ("lite-gpio",Seq(1),"oscillator-off GPIO wake"),
      ("lite-jtag",Seq(7),"oscillator-off JTAG wake"),
      ("lite-usb",Seq(5),"oscillator-on USB resume")))
  test(if(imageName=="lite-reset") "real lite watchdog wakes the stopped oscillator and resets services" else
      s"real performance and WFI firmware retain main state through $label") {
    val probeSettings=Settings.defaultRaw[SocOscSleepProbe].copy(
      randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
    val boot="boot-"+imageName
    simulateRaw(new SocOscSleepProbe(boot),settings=probeSettings,firtoolOpts=gate) {d=>
      pins(d);d.porBypass.poke(false.B);d.aonClockSelect.poke(false.B);d.externalReset_n.poke(true.B)
      if(imageName=="lite-usb") {d.pins.usbVbus.poke(true.B);d.pins.usbDpRx.poke(true.B)}
      val m=d.model.get;m.supplyMv.poke(0.U);m.porReference.step(3);m.lfClock.step(4)
      m.supplyMv.poke(3300.U);m.porReference.step(1002)
      def high(v: Bool)=v.peek().litToBoolean
      var sourceAge=0
      def tick(n: Int=1): Unit=for(_<-0 until n) {
        // Board model stops the source completely and takes two nominal AON
        // periods to restart. Firmware selects a longer four-tick delay.
        if(high(d.oscEn)) {sourceAge+=1;if(sourceAge>2) d.oscIn.step(1500)} else sourceAge=0
        m.porReference.step(31);m.lfClock.step()
      }
      tick(580);d.status.servicesReleased.expect(true.B);d.oscEn.expect(true.B)
      def tap(tms: Boolean,tdi: Boolean=false): Unit={
        d.pins.inactive.jtagTck.poke(false.B);d.pins.inactive.jtagTms.poke(tms.B)
        d.pins.inactive.jtagTdi.poke(tdi.B);tick()
        d.pins.inactive.jtagTck.poke(true.B);tick()
        d.pins.inactive.jtagTck.poke(false.B)
      }
      if(imageName=="lite-jtag") {for(_<-0 until 16) tap(true);tap(false);for(_<-0 until 16) tap(false)}
      // Performance ROM copies/releases the AON-only helper; no loader transport.
      for(wake<-wakes) {
        var elapsed=0
        if(wake==5) {
          // D81: attached USB converts this deep request to light sleep. Let
          // firmware reach OFF and the real resume detector qualify idle J.
          tick(10000)
          d.oscEn.expect(true.B);d.pins.usbPullup.expect(true.B)
          for(_<-0 until 12) {d.oscIn.step();d.status.mainLevel.expect(false.B)}
        } else while(high(d.oscEn)) {
          tick();elapsed+=1
          assert(elapsed<20000,s"OSC_FIRMWARE_SLEEP wake=$wake ready=${high(d.status.coreReady)} sleeping=${high(d.status.coreSleeping)} gpio=${d.pins.inactive.gpioOut.peek().litValue} hold=${high(d.observe.hold)} gate=${high(d.observe.gate)} pc=${d.observe.pc.peek().litValue.toString(16)}")
        }
        d.status.coreReady.expect(true.B);d.status.coreSleeping.expect(true.B)
        d.status.servicesReleased.expect(true.B);d.pins.inactive.gpioOut.expect(5.U)
        tick(40);d.oscEn.expect((wake==5).B);d.status.mainLevel.expect(false.B)
        d.pins.inactive.gpioOut.expect(5.U)
        if(wake==5) {
          // Host K state after the full production idle qualifier. No shortened
          // USB suspend counter or injected AON wake signal is used.
          d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(true.B)
          tick(640);d.oscEn.expect(true.B) // 20 ms at nominal 32 kHz AON.
          d.pins.usbDpRx.poke(true.B);d.pins.usbDnRx.poke(false.B);tick(64)
        } else if(wake>=2 && wake<=4) {
          val index=wake-2
          d.pins.uartRx(index).poke(false.B)
          elapsed=0
          while(!high(d.oscEn)) {tick();elapsed+=1;assert(elapsed<16,"OSC_UART_WAKE_LOST")}
          tick(10);d.pins.uartRx(index).poke(true.B);tick(64)
        } else if(wake==1 || wake==7) {
          if(wake==1) d.pins.inactive.gpioIn.poke(2.U)
          else {
            // IEEE TAP states: idle -> select DR -> select IR -> capture IR -> shift IR.
            tap(true);tap(true);tap(false);tap(false)
            for(i<-0 until 5) tap(i==4,((0x11>>i)&1)!=0) // DMI instruction.
            tap(true);tap(false)
            tap(true);tap(false);tap(false) // capture/shift DR.
            val readStatus=(BigInt(0x11)<<34)|1 // DMI read dmstatus, no halt request.
            for(i<-0 until 41) tap(i==40,readStatus.testBit(i))
            tap(true);tap(false);for(_<-0 until 8) tap(false)
          }
          elapsed=0
          while(!high(d.oscEn)) {tick();elapsed+=1;assert(elapsed<16,s"OSC_PIN_WAKE_LOST source=$wake")}
          tick(74)
        } else {
          // Timer expiry, a lite mailbox write or the real lite watchdog must
          // wake the production assembly without testbench wake injection.
          elapsed=0
          while(!high(d.oscEn)) {tick();elapsed+=1;assert(elapsed<20000,s"OSC_AON_WAKE_LOST source=$wake")}
          // Internal reset restores conservative startup; the sole boot master
          // reports the watchdog cause and deliberately leaves the hung helper held.
          // Existing wake cases retain their original observation interval.
          tick(if(wake==8) 2000 else 74)
        }
        d.status.servicesReleased.expect(true.B);d.status.sourceStable.expect(true.B)
        d.status.fault.expect(false.B)
        if(wake==8) {
          d.observe.serviceUp.expect(true.B);d.observe.gate.expect(true.B)
          d.observe.liteHeld.expect(true.B)
          d.status.coreReady.expect(true.B);d.pins.inactive.gpioOut.expect(1.U)
        } else d.status.coreReady.expect(true.B)
      }
      var elapsed=0
      while(!wakes.contains(8) && d.pins.inactive.gpioOut.peek().litValue!=1) {
        tick();elapsed+=1;assert(elapsed<10000,"OSC_FIRMWARE_WAKE_CAUSE_OR_RETENTION")
      }
      d.oscEn.expect(true.B);d.status.fault.expect(false.B)
    }
  }
}
