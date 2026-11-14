package deadhorse.lib

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

class RegBlockWrongStrobes(json: String) extends RegBlock(json) {
  override protected def strobes: UInt = Reverse(bus.req_wstrb)
}
class RegBlockWrongReset(json: String) extends RegBlock(json) {
  override protected def initialValue(f: RegField): BigInt = f.resetValue ^ 1
}
class RegBlockWrongRead(json: String) extends RegBlock(json) {
  override protected def readResult(value: UInt): UInt = value ^ 1.U
}

/** Port-only temporal properties generated from each field's access policy.
  * Unlike the implementation's word masks, stored-field properties specify
  * each bit's preservation, software action, and hardware priority separately.
  */
class RegBlockFormal(json: String, variant: String) extends RawModule {
  val description = new RegDescription(json)
  val clock = IO(Input(Clock()))
  val reset_n = IO(Input(Bool()))
  val checking = IO(Output(Bool()))
  val bus = IO(new RegBus(description.addressWidth))
  val hw = IO(new RegHardware(description.fields))
  val dut = Module(variant match {
    case "wrong_strobes" => new RegBlockWrongStrobes(json)
    case "wrong_reset" => new RegBlockWrongReset(json)
    case "wrong_read" => new RegBlockWrongRead(json)
    case _ => new RegBlock(json)
  })
  dut.clk := clock
  dut.rst_n := reset_n
  dut.bus <> bus
  dut.hw <> hw

