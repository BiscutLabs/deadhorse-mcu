package deadhorse.lib

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

/** Explicit clock pin allows the test to assert reset without a clock edge. */
class RegBlockTestHarness(json: String) extends RawModule {
  val description = new RegDescription(json)
  val clockPin = IO(Input(Bool()))
  val rst_n = IO(Input(Bool()))
  val bus = IO(new RegBus(description.addressWidth))
  val hw = IO(new RegHardware(description.fields))
  private val dut = Module(new RegBlock(json))
  dut.clk := clockPin.asClock
  dut.rst_n := rst_n
  dut.bus <> bus
  dut.hw <> hw
}

class RegBlockSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t05/simulation").toAbsolutePath
  }
  private def prepare(block: String, seed: Int): (String, os.Path) = {
    val dir = os.pwd / "build" / "regmap" / block
    os.proc("python3", "hw/regmap/regmap.py", s"hw/regmap/fixtures/$block/$block.regmap.yaml",
      "--out", dir.toString).call(stdout = os.Inherit, stderr = os.Inherit)
    val json = dir / s"${block}_regs.json"
    val trace = dir / "trace.json"
    os.proc("python3", "hw/regmap/trace.py", json.toString, trace.toString, "--seed", seed.toString)
      .call(stdout = os.Inherit, stderr = os.Inherit)
    (json.toString, trace)
  }
  private def runTrace(dut: RegBlockTestHarness, path: os.Path): Unit = {
    val trace = ujson.read(os.read(path))
    info(s"RegBlock seed=${trace("seed")} random requests=${trace("random_requests")} accepted=${trace("accepted_requests")}")
    assert(trace("random_requests").num >= 2000)
    def number(v: ujson.Value): BigInt = BigInt(v.num.toLong)
    def observe(expected: ujson.Value, index: Int): Unit = {
      def eq(signal: UInt, value: ujson.Value, name: String): Unit =
        assert(signal.peek().litValue == number(value), s"REG_MODEL_MISMATCH cycle=$index port=$name expected=$value")
      eq(dut.bus.req_ready, expected("req_ready"), "req_ready")
      eq(dut.bus.rsp_valid, expected("rsp_valid"), "rsp_valid")
      eq(dut.bus.rsp_rdata, expected("rsp_rdata"), "rsp_rdata")
      eq(dut.bus.rsp_error, expected("rsp_error"), "rsp_error")
      expected("hw").obj.foreach { case (name, value) => eq(dut.hw(name), value, name) }
    }
    dut.clockPin.poke(false.B)
    dut.rst_n.poke(true.B)
    dut.bus.req_valid.poke(false.B)
    dut.bus.req_write.poke(false.B)
    dut.bus.req_addr.poke(0.U)
    dut.bus.req_wdata.poke(0.U)
    dut.bus.req_wstrb.poke(0.U)
    dut.bus.rsp_ready.poke(false.B)
    dut.description.fields.foreach(f => f.ports.filter(_._3).foreach { case (suffix, _, _) =>
      dut.hw(f.key + "_" + suffix).poke(0.U)
    })
    dut.bus.req_ready.peek()
    for ((row, index) <- trace("cycles").arr.zipWithIndex) {
      val in = row("inputs")
      dut.rst_n.poke((in("reset_n").num != 0).B)
      dut.bus.req_valid.poke((in("req_valid").num != 0).B)
      dut.bus.req_write.poke((in("req_write").num != 0).B)
      dut.bus.req_addr.poke(number(in("req_addr")).U)
      dut.bus.req_wdata.poke(number(in("req_wdata")).U)
      dut.bus.req_wstrb.poke(number(in("req_wstrb")).U)
      dut.bus.rsp_ready.poke((in("rsp_ready").num != 0).B)
      in("hw").obj.foreach { case (name, value) => dut.hw(name).poke(number(value).U) }
      if (in("reset_n").num == 0) observe(row("expected"), index) // edge-free reset
      dut.clockPin.poke(true.B)
      observe(row("expected"), index)
      dut.clockPin.poke(false.B)
      observe(row("expected"), index)
    }
  }

  for ((block, seed) <- Seq("coverage" -> 50501, "mixed" -> 50502)) {
    test(s"$block registers agree with the independent Python model") {
      val (json, trace) = prepare(block, seed)
      simulateRaw(new RegBlockTestHarness(json), subdirectory = Some(block))(runTrace(_, trace))
    }
  }
  test("the identical checker rejects a deliberately corrupted expectation file") {
    val (json, trace) = prepare("mixed", 50502)
    val failure = intercept[TestFailedException] {
      simulateRaw(new RegBlockTestHarness(json), subdirectory = Some("wrong_expectation"))(
        runTrace(_, trace / os.up / "trace.wrong.json"))
    }
    assert(failure.getMessage.contains("REG_MODEL_MISMATCH"))
    info("Negative control caught: REG_MODEL_MISMATCH")
  }

  test("validated wide addresses remain distinct through JSON and hardware decode") {
    val dir = os.pwd / "build" / "regmap" / "wide"
    os.proc("python3", "hw/regmap/regmap.py", "hw/regmap/fixtures/wide/wide.regmap.yaml",
      "--out", dir.toString).call(stdout = os.Inherit, stderr = os.Inherit)
    val json = (dir / "wide_regs.json").toString
    simulateRaw(new RegBlockTestHarness(json), subdirectory = Some("wide")) { dut =>
      dut.clockPin.poke(false.B)
      dut.rst_n.poke(true.B)
      dut.bus.req_valid.poke(false.B)
      dut.bus.req_write.poke(false.B)
      dut.bus.req_addr.poke(0.U)
      dut.bus.req_wdata.poke(0.U)
      dut.bus.req_wstrb.poke(0.U)
      dut.bus.rsp_ready.poke(true.B)
      dut.bus.req_ready.peek()
      dut.rst_n.poke(false.B)
      assert(dut.bus.req_ready.peek().litToBoolean)
      dut.rst_n.poke(true.B)
      def edge(): Unit = {
        dut.clockPin.poke(true.B); dut.bus.rsp_valid.peek()
        dut.clockPin.poke(false.B); dut.bus.rsp_valid.peek()
      }
      for ((delta, expected) <- Seq(0 -> 17, 4 -> 29)) {
        dut.bus.req_addr.poke(((BigInt(1) << 65) + delta).U)
        dut.bus.req_valid.poke(true.B)
        edge()
        assert(dut.bus.rsp_valid.peek().litToBoolean)
        assert(!dut.bus.rsp_error.peek().litToBoolean)
        assert(dut.bus.rsp_rdata.peek().litValue == expected)
        dut.bus.req_valid.poke(false.B)
        edge()
      }
    }
  }
}
