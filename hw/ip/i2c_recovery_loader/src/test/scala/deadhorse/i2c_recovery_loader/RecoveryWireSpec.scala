package deadhorse.i2c_recovery_loader

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable.ArrayBuffer

/** Host drives low or releases SDA. Resolve the target's own ACK/data at its pin. */
class RecoveryWireBench extends Module {
  val scl = IO(Input(Bool()))
  val hostLow = IO(Input(Bool()))
  val sda = IO(Output(Bool()))
  val target = withReset(reset.asAsyncReset) { Module(new ClockedI2cTarget(0x35, 256)) }
  target.io.scl := scl
  sda := !(hostLow || target.io.pullLow)
  target.io.sda := sda
  target.io.applicationCancel := false.B
  target.io.readWord := "h12345678".U
  val frame = IO(Output(chisel3.util.Valid(new HostFrame)))
  frame := target.io.frame
}

class RecoveryWireSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t18/wire-simulation").toAbsolutePath
  }

  test("only complete addressed writes publish frames, including across restart and idle timeout") {
    simulate(new RecoveryWireBench) { d =>
      val frames = ArrayBuffer.empty[Seq[Int]]
      def step(count: Int): Unit = for (_ <- 0 until count) {
        if (d.frame.valid.peek().litToBoolean) {
          assert(!d.frame.bits.overflow.peek().litToBoolean)
          frames += (0 until d.frame.bits.length.peek().litValue.toInt)
            .map(i => d.frame.bits.bytes(i).peek().litValue.toInt)
        }
        d.clock.step()
      }
      def drive(clockHigh: Boolean, dataLow: Boolean): Unit = {
        d.scl.poke(clockHigh.B)
        d.hostLow.poke(dataLow.B)
        step(5)
      }
      def start(): Unit = {
        drive(true, false)
        drive(true, true)
        drive(false, true)
      }
      def stop(): Unit = {
        drive(false, true)
        drive(true, true)
        drive(true, false)
      }
      def write(byte: Int, acknowledged: Boolean = true): Unit = {
        for (bit <- 7 to 0 by -1) {
          val low = (byte & (1 << bit)) == 0
          drive(false, low)
          drive(true, low)
          drive(false, low)
        }
        drive(false, false)
        drive(true, false)
        d.sda.expect((!acknowledged).B)
        drive(false, false)
      }
      drive(true, false)
      start(); write(0x6a); stop()
      start(); write(0x68, acknowledged = false); stop()
      start(); write(0x6a); write(2); drive(false, false); step(260); stop()
      assert(frames.isEmpty)
      val command = Seq(2, 0, 0, 0, 0, 0x12, 0x34, 0x56, 0x78)
      start(); write(0x6a); command.foreach(b => write(b))
      assert(frames.isEmpty)
      start(); write(0x6a); write(3); stop()
      assert(frames.toList == List(command, Seq(3)))
    }
  }
}
