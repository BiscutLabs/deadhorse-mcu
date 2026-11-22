package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocPwmCoreResetBench extends DeadhorseSoc(
  "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
  Paths.get("build/t22/firmware/boot.hex").toAbsolutePath.toString,i1Config=Some(SocPwmFiles.config())) {
  // Observe an actual MMIO acceptance, not private PWM state.
  val applied=IO(Output(Bool()))
  applied:=memory.peripheral.req && memory.peripheral.gnt && memory.peripheral.bits.we &&
    memory.peripheral.bits.addr==="h40030000".U
}
class SocPwmCoreResetSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t22/core-reset-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocPwmCoreResetBench].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(
      Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i",
    "--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  test("real core reset preserves the active waveform and queued configuration") {
    simulateRaw(new SocPwmCoreResetBench,firtoolOpts=gates,settings=settings) {d=>
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
      var startedAt= -1;var applies=0;var resetAt= -1
      for(cycle<-0 until 12000) {
        if(d.applied.peek().litToBoolean) {applies+=1;if(applies==2) resetAt=cycle+16}
        if(cycle==resetAt) d.mainCoreReset_n.poke(false.B)
        tick()
        val enabled=p.inactive.actuatorEnable.peek().litValue==1
        if(enabled && startedAt<0) startedAt=cycle
        if(startedAt>=0) {
          val elapsed=cycle-startedAt
          val expected=if(elapsed<10000) elapsed<5000 else (elapsed-10000)%8<2
          assert(enabled && p.inactive.actuatorOut.peek().litValue.testBit(0)==expected,"PWM_CORE_RESET_WAVEFORM")
        }
      }
      assert(applies==2 && resetAt>=0 && startedAt>=0 && resetAt<startedAt+5000,"PWM_RESET_SCENARIO")
      d.warmReset_n.poke(false.B)
      assert(p.inactive.actuatorEnable.peek().litValue==0 && p.inactive.actuatorOut.peek().litValue==0)
    }
  }
}
