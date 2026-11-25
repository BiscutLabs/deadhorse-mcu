package deadhorse.top
import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocDormantHoldSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/dormant-hold/simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocDormantProbe].copy(randomization=Randomization.random.copy(memories=false))
    .withLibraryPaths(Seq(Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  for(kind<-0 to 3) test(s"production deep sleep inhibition kind=$kind (idle, timer, DMA, USB)") {
    simulateRaw(new SocDormantProbe(s"build/plan05/hold-firmware/$kind.hex",realUsb=true),settings=settings,firtoolOpts=gates) {d=>
      def high(v: Bool)=v.peek().litToBoolean
      val p=d.pins;val a=d.model.get
      p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B)
      p.aonExtraIn.poke(0.U)
      p.usbVbus.poke((kind==3).B);p.usbDpRx.poke((kind==3).B);p.usbDnRx.poke(false.B)
      SocInactiveTestInputs.drive(p.inactive,0)
      d.aonClockSelect.poke(false.B);d.porBypass.poke(false.B);d.externalReset_n.poke(false.B)
      a.supplyMv.poke(0.U);a.porReference.step(3);a.lfClock.step(3);d.oscIn.step(6)
      a.supplyMv.poke(3300.U);a.porReference.step(1002);d.externalReset_n.poke(true.B)
      def tick(): Unit={if(high(d.oscEn)) d.oscIn.step(1500);a.porReference.step(32);a.lfClock.step()}
      var elapsed=0
      while((!high(d.status.coreSleeping) || d.stage.peek().litValue!=BigInt("51051000",16)+kind) && elapsed<3000) {tick();elapsed+=1}
      assert(high(d.status.coreSleeping) && d.stage.peek().litValue==BigInt("51051000",16)+kind,"HOLD_FIRMWARE_WFI")
      for(_<-0 until 64) tick()
      if(kind==0) assert(!high(d.oscEn),"IDLE_DEEP_SLEEP")
      else {
        assert(d.holds.peek().litValue.testBit(kind-1),"HOLD_PRODUCER_NOT_ACTIVE")
        for(_<-0 until 128) {tick();assert(high(d.oscEn),"ACTIVE_HOLD_STOPPED_OSCILLATOR")}
        if(kind<3) {
          val levels=(0 until 12).map {_=>d.oscIn.step();high(d.status.mainLevel)}
          assert(levels.contains(true) && levels.contains(false),"MAIN_HOLD_CLOCK_STOPPED")
        }
        else {assert(high(p.usbPullup),"USB_ENABLED");for(_<-0 until 12) {d.oscIn.step();d.status.mainLevel.expect(false.B)}}
      }
    }
  }
  test("a hung lite watcher keeps counting and triggers its whole-chip watchdog while OSC_IN is stopped") {
    simulateRaw(new SocDormantProbe("build/plan05/hung-firmware/boot.hex"),settings=settings,firtoolOpts=gates) {d=>
      def high(v: Bool)=v.peek().litToBoolean
      val p=d.pins;val a=d.model.get
      p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B)
      p.aonExtraIn.poke(0.U)
      p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
      SocInactiveTestInputs.drive(p.inactive,0)
      d.aonClockSelect.poke(false.B);d.porBypass.poke(false.B);d.externalReset_n.poke(false.B)
      a.supplyMv.poke(0.U);a.porReference.step(3);a.lfClock.step(3);d.oscIn.step(6)
      a.supplyMv.poke(3300.U);a.porReference.step(1002);d.externalReset_n.poke(true.B)
      def tick(): Unit={if(high(d.oscEn)) d.oscIn.step(1500);a.porReference.step(32);a.lfClock.step()}
      var elapsed=0;while(high(d.oscEn) && elapsed<3000) {tick();elapsed+=1}
      assert(!high(d.oscEn) && d.stage.peek().litValue==BigInt("51052000",16),"LITE_WATCHDOG_DORMANT")
      elapsed=0
      while(d.liteWatchdogLeft.peek().litValue==0 && elapsed<512) {
        tick();elapsed+=1;assert(!high(d.oscEn),"LITE_WATCHDOG_SETUP_WOKE_MAIN")
      }
      val left=d.liteWatchdogLeft.peek().litValue;assert(left>64 && left<=512,"LITE_WATCHDOG_NOT_STARTED")
      for(_<-0 until 64) {tick();assert(!high(d.oscEn) && !high(d.liteWatchdogReset))}
      assert(d.liteWatchdogLeft.peek().litValue==left-64,"LITE_WATCHDOG_FROZEN")
      elapsed=0;while(!high(d.liteWatchdogReset) && elapsed<512) {tick();elapsed+=1}
      assert(high(d.liteWatchdogReset) && high(d.liteWatchdogCause),"LITE_WATCHDOG_HANG_UNCAUGHT")
      assert(!high(d.status.coreReady) && high(d.liteHeld),"LITE_WATCHDOG_WHOLE_RESET")
      elapsed=0
      while(!high(d.oscEn) && elapsed<8) {
        assert(!high(d.status.coreReady) && high(d.liteHeld),"LITE_WATCHDOG_EARLY_RELEASE")
        tick();elapsed+=1
      }
      assert(high(d.oscEn),"LITE_WATCHDOG_OSCILLATOR_RESTART")
      assert(!high(d.status.coreReady) && high(d.liteHeld),"LITE_WATCHDOG_RESTART_CONTAINMENT")
    }
  }

}
