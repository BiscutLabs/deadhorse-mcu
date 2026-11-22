package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocPinmuxCoreResetBench extends DeadhorseSoc(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t24/firmware/boot.hex").toAbsolutePath.toString,i1Config=Some(SocPinmuxFiles.config())) {
  // Observe an actual MMIO acceptance, not private selector state.
  val applied=IO(Output(Bool()))
  applied:=memory.peripheral.req && memory.peripheral.gnt && memory.peripheral.bits.we &&
    memory.peripheral.bits.addr==="h40012208".U
}
class SocPinmuxCoreResetSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t24/core-reset-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocPinmuxCoreResetBench].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(
      Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i",
    "--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  test("real core reset preserves pin selection and registered outputs") {
    simulateRaw(new SocPinmuxCoreResetBench,firtoolOpts=gates,settings=settings) {d=>
      val p=d.i1.get
      d.uartRx.poke(true.B);d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B)
      d.mainCoreReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
      p.aonServiceReset_n.poke(false.B);p.usbServiceReset_n.poke(false.B)
      p.lite.req.poke(false.B);p.lite.bits.poke(0.U.asTypeOf(p.lite.bits))
      p.liteHalted.poke(true.B);p.resetReason.poke(0.U);p.crashCount.poke(0.U)
      p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U)
      p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B);p.recoveryScl.poke(true.B);p.recoverySda.poke(true.B)
      p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
      SocInactiveTestInputs.drive(p.inactive,0)
      def tick(): Unit={d.mainClock.step();p.aonClock.step();p.usbClock.step()}
      for(_<-0 until 4) tick()
      d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B);d.mainCoreReset_n.poke(true.B)
      d.mainServiceReset_n.poke(true.B);p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)
      var writes=0;var resetAt= -1
      for(cycle<-0 until 2400) {
        if(d.applied.peek().litToBoolean) {writes+=1;resetAt=cycle+24}
        if(cycle==resetAt) d.mainCoreReset_n.poke(false.B)
        tick()
        if(resetAt>=0 && cycle>=resetAt) {
          assert(p.inactive.gpioEnable.peek().litValue==7 && p.inactive.gpioOut.peek().litValue==5,
            "PINMUX_CORE_RESET_PRESERVES")
        }
      }
      assert(writes==1 && resetAt>=0 && resetAt<2300,"PINMUX_RESET_SCENARIO")
      d.warmReset_n.poke(false.B)
      assert(p.inactive.gpioEnable.peek().litValue==0 && p.inactive.gpioOut.peek().litValue==0)
    }
  }
}
