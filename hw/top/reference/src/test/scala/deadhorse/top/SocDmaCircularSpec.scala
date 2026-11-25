package deadhorse.top
import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable.ArrayBuffer

class SocDmaCircularBench extends SocExternalClockTest(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t40/firmware/boot.hex").toAbsolutePath.toString,
  i1Config=Some(SocProduction.config(realUsb=false)))
class SocDmaCircularSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t40/soc-circular-simulation").toAbsolutePath
  }
  val settings=Settings.defaultRaw[SocDmaCircularBench].copy(randomization=Randomization.random.copy(memories=false))
    .withLibraryPaths(Seq(Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  test("production core consumes three UART ring laps through current while executing a busy loop") {
    simulateRaw(new SocDmaCircularBench,firtoolOpts=gates,settings=settings) {d=>
      val p=d.i1.get
      d.uartRx.poke(true.B);d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B)
      d.mainCoreReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
      p.aonServiceReset_n.poke(false.B);p.usbServiceReset_n.poke(false.B)
      p.lite.req.poke(false.B);p.lite.bits.poke(0.U.asTypeOf(p.lite.bits));p.liteHalted.poke(true.B)
      p.resetReason.poke(0.U);p.crashCount.poke(0.U);p.uartRx.foreach(_.poke(true.B))
      p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U);p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B)
      p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
      SocInactiveTestInputs.drive(p.inactive,0);p.clockControl.clearAck.poke(0.U)
      def tick(): Unit={d.uartRx.poke(d.uartTx.peek());d.mainClock.step();p.aonClock.step();p.usbClock.step()}
      for(_<-0 until 4) tick()
      d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B);d.mainCoreReset_n.poke(true.B)
      d.mainServiceReset_n.poke(true.B);p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)
      SocTestBoot.release(d,()=>tick())
      val samples=ArrayBuffer.empty[Boolean];var cycles=0;var retired=0
      while(p.inactive.gpioOut.peek().litValue!=5 && cycles<30000) {
        tick();cycles+=1;samples+=d.uartTx.peek().litToBoolean
        assert(p.inactive.gpioOut.peek().litValue!=7,"SOC_RING_FIRMWARE_BYTE_OR_STATUS_ERROR")
        if(d.rvfi("rvfi_valid").asInstanceOf[Bool].peek().litToBoolean) {
          retired+=1;assert(!d.rvfi("rvfi_trap").asInstanceOf[Bool].peek().litToBoolean,"SOC_RING_TRAP")
        }
      }
      assert(p.inactive.gpioOut.peek().litValue==5 && retired>100,s"SOC_RING_BUSY_CORE_COMPLETES gpio=${p.inactive.gpioOut.peek().litValue} retired=$retired cycles=$cycles")
      val bytes=ArrayBuffer.empty[Int];var at=0
      while(at+160<=samples.size) {
        if(samples(at)) at+=1 else {
          assert(!samples(at+8) && samples(at+152),"SOC_RING_UART_FRAME")
          bytes+=(0 until 8).map(b=>if(samples(at+24+16*b))1<<b else 0).sum;at+=160
        }
      }
      assert(bytes.toVector==Vector.tabulate(24)(i=>(71+29*i)&255),"SOC_RING_UART_ORACLE")
      println(s"T40 measured simulation: cycles=$cycles retired=$retired bytes=${bytes.size}")
    }
  }
}
