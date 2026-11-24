package deadhorse.top
import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocBootReleaseBench(bypass: Boolean=false) extends SocExternalClockTest(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t28/firmware/boot.hex").toAbsolutePath.toString,i1Config=Some(SocProduction.config(realUsb=false))) {
  override protected def bootPermit(released: Bool): Bool=if(bypass) true.B else released
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
    p.liteHalted.poke(true.B);p.resetReason.poke(0.U);p.crashCount.poke(0.U)
    p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U)
    p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B);p.recoveryScl.poke(true.B);p.recoverySda.poke(true.B)
    p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
    SocInactiveTestInputs.drive(p.inactive,0)
    var mainRuns=true
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      if(mainRuns) d.mainClock.step();p.aonClock.step();p.usbClock.step()
    }
    def held(): Unit={
      assert(!high(d.coreReady) && d.rvfi("rvfi_valid").peek().litValue==0,"BOOT_INITIAL_HOLD")
      assert(p.inactive.gpioEnable.peek().litValue==0)
    }
    tick(4);d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B);d.mainCoreReset_n.poke(true.B)
    d.mainServiceReset_n.poke(true.B);p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)
    tick(30);held()
    var hostLow=false
    def wireStep(n: Int): Unit=for(_<-0 until n) {
      p.recoverySda.poke((!hostLow && !high(p.recoverySdaLow)).B);tick()
      p.recoverySda.poke((!hostLow && !high(p.recoverySdaLow)).B)
    }
    def line(scl: Boolean,low: Boolean): Unit={hostLow=low;p.recoveryScl.poke(scl.B);wireStep(5)}
    def send(v: Int): Unit={
      for(bit<-7 to 0 by -1) {val low=(v&(1<<bit))==0;line(false,low);line(true,low);line(false,low)}
      line(false,false);line(true,false);assert(!high(p.recoverySda),"BOOT_LOADER_ACK");line(false,false)
    }
    def bytes(v: Long): Seq[Int]=(0 until 4).map(i=>((v>>>(8*i))&255).toInt)
    def command(op: Int,words: Long*): Unit={
      line(true,false);line(true,true);line(false,true);send(0x6a);send(op)
      words.flatMap(bytes).foreach(send)
      line(false,true);line(true,true);line(true,false);wireStep(8)
    }
    command(5);tick(50);held() // Invalid START is insufficient.
    val source=scala.io.Source.fromFile("build/t28/firmware/lite.hex")
    val image=try source.getLines().map(x=>java.lang.Long.parseUnsignedLong(x,16)).toVector finally source.close()
    val crc=new java.util.zip.CRC32;image.flatMap(bytes).foreach(crc.update)
    command(1,image.size*4,16,crc.getValue,0x10000,16,0,0,0x2025)
    image.zipWithIndex.foreach {case(w,i)=>command(2,i*4,w)};command(3)
    assert(high(p.loaderProgrammed));held()
    // Real lite executes the release store with main stopped.
    mainRuns=false;command(6);assert(high(p.loaderLocked));tick(5000);held()
    mainRuns=true
    var n=0
    while(p.inactive.gpioEnable.peek().litValue!=5 || p.inactive.gpioOut.peek().litValue!=5) {
      tick();n+=1;assert(n<3000,"BOOT_PERFORMANCE_SIGNATURE")
    }
    assert(high(d.coreReady))
    p.aonServiceReset_n.poke(false.B);tick(5)
    assert(high(d.coreReady),"BOOT_SERVICE_REHOLD")
    p.aonServiceReset_n.poke(true.B);tick(30);assert(high(d.coreReady))
    d.mainCoreReset_n.poke(false.B);tick(4);assert(!high(d.coreReady))
    assert(p.inactive.gpioEnable.peek().litValue==5,"BOOT_SHARED_PRESERVED")
    d.mainCoreReset_n.poke(true.B);tick(200);assert(high(d.coreReady),"BOOT_CORE_RESTART")
    d.mainServiceReset_n.poke(false.B);tick(4);d.mainServiceReset_n.poke(true.B)
    n=0
    while(p.inactive.gpioEnable.peek().litValue!=5) {tick();n+=1;assert(n<3000,"BOOT_SERVICE_RESTART")}
    // Raw whole reset re-closes even when both relevant clocks stop.
    d.warmReset_n.poke(false.B)
    assert(!high(d.coreReady) && p.inactive.gpioEnable.peek().litValue==0,"BOOT_WHOLE_ASSERT")
    tick(4);d.warmReset_n.poke(true.B);tick(100);held()
    assert(high(p.loaderLocked),"BOOT_LOCK_RETENTION")
  }
  test("real recovery loader and lite firmware release performance with independent resets") {
    simulateRaw(new SocBootReleaseBench,firtoolOpts=gates,settings=settings)(exercise)
  }
  test("bypassing the release binding is rejected by the same whole-top oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocBootReleaseBench(true),firtoolOpts=gates,settings=settings)(exercise)
    };assert(e.getMessage.contains("BOOT_INITIAL_HOLD"))
  }
}