  withClockAndReset(clock, false.B) {
    val historyValid = RegNext(true.B)
    dontTouch(historyValid)
    checking := historyValid
    val priorReleased = RegNext(reset_n)
    val active = checking && reset_n && priorReleased
    val sampledReset = checking && !priorReleased
    val checks = scala.collection.mutable.ArrayBuffer.empty[Bool]
    def alwaysWhen(condition: Bool, property: Bool): Unit = checks += (!condition || property)
    // Prove this consequence of the existing startup contract. It excludes
    // unreachable induction states where history is disabled indefinitely
    // while the DUT has never seen reset; no input assumption is added.
    checks += (checking || !reset_n)
    val accept = bus.req_valid && bus.req_ready
    val knownAddress = description.offsets.map(o => bus.req_addr === o.U).foldLeft(false.B)(_ || _)
    val incomplete = description.fields.filter(_.access == "wo").map { f =>
      val lanes = (f.lsb / 8 to f.msb / 8).map(i => bus.req_wstrb(i))
      bus.req_addr === f.offset.U && lanes.reduce(_ || _) && !lanes.reduce(_ && _)
    }.foldLeft(false.B)(_ || _)
    val fault = !knownAddress || bus.req_addr(1, 0) =/= 0.U || (bus.req_write && incomplete)
    val software = accept && bus.req_write && !fault
    val previousAccept = RegNext(accept)
    val previousPending = RegNext(bus.rsp_valid)
    val previousReady = RegNext(bus.rsp_ready)
    val expectedPending = previousAccept || (previousPending && !previousReady)
    // Strengthening invariant: the two public control outputs are complements
    // even across reset assertion, when data-history checks are disabled.
    alwaysWhen(checking, bus.req_ready === !bus.rsp_valid)
    alwaysWhen(active, bus.rsp_valid === expectedPending && bus.req_ready === !expectedPending)
    alwaysWhen(sampledReset, bus.req_ready && !bus.rsp_valid && bus.rsp_rdata === 0.U && !bus.rsp_error)
    val oldResponse = RegNext(bus.rsp_rdata)
    val oldError = RegNext(bus.rsp_error)
    alwaysWhen(active && !previousAccept, bus.rsp_rdata === oldResponse && bus.rsp_error === oldError)
    alwaysWhen(active && previousAccept, bus.rsp_error === RegNext(fault))

    // Build expected read data bit by bit, sampling public q/d at acceptance.
    val readBits = (0 until 32).map { bit =>
      description.fields.filter(f => f.lsb <= bit && bit <= f.msb && f.access != "wo" && f.access != "w1p")
        .map { f =>
          val source = hw(f.key + (if (f.access == "ro") "_d" else "_q"))
          bus.req_addr === f.offset.U && source(bit - f.lsb)
        }.foldLeft(false.B)(_ || _)
    }
    val expectedRead = RegNext(Mux(bus.req_write || fault, 0.U(32.W), VecInit(readBits).asUInt))
    alwaysWhen(active && previousAccept, bus.rsp_rdata === expectedRead)

    description.fields.foreach { f =>
      val selected = software && bus.req_addr === f.offset.U
      if (f.stored) {
        val q = hw(f.key + "_q")
        val nextBits = (0 until f.width).map { bit =>
          val lane = (bit + f.lsb) / 8
          val written = selected && bus.req_wstrb(lane)
          val value = bus.req_wdata(bit + f.lsb)
          f.access match {
            case "rw" => Mux(written, value, q(bit))
            case "rwh" => Mux(hw(f.key + "_we").asBool, hw(f.key + "_d")(bit), Mux(written, value, q(bit)))
            case "w1c" => hw(f.key + "_set")(bit) || (q(bit) && !(written && value))
          }
        }
        alwaysWhen(active, q === RegNext(VecInit(nextBits).asUInt))
        alwaysWhen(sampledReset, q === f.resetValue.U)
      }
      if (f.access == "w1p") {
        val expected = VecInit((f.lsb to f.msb).map(bit => selected && bus.req_wstrb(bit / 8) && bus.req_wdata(bit))).asUInt
        alwaysWhen(active, hw(f.key + "_pulse") === RegNext(expected))
        alwaysWhen(sampledReset, hw(f.key + "_pulse") === 0.U)
      }
      if (f.access == "wo") {
        val issue = selected && (f.lsb / 8 to f.msb / 8).map(i => bus.req_wstrb(i)).reduce(_ || _)
        val previousIssue = RegNext(issue)
        alwaysWhen(active, hw(f.key + "_we").asBool === previousIssue)
        alwaysWhen(active && previousIssue, hw(f.key + "_wdata") === RegNext(bus.req_wdata(f.msb, f.lsb)))
        alwaysWhen(sampledReset, hw(f.key + "_we") === 0.U && hw(f.key + "_wdata") === 0.U)
      }
    }
    val hardwareCollision = description.fields.filter(_.access == "rwh").map(f =>
      software && bus.req_addr === f.offset.U && hw(f.key + "_we").asBool).foldLeft(false.B)(_ || _)
    val targets = Seq(
      active && accept && !bus.req_write && !fault,
      active && software && bus.req_wstrb =/= 15.U && bus.req_wstrb =/= 0.U,
      active && accept && bus.req_write && incomplete,
      active && bus.rsp_valid && !bus.rsp_ready,
      active && hardwareCollision,
      active && previousAccept && bus.rsp_error,
      checking && !reset_n && priorReleased && previousPending
    )
    if (variant == "cover") targets.foreach(cover(_))
    else assert(checks.reduce(_ && _))
  }
}

object EmitRegBlockFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "Usage: EmitRegBlockFormal <validated.json> build/<output>")
    val output = Paths.get(args(1)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for (variant <- Seq("correct", "wrong_strobes", "wrong_reset", "wrong_read", "cover")) {
      val dir = output.resolve(variant)
      Files.createDirectories(dir)
      def circuit = chisel3.layer.elideBlocks(new RegBlockFormal(args(0), variant))
      ChiselStage.emitSystemVerilogFile(circuit, Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
      if (variant != "cover") {
        Files.writeString(dir.resolve("RegBlockFormal.btor2"), ChiselStage.emitBtor2(circuit,
          Array.empty[String], Array("--lower-to-core", "--verification-flavor=immediate")))
      }
    }
  }
}
