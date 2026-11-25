package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocWatchdogOfferedSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/watchdog-offered-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocWatchdogPhaseProbe].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  for(earlyWrite<-Seq(false,true)) test(s"real watchdog expires after acceptance and before dispatch, earlyWrite=$earlyWrite") {
    def exercise(): Unit=simulateRaw(new SocWatchdogPhaseProbe(offered=true,earlyWrite=earlyWrite),settings=settings,firtoolOpts=gates) {d=>
      val p=d.pins.inactive;val o=d.observe;val m=d.model.get
      d.pins.uartRx.foreach(_.poke(true.B));d.pins.spiMiso.poke(false.B)
      d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)

      d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
      p.qspiDqIn.poke(0.U);p.jtagTck.poke(false.B);p.jtagTms.poke(true.B);p.jtagTdi.poke(false.B)
      p.imuDrdy.poke(false.B);p.gpioIn.poke(0.U);p.timerIn.poke(0.U);d.pins.aonExtraIn.poke(0.U)
      d.porBypass.poke(false.B);d.aonClockSelect.poke(false.B)
      d.externalReset_n.poke(false.B);d.monitorReset_n.poke(false.B)
      m.supplyMv.poke(0.U);m.porReference.step(3)
      def high(v: Bool)=v.peek().litToBoolean
      var armed=false;var sawExpiry=false;var now=0L;var expiryAt=0L
      def tick(n: Int=1): Unit=for(_<-0 until n) {
        d.oscIn.step(1500);m.porReference.step(31)
        val pendingBefore=high(o.downstreamPending);val offeredBefore=high(o.offered)
        m.lfClock.step();now+=1
        if(armed) {
          if(!sawExpiry && high(o.resetHold)) {
            sawExpiry=true;expiryAt=now
            // servicesReleased is the cold-owned source-qualification record;
            // actual consumers must assert warm immediately, before its clear.
            o.mainUp.expect(false.B);o.aonUp.expect(false.B)
            o.clientUp.expect(false.B);o.ready.expect(false.B)
            println(s"WATCHDOG_OFFERED_EXPIRY accepted=${o.clientAccepted.peek().litValue} offered=${high(o.offered)} dispatches=${o.dispatches.peek().litValue} commits=${o.targetCommitted.peek().litValue} returned=${o.returned.peek().litValue} acceptCycle=${o.acceptedCycle.peek().litValue}")
            assert(o.clientAccepted.peek().litValue==1 && offeredBefore &&
              o.dispatches.peek().litValue==0 && o.targetCommitted.peek().litValue==0,
              "WATCHDOG_OFFERED_PHASE")
            assert(pendingBefore,"WATCHDOG_PENDING_AT_EXPIRY")
            o.downstreamPending.expect(false.B);o.returned.expect(0.U);o.clientResponse.expect(false.B)
            p.gpioEnable.expect(0.U);p.gpioOut.expect(0.U)
          }
        }
      }
      tick(4);m.supplyMv.poke(3300.U);m.porReference.step(1002);d.externalReset_n.poke(true.B)
      tick(580);d.status.servicesReleased.expect(true.B);d.status.coreReady.expect(true.B)
      d.monitorReset_n.poke(true.B)
      armed=true;p.gpioIn.poke(4.U) // physical trigger after monitor initialization
      var elapsed=0
      while(!(sawExpiry && high(o.ready) && high(d.status.coreSleeping) && p.gpioOut.peek().litValue==2) && elapsed<1000) {
        tick();elapsed+=1
      }
      println(s"WATCHDOG_OFFERED_TIMESTAMPS acceptedCycle=${o.acceptedCycle.peek().litValue} expiryCycle=${o.expiryCycle.peek().litValue} dispatchedCycle=${o.dispatchedCycle.peek().litValue}")
      assert(sawExpiry,"WATCHDOG_PHASE_EXPIRY_MISSING")
      assert(high(o.ready) && high(d.status.coreSleeping) && p.gpioOut.peek().litValue==2,"WATCHDOG_PHASE_REBOOT_FAILED")
      o.cause.expect(true.B);o.crashes.expect(1.U);o.targetCommitted.expect(0.U);o.clientAccepted.expect(1.U)
      o.returned.expect(0.U);o.staleResponses.expect(0.U);o.earlyReady.expect(0.U)
      o.dispatches.expect(0.U);o.commitData.expect(0.U);o.commitMask.expect(0.U)
      p.gpioEnable.expect(3.U);tick(16)
      o.targetCommitted.expect(0.U);o.crashes.expect(1.U);o.staleResponses.expect(0.U);o.earlyReady.expect(0.U)
      info(s"covered real watchdog accepted/offered before dispatch, expiry AON tick=$expiryAt; zero canceled commits/returns and clean reboot")
    }
    if(earlyWrite) {
      val e=intercept[org.scalatest.exceptions.TestFailedException] {exercise()}
      assert(e.getMessage.contains("WATCHDOG_OFFERED_PHASE"))
    } else exercise()
  }
}
