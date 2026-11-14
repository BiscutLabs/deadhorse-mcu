package deadhorse.lib

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

/** Bool clock pin permits explicit edge-free reset stimulus through public IO. */
class HelloTestHarness(wrongIncrement: Boolean) extends RawModule {
  val clockPin = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val in = IO(Input(UInt(8.W)))
  val out = IO(Output(UInt(8.W)))
  private val dut = Module(if (wrongIncrement) new HelloWrongIncrement else new Hello)
  dut.clock := clockPin.asClock
  dut.reset_n := reset_n
  dut.in := in
  out := dut.out
}

class HelloSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t07/simulation").toAbsolutePath
  }
  // Specification model: adjacent entries in a circular alphabet, independent
  // of hardware addition/truncation and of observed simulation values.
  private val alphabet = (0 to 255).toVector
  private val nextByte = alphabet.zip(alphabet.tail :+ alphabet.head).toMap

  private def check(dut: HelloTestHarness): Unit = {
    def observe(expected: Int): Unit =
      assert(dut.out.peek().litValue == expected, s"HELLO_MODEL_MISMATCH expected=$expected")
    def edge(): Unit = {
      dut.clockPin.poke(false.B)
      dut.out.peek() // Evaluate the falling edge before scheduling a rising edge.
      dut.clockPin.poke(true.B)
      dut.out.peek()
      dut.clockPin.poke(false.B)
      dut.out.peek()
    }
    dut.clockPin.poke(false.B)
    dut.in.poke(19.U)
    dut.reset_n.poke(true.B)
    dut.out.peek() // Establish deasserted reset before the first assertion.
    dut.reset_n.poke(false.B)
    observe(0) // Assert reset without any clock edge.
    dut.reset_n.poke(true.B)
    observe(0)
    var previous = 0
    for (input <- alphabet) {
      dut.in.poke(input.U)
      observe(previous)
      edge()
      previous = nextByte(input)
      observe(previous)
    }
    dut.in.poke(42.U)
    edge()
    observe(43)
    dut.reset_n.poke(false.B)
    observe(0) // Reset an active/nonzero result while the clock is stopped.
    dut.in.poke(123.U)
    edge()
    observe(0)
    dut.reset_n.poke(true.B)
    observe(0)
    edge()
    observe(124)
  }

  test("registered successor, wraparound, asynchronous reset and recovery") {
    simulateRaw(new HelloTestHarness(false), subdirectory = Some("correct"))(check)
  }

  test("the behavioral checker detects a wrong increment") {
    val failure = intercept[TestFailedException] {
      simulateRaw(new HelloTestHarness(true), subdirectory = Some("wrong_increment"))(check)
    }
    assert(failure.getMessage.contains("HELLO_MODEL_MISMATCH"))
    info("Negative control caught: HELLO_MODEL_MISMATCH")
  }
}
