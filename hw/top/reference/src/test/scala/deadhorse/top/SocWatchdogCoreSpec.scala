package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocWatchdogCoreBench extends SocExternalClockTest(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t26/firmware/boot.hex").toAbsolutePath.toString,i1Config=Some(SocProduction.config(realUsb=false)))
class SocWatchdogCoreSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t26/core-reset-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocWatchdogCoreBench].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(
      Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i",
    "--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  test("real watchdog warm reset clears DMA/GPIO/timers and firmware observes retained cause") {
    simulateRaw(new SocWatchdogCoreBench,firtoolOpts=gates,settings=settings) {d=>
      val p=d.i1.get
      d.uartRx.poke(true.B);d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B)
      d.mainCoreReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
      p.aonServiceReset_n.poke(false.B);p.usbServiceReset_n.poke(false.B)
      p.lite.req.poke(false.B);p.lite.bits.poke(0.U.asTypeOf(p.lite.bits))
      p.liteHalted.poke(true.B);p.resetReason.poke(0.U);p.crashCount.poke(0.U)
      p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U)
      p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B);
      p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
      SocInactiveTestInputs.drive(p.inactive,0)
      def tick(): Unit={d.mainClock.step();p.aonClock.step();p.usbClock.step()}
      for(_<-0 until 4) tick()
      d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B);d.mainCoreReset_n.poke(true.B)
      d.mainServiceReset_n.poke(true.B);p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)
      SocTestBoot.release(d,()=>tick())
      var wasReady=false;var sawEnabled=false;var sawReset=false;var recovered=false
      var cycles=0
      while(!recovered && cycles<12000) {
        tick();cycles+=1
        val ready=d.coreReady.peek().litToBoolean
        val enabled=p.inactive.actuatorEnable.peek().litValue==1
        if(enabled) sawEnabled=true
        if(wasReady && !ready && sawEnabled) {
          sawReset=true
          assert(p.inactive.actuatorEnable.peek().litValue==0,"WATCHDOG_CORE_PWM")
          assert(p.inactive.gpioEnable.peek().litValue==0,"WATCHDOG_CORE_GPIO_RESET")
        }
        recovered=sawReset && ready && p.inactive.gpioOut.peek().litValue==4 &&
          p.inactive.gpioEnable.peek().litValue==6
        wasReady=ready
      }
      assert(sawEnabled && sawReset && recovered,"WATCHDOG_CORE_RESTART_SIGNATURE")
      d.warmReset_n.poke(false.B)
      assert(p.inactive.actuatorEnable.peek().litValue==0 && p.inactive.actuatorOut.peek().litValue==0)
    }
  }
}
