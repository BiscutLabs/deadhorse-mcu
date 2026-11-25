package deadhorse.top
import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocXipBench extends SocExternalClockTest(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t30/firmware/boot.hex").toAbsolutePath.toString,i1Config=Some(SocProduction.config(realUsb=false)))
class SocXipSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t30/soc-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocXipBench].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(
      Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i",
    "--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  def exercise(d: SocXipBench): Unit={
    val p=d.i1.get
    def high(v: Bool)=v.peek().litToBoolean
    d.uartRx.poke(true.B);d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B)
    d.mainCoreReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
    p.aonServiceReset_n.poke(false.B);p.usbServiceReset_n.poke(false.B)
    p.lite.req.poke(false.B);p.lite.bits.poke(0.U.asTypeOf(p.lite.bits))
    p.aonExtraIn.poke(0.U);p.liteHalted.poke(true.B);p.resetReason.poke(0.U);p.crashCount.poke(0.U)
    p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U)
    p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B);
    p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
    SocInactiveTestInputs.drive(p.inactive,0)
    val flash=java.nio.file.Files.readAllBytes(Paths.get("build/t30/firmware/flash.bin"))
    val peer=new deadhorse.qspi_xip.FlashPeer(p.inactive.qspiCs_n,p.inactive.qspiSclk,
      p.inactive.qspiDqOut,p.inactive.qspiDqEnable,p.inactive.qspiDqIn,d.mainServiceReset_n,
      a=>if(a>=0 && a<flash.length) flash(a.toInt)&255 else 0)
    var retiredFlash=false
    var mainRuns=true
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      if(mainRuns) {
        peer.observe()
        if(d.rvfi("rvfi_valid").peek().litValue!=0 && d.rvfi("rvfi_pc_rdata").peek().litValue>=0x10000000L)
          retiredFlash=true
        d.mainClock.step()
      }
      p.aonClock.step();p.usbClock.step()
    }
    def held(): Unit={
      assert(!high(d.coreReady) && d.rvfi("rvfi_valid").peek().litValue==0,"BOOT_INITIAL_HOLD")
      assert(p.inactive.gpioEnable.peek().litValue==0)
    }
    tick(4);d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B)
    d.mainServiceReset_n.poke(true.B);p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)
    tick(30);held()
    SocTestBoot.release(d,()=>tick())
    var n=0
    while(p.inactive.gpioEnable.peek().litValue!=5 || p.inactive.gpioOut.peek().litValue!=5) {
      tick();n+=1;assert(n<50000,"XIP_PERFORMANCE_SIGNATURE")
    }
    assert(high(d.coreReady) && retiredFlash,"XIP_REAL_CORE_RETIRE")
    assert(peer.frames.nonEmpty && peer.frames.forall(_._1==0))
    // Reset only the performance client while a flash fetch is active.
    var wait=0
    while(p.inactive.qspiCs_n.peek().litValue==3) {tick();wait+=1;assert(wait<2000)}
    d.mainCoreReset_n.poke(false.B);tick(4)
    assert(!high(d.coreReady) && p.inactive.qspiCs_n.peek().litValue==2,"XIP_SHARED_FRAME_PRESERVED")
    d.mainCoreReset_n.poke(true.B);retiredFlash=false;n=0
    while(!retiredFlash) {tick();n+=1;assert(n<50000,"XIP_RESET_RESTART")}
  }
  test("performance configures XIP, executes and loads native flash across client reset") {
    simulateRaw(new SocXipBench,firtoolOpts=gates,settings=settings)(exercise)
  }
}
