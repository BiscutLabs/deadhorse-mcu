package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocWatchdogPhaseSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/watchdog-phase-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocWatchdogPhaseProbe].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  for(badKey<-Seq(false,true)) test(s"real watchdog expiry drains committed START, wrongKey=$badKey") {
    def exercise(): Unit=simulateRaw(new SocWatchdogPhaseProbe(badKey),settings=settings,firtoolOpts=gates) {d=>
      val p=d.pins.inactive;val o=d.observe;val m=d.model.get
      d.pins.uartRx.foreach(_.poke(true.B));d.pins.spiMiso.poke(false.B)
      d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)
      d.pins.recoveryScl.poke(true.B);d.pins.recoverySda.poke(true.B)
      d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
      p.qspiDqIn.poke(0.U);p.jtagTck.poke(false.B);p.jtagTms.poke(true.B);p.jtagTdi.poke(false.B)
      p.imuDrdy.poke(false.B);p.gpioIn.poke(0.U);p.timerIn.poke(0.U)
      d.porBypass.poke(false.B);d.aonClockSelect.poke(false.B)
      d.externalReset_n.poke(false.B);d.monitorReset_n.poke(false.B)
      m.supplyMv.poke(0.U);m.porReference.step(3)
      def high(v: Bool)=v.peek().litToBoolean
      var armed=false;var sawExpiry=false;var now=0L;var expiryAt=0L
      def tick(n: Int=1): Unit=for(_<-0 until n) {
        d.oscIn.step(1500);m.porReference.step(31);m.lfClock.step();now+=1
        if(armed) {
          d.status.servicesReleased.expect(true.B);o.mainUp.expect(true.B);o.aonUp.expect(true.B)
          if(!sawExpiry && high(o.resetHold)) {
            sawExpiry=true;expiryAt=now
            o.clientUp.expect(false.B);o.ready.expect(false.B)
            o.clientAccepted.expect(1.U);o.targetCommitted.expect(1.U)
            o.downstreamPending.expect(true.B);o.returned.expect(0.U);o.clientResponse.expect(false.B)
            o.commitData.expect("h57445354".U);o.commitMask.expect(15.U);o.targetOrigin.expect(1.U)
            p.gpioEnable.expect(3.U);p.gpioOut.expect(1.U)
          }
        }
      }
      tick(4);m.supplyMv.poke(3300.U);m.porReference.step(1002);d.externalReset_n.poke(true.B)
      tick(580);d.status.servicesReleased.expect(true.B);d.status.coreReady.expect(false.B)
      d.monitorReset_n.poke(true.B)
      var hostLow=false
      def wireStep(n: Int): Unit=for(_<-0 until n) {
        d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B);tick()
        d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B)
      }
      def line(scl: Boolean,low: Boolean): Unit={hostLow=low;d.pins.recoveryScl.poke(scl.B);wireStep(5)}
      def send(byte: Int): Unit={
        for(bit<-7 to 0 by -1) {val low=(byte&(1<<bit))==0;line(false,low);line(true,low);line(false,low)}
        line(false,false);line(true,false);assert(!high(d.pins.recoverySda),"WATCHDOG_LOADER_ACK");line(false,false)
      }
      def bytes(v: Long): Seq[Int]=(0 until 4).map(i=>((v>>>(8*i))&255).toInt)
      def command(op: Int,words: Seq[Long]=Seq.empty): Unit={
        line(true,false);line(true,true);line(false,true);send(0x6a);send(op)
        words.flatMap(bytes).foreach(send);line(false,true);line(true,true);line(true,false);wireStep(8)
      }
      val source=scala.io.Source.fromFile("build/t33/client-firmware/release.hex")
      val image=try source.getLines().map(x=>java.lang.Long.parseUnsignedLong(x,16)).toVector finally source.close()
      val crc=new java.util.zip.CRC32;image.flatMap(bytes).foreach(crc.update)
      command(1,Seq(image.size*4L,16,crc.getValue,0x10000,16,0,0,0x2025))
      image.zipWithIndex.foreach {case(word,index)=>command(2,Seq(index*4L,word))}
      command(3);armed=true;command(6)
      var elapsed=0
      while(!(sawExpiry && high(o.ready) && high(d.status.coreSleeping) && p.gpioOut.peek().litValue==2) && elapsed<1000) {
        tick();elapsed+=1
      }
      assert(sawExpiry,"WATCHDOG_PHASE_EXPIRY_MISSING")
      assert(high(o.ready) && high(d.status.coreSleeping) && p.gpioOut.peek().litValue==2,"WATCHDOG_PHASE_REBOOT_FAILED")
      o.cause.expect(true.B);o.crashes.expect(1.U);o.targetCommitted.expect(1.U);o.clientAccepted.expect(1.U)
      o.returned.expect(1.U);o.staleResponses.expect(0.U);o.earlyReady.expect(0.U)
      p.gpioEnable.expect(3.U);tick(16)
      o.targetCommitted.expect(1.U);o.crashes.expect(1.U);o.staleResponses.expect(0.U);o.earlyReady.expect(0.U)
      info(s"covered real watchdog committed START/in-flight return, expiry AON tick=$expiryAt; reboot and preserved GPIO verified")
    }
    if(badKey) {
      val e=intercept[org.scalatest.exceptions.TestFailedException] {exercise()}
      assert(e.getMessage.contains("WATCHDOG_PHASE_EXPIRY_MISSING"))
    } else exercise()
  }
}
