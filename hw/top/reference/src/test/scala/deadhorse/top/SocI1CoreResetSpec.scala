package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable.ArrayBuffer

/** Test-only public MMIO offer observation and actual reset-wiring fault. */
class SocI1CoreResetBench(corrupt: Boolean) extends SocExternalClockTest(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t20/i0-firmware/boot.hex").toAbsolutePath.toString,
  i1Config=Some(SocProduction.config(realUsb=false))) {
  val firstByteOffered=IO(Output(Bool()))
  firstByteOffered:=memory.peripheral.req && memory.peripheral.bits.we &&
    memory.peripheral.bits.addr==="h4001000c".U && memory.peripheral.bits.wdata===73.U
  if(corrupt) memory.serviceReset_n:=coreRelease.released
}

class SocI1CoreResetSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t20/i1/core-reset-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocI1CoreResetBench].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(
      Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i",
    "--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  private def decode(samples: Seq[Boolean]): String = {
    val bytes=ArrayBuffer.empty[Char];var at=0
    while(at+160<=samples.size) {
      if(samples(at)) at+=1
      else {
        assert(!samples(at+8) && samples(at+152),"I1_CORE_RESET_UART_FRAME")
        bytes+=(0 until 8).map(i=>if(samples(at+24+16*i)) 1<<i else 0).sum.toChar
        at+=160
      }
    }
    bytes.mkString
  }
  for(corrupt<-Seq(false,true)) test(s"core-only reset retains the offered I1 MMIO side effect, corrupt=$corrupt") {
    simulateRaw(new SocI1CoreResetBench(corrupt),firtoolOpts=gates,settings=settings) { d =>
      val p=d.i1.get
      d.uartRx.poke(true.B);d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B)
      d.mainCoreReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
      p.aonServiceReset_n.poke(false.B);p.usbServiceReset_n.poke(false.B)
      p.lite.req.poke(false.B);p.lite.bits.poke(0.U.asTypeOf(p.lite.bits))
      p.liteHalted.poke(true.B);p.resetReason.poke(0.U);p.crashCount.poke(0.U)
      p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U)
      p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B);p.recoveryScl.poke(true.B);p.recoverySda.poke(true.B)
      p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
      val samples=ArrayBuffer.empty[Boolean]
      def tick(): Unit = {
        // No JTAG operation in this core-reset test; keep the real TAP reset.
        SocInactiveTestInputs.drive(p.inactive,(samples.size&65535& ~48)|32)
        SocInactiveTestInputs.check(p.inactive)
        d.mainClock.step();p.aonClock.step();p.usbClock.step()
        samples+=d.uartTx.peek().litToBoolean
      }
      for(_<-0 until 4) tick()
      d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B);d.mainCoreReset_n.poke(true.B)
      d.mainServiceReset_n.poke(true.B);p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)
      SocTestBoot.release(d,()=>tick())
      var n=0
      while(!d.firstByteOffered.peek().litToBoolean && n<3000) {tick();n+=1}
      assert(d.firstByteOffered.peek().litToBoolean,"I1_CORE_RESET_PHASE_NOT_REACHED")
      d.mainCoreReset_n.poke(false.B)
      for(_<-0 until 4) tick()
      d.mainCoreReset_n.poke(true.B)
      var retired=0
      for(_<-0 until 3000) {
        tick()
        if(d.rvfi("rvfi_valid").asInstanceOf[Bool].peek().litToBoolean) {
          retired+=1
          assert(d.coreReady.peek().litToBoolean,"I1_CORE_EPOCH_EARLY")
          assert(!d.rvfi("rvfi_trap").asInstanceOf[Bool].peek().litToBoolean,"I1_CORE_RESET_TRAP")
        }
      }
      assert(retired>30,"I1_CORE_RESET_NO_REBOOT")
      // The retained old 'I' completes once, then the reboot prints I0\n.
      def check(): Unit=assert(decode(samples.toSeq)=="II0\n","I1_CORE_RESET_MMIO_ORACLE")
      if(corrupt) {
        val failure=intercept[org.scalatest.exceptions.TestFailedException] {check()}
        assert(failure.getMessage.contains("I1_CORE_RESET_MMIO_ORACLE"))
      } else check()
    }
  }
}
