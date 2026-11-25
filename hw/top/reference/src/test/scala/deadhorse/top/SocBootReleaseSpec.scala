package deadhorse.top
import chisel3._
import chisel3.util.experimental.BoringUtils
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocBootReleaseBench(blockBoot: Boolean=false) extends SocExternalClockTest(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t28/firmware/boot.hex").toAbsolutePath.toString,i1Config=Some(SocProduction.config(realUsb=false))) {
  override protected def bootPermit(released: Bool): Bool=if(blockBoot) false.B else released
  val liteHeld=IO(Output(Bool()));liteHeld:=BoringUtils.bore(subsystem.get.liteBootHeld)
  val starts=IO(Output(UInt(8.W)))
  withClockAndReset(i1.get.aonClock,(!(coldReset_n && warmReset_n)).asAsyncReset) {
    val n=RegInit(0.U(8.W));when(i1.get.liteStart) {n:=n+1.U};starts:=n
  }
}
class SocBootReleaseSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t28/soc-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocBootReleaseBench].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(
      Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i",
    "--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  def exercise(d: SocBootReleaseBench): Unit={
    val p=d.i1.get
    def high(v: Bool)=v.peek().litToBoolean
    d.uartRx.poke(true.B);d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B)
    d.mainCoreReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
    p.aonServiceReset_n.poke(false.B);p.usbServiceReset_n.poke(false.B)
    p.lite.req.poke(false.B);p.lite.bits.poke(0.U.asTypeOf(p.lite.bits))
    p.liteHalted.poke(true.B);p.resetReason.poke(0.U);p.crashCount.poke(0.U);p.aonExtraIn.poke(0.U)
    p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U)
    p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B);
    p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
    p.clockControl.reset_n.poke(true.B);p.clockControl.coreIdle.poke(false.B);p.clockControl.closed.poke(false.B)
    p.clockControl.stable.poke(false.B);p.clockControl.jtagWake.poke(false.B)
    SocInactiveTestInputs.drive(p.inactive,32)
    var mainRuns=true
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      if(mainRuns) d.mainClock.step();p.aonClock.step();p.usbClock.step()
    }
    def signature(): Unit={
      var n=0
      while(p.inactive.gpioEnable.peek().litValue!=5 || p.inactive.gpioOut.peek().litValue!=5) {
        tick();n+=1;assert(n<3000,"BOOT_PERFORMANCE_SIGNATURE")
      }
      assert(high(d.coreReady))
    }
    tick(4);d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B)
    d.mainServiceReset_n.poke(true.B);p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)
    mainRuns=false;tick(50)
    assert(high(d.liteHeld) && d.starts.peek().litValue==0 && !high(d.coreReady),"BOOT_AON_WITHOUT_MAIN")
    mainRuns=true;SocTestBoot.release(d,()=>tick());signature();tick(100)
    assert(!high(d.liteHeld) && d.starts.peek().litValue==1,"BOOT_EXPLICIT_LITE_RELEASE")
    p.aonServiceReset_n.poke(false.B);tick(5)
    assert(high(d.coreReady),"BOOT_SERVICE_REHOLD")
    p.aonServiceReset_n.poke(true.B);tick(30)
    assert(high(d.coreReady) && high(d.liteHeld) && d.starts.peek().litValue==1,"BOOT_NO_LITE_AUTOSTART")
    d.mainCoreReset_n.poke(false.B);tick(4);assert(!high(d.coreReady))
    assert(p.inactive.gpioEnable.peek().litValue==5,"BOOT_SHARED_PRESERVED")
    d.mainCoreReset_n.poke(true.B);tick(200)
    var n=0;while(high(d.liteHeld)) {tick();n+=1;assert(n<3000,"BOOT_CORE_RESTART")}
    while(d.starts.peek().litValue!=2) {
      assert(high(d.coreReady) && !high(d.liteHeld) && d.starts.peek().litValue<2,"BOOT_RELEASE_ORDER")
      tick();n+=1;assert(n<3000,"BOOT_CORE_RESTART")
    }
    assert(high(d.coreReady) && d.starts.peek().litValue==2)
    d.mainServiceReset_n.poke(false.B);tick(4);d.mainServiceReset_n.poke(true.B)
    signature();tick(200)
    assert(d.starts.peek().litValue==2 && !high(d.liteHeld),"BOOT_SURVIVING_LITE_RESTARTED")
    // Whole reset still asserts with the clocks stopped; next boot is automatic.
    d.warmReset_n.poke(false.B)
    assert(!high(d.coreReady) && high(d.liteHeld) && p.inactive.gpioEnable.peek().litValue==0,"BOOT_WHOLE_ASSERT")
    tick(4);d.warmReset_n.poke(true.B);signature();tick(100)
    assert(!high(d.liteHeld) && d.starts.peek().litValue==1,"BOOT_WHOLE_RELOAD")
  }
  test("performance boots first and releases lite while independent resets retain surviving owners") {
    simulateRaw(new SocBootReleaseBench,firtoolOpts=gates,settings=settings)(exercise)
  }
  test("blocking the performance boot binding is rejected by the whole-top oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocBootReleaseBench(true),firtoolOpts=gates,settings=settings)(exercise)
    };assert(e.getMessage.contains("BOOT_PERFORMANCE_SIGNATURE"))
  }
}
