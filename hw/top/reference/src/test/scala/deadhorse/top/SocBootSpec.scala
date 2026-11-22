package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim, Randomization, Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable.ArrayBuffer

class SocBootSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t20/i0-simulation").toAbsolutePath
  }
  private val settings = Settings.defaultRaw[SocCoreAssembly].copy(
    randomization = Randomization.random.copy(memories = false)).withLibraryPaths(Seq(
      Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv")
        .toAbsolutePath.toString))
  private val gateBinding = Array("--ckg-name=prim_generic_clock_gating", "--ckg-input=clk_i",
    "--ckg-output=clk_o", "--ckg-enable=en_i", "--ckg-test-enable=test_en_i")
  private def decode(samples: Seq[Boolean]): String = {
    val bytes = ArrayBuffer.empty[Char]
    var at = 0
    while(at + 160 <= samples.size) {
      if(samples(at)) at += 1
      else {
        assert(!samples(at + 8) && samples(at + 152), "UART_FRAME_MODEL")
        val value = (0 until 8).map(bit => if(samples(at + 24 + 16*bit)) 1 << bit else 0).sum
        bytes += value.toChar; at += 160
      }
    }
    bytes.mkString
  }
  for(integrated<-Seq(false,true)) test(s"${if(integrated) "I1" else "I0"} boots faithful RV32IMFC, checks SRAM byte writes and FMUL, and prints on real UART") {
    val receipt=ujson.read(os.read(os.Path("build/t20/i0-firmware/result.json",os.pwd)))
    assert(receipt("status").str=="prepared_not_executed", "I0_PREPARATION_RECEIPT")
    val digest=java.security.MessageDigest.getInstance("SHA-256")
      .digest(java.nio.file.Files.readAllBytes(Paths.get("build/t20/i0-firmware/boot.hex")))
      .map(b=>f"${b & 255}%02x").mkString
    assert(digest==receipt("rom_sha256").str, "I0_ROM_RECEIPT")
    simulateRaw(if(integrated) new DeadhorseSoc("build/t20/map/soc.json", "build/t20/i0-firmware/uart_regs.json",
      Paths.get("build/t20/i0-firmware/boot.hex").toAbsolutePath.toString,
      i1Config=Some(SocProduction.config(realUsb=false))) else new SocMinimalI0(
        "build/t20/map/soc.json","build/t20/i0-firmware/uart_regs.json",
        Paths.get("build/t20/i0-firmware/boot.hex").toAbsolutePath.toString),
      firtoolOpts=gateBinding, settings=settings) { d =>
      d.uartRx.poke(true.B)
      d.coldReset_n.poke(false.B); d.warmReset_n.poke(false.B)
      d.mainCoreReset_n.poke(false.B); d.mainServiceReset_n.poke(false.B)
      d.i1.foreach { p =>
        p.aonServiceReset_n.poke(false.B);p.usbServiceReset_n.poke(false.B)
        p.lite.req.poke(false.B);p.lite.bits.poke(0.U.asTypeOf(p.lite.bits))
        p.liteHalted.poke(true.B);p.resetReason.poke(0.U);p.crashCount.poke(0.U)
        p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.spiTimeNow.poke(0.U)
        p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B);p.recoveryScl.poke(true.B);p.recoverySda.poke(true.B)
        p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B)
      }
      def tick(): Unit = {
        d.mainClock.step();d.i1.foreach {p=>p.aonClock.step();p.usbClock.step()}
      }
      for(_<-0 until 4) tick()
      d.coldReset_n.poke(true.B); d.warmReset_n.poke(true.B)
      d.mainCoreReset_n.poke(true.B); d.mainServiceReset_n.poke(true.B)
      d.i1.foreach {p=>p.aonServiceReset_n.poke(true.B);p.usbServiceReset_n.poke(true.B)}
      if(integrated) SocTestBoot.release(d,()=>tick())
      val samples = ArrayBuffer.empty[Boolean]
      var retired = 0; var sawMultiply = false
      for(_ <- 0 until 3000) {
        tick()
        samples += d.uartTx.peek().litToBoolean
        if(d.rvfi("rvfi_valid").asInstanceOf[Bool].peek().litToBoolean) {
          retired += 1
          assert(!d.rvfi("rvfi_trap").asInstanceOf[Bool].peek().litToBoolean, "I0_UNEXPECTED_TRAP")
          val instruction = d.rvfi("rvfi_insn").asInstanceOf[UInt].peek().litValue
          if((instruction & 0x7f) == 0x53 && ((instruction >> 25) & 0x7f) == 8) sawMultiply = true
        }
      }
      assert(retired > 30 && sawMultiply, "I0_DID_NOT_EXECUTE_CORE_AND_FPU")
      assert(decode(samples.toSeq) == "I0\n", "I0_UART_PAYLOAD")
      // Deliberately corrupt a sampled data bit; the same decoder must reject it.
      val start = samples.indexWhere(!_)
      val corrupt = samples.toArray; corrupt(start + 24) = !corrupt(start + 24)
      assert(decode(corrupt.toSeq) != "I0\n", "I0_UART_NEGATIVE_CONTROL")
    }
  }
}
