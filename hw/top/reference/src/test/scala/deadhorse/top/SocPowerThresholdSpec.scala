package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Observe the actual digital-to-analog threshold boundary; no injected bus. */
class SocPowerThresholdProbe(badKey: Boolean=false) extends SocAnalogModelTest("build/t20/map/soc.json",SocProduction.config().uart,
    Paths.get(s"build/t33/threshold-firmware/${if(badKey) "boot-bad-key" else "boot"}.hex").toAbsolutePath.toString) {
  val macroThreshold=IO(Output(UInt(2.W)))
  val macroReset_n=IO(Output(Bool()))
  macroThreshold:=threshold;macroReset_n:=supplyReset
}

class SocPowerThresholdSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/threshold-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocPowerThresholdProbe].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gate=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")

  for((brownout,badKey)<-Seq((false,false),(true,false),(false,true)))
  test(s"real performance MMIO threshold change and software reset reason, brownout=$brownout badKey=$badKey") {
    simulateRaw(new SocPowerThresholdProbe(badKey),settings=settings,firtoolOpts=gate) {d=>
      d.pins.aonExtraIn.poke(0.U);d.pins.uartRx.foreach(_.poke(true.B));d.pins.spiMiso.poke(false.B)
      d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)

      d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
      val p=d.pins.inactive
      p.qspiDqIn.poke(0.U);p.jtagTck.poke(false.B);p.jtagTms.poke(true.B);p.jtagTdi.poke(false.B)
      p.imuDrdy.poke(false.B);p.gpioIn.poke(0.U);p.timerIn.poke(0.U)
      d.porBypass.poke(false.B);d.aonClockSelect.poke(false.B);d.externalReset_n.poke(true.B)
      val m=d.model.get;m.supplyMv.poke(0.U);m.porReference.step(3);m.lfClock.step(4)
      def high(v: Bool)=v.peek().litToBoolean
      def tick(n: Int=1): Unit=for(_<-0 until n) {
        d.oscIn.step(1500);m.porReference.step(31);m.lfClock.step()
      }
      // All voltages/delays are the existing assumed digital macro contract.
      m.supplyMv.poke(3300.U);m.porReference.step(1002);tick(580)
      d.status.servicesReleased.expect(true.B);d.macroThreshold.expect(0.U)
      def load(): Unit=p.gpioIn.poke(1.U) // Board stimulus releases the diagnostic wait.
      def expectReport(value: Int): Unit={
        var elapsed=0
        while(p.gpioOut.peek().litValue!=value && elapsed<10000) {tick();elapsed+=1}
        assert(p.gpioOut.peek().litValue==value,s"POWER_FIRMWARE_REPORT expected=$value actual=${p.gpioOut.peek().litValue}")
      }
      load();expectReport(1) // real PowerReset.reason read: POR
      expectReport(4)
      if(brownout) m.supplyMv.poke(3150.U) // above old falling, below new falling threshold
      if(!brownout) {
        var elapsed=0
        while((p.gpioOut.peek().litValue & 6)!=6 && elapsed<10000) {tick();elapsed+=1}
        assert((p.gpioOut.peek().litValue & 6)==6,"POWER_THRESHOLD_REPORT_MISSING")
        def check(): Unit=assert(p.gpioOut.peek().litValue==7,"POWER_THRESHOLD_ORACLE")
        if(badKey) {
          // Actual changed producer write, through real firmware and the bus.
          val e=intercept[org.scalatest.exceptions.TestFailedException] {check()}
          assert(e.getMessage.contains("POWER_THRESHOLD_ORACLE"));d.macroThreshold.expect(0.U)
        } else {check();d.macroThreshold.expect(1.U)}
        tick(100);d.status.aonReleased.expect(true.B);d.status.servicesReleased.expect(true.B)
      } else {
        var elapsed=0
        while(high(d.status.aonReleased) && elapsed<10000) {tick();elapsed+=1}
        assert(!high(d.status.aonReleased),"POWER_THRESHOLD_BROWNOUT_MISSING")
        d.macroReset_n.expect(false.B);d.status.servicesReleased.expect(false.B);d.macroThreshold.expect(0.U)
        p.gpioIn.poke(0.U)
        tick(40);d.status.aonReleased.expect(false.B)
        m.supplyMv.poke(3300.U);m.porReference.step(998)
        d.macroReset_n.expect(false.B);d.status.aonReleased.expect(false.B)
        m.porReference.step(4);d.macroReset_n.expect(true.B)
        d.status.aonReleased.expect(false.B);d.status.servicesReleased.expect(false.B);tick(580)
        d.status.servicesReleased.expect(true.B);d.status.resetCauses.expect(2.U)
        d.macroThreshold.expect(0.U)
        // Brownout restarts the single boot master, which reads the actual reason.
        load();expectReport(2)
      }
    }
  }
}
