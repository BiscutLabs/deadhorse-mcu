package deadhorse.reference

import chisel3._
import chisel3.experimental.{Param, RawParam}
import circt.stage.ChiselStage
import scala.collection.immutable.ListMap
import java.nio.file.{Files, Path}

/** Verification-only adapter. The source list and every parameter come from
  * the checked reference lock/config; this module is never chip RTL.
  */
class ReferencePorts(fields: Seq[(String, Int, Boolean)]) extends Record {
  val elements = ListMap(fields.map { case (name, width, input) =>
    val data: Data = if (name == "clk_i") Clock() else UInt(width.W)
    name -> (if (input) Input(data) else Output(data))
  }: _*)
}

class ReferenceCore(params: Map[String, Param], fields: Seq[(String, Int, Boolean)])
    extends BlackBox(params) {
  override def desiredName = "ibex_top"
  val io = IO(new ReferencePorts(fields))
}

class ReferenceFormal(params: Map[String, Param], fields: Seq[(String, Int, Boolean)],
    fault: Boolean, nonzeroFault: Boolean = false)
    extends RawModule {
  override def desiredName = "rvfi_wrapper"
  val clock = IO(Input(Clock()))
  val reset = IO(Input(Bool()))
  // Unconnected by the upstream testbench, made symbolic by setundef -anyseq.
  val instruction = IO(Input(UInt(32.W)))
  val readData = IO(Input(UInt(32.W)))
  val rvfi = IO(new Record {
    val elements = ListMap(fields.filter(_._1.startsWith("rvfi_")).map {
      case (name, width, _) => name.stripPrefix("rvfi_") -> Output(UInt(width.W))
    }: _*)
  })
  val core = Module(new ReferenceCore(params, fields))
  def in(name: String) = core.io.elements(name).asInstanceOf[UInt]
  core.io.elements("clk_i").asInstanceOf[Clock] := clock
  fields.filter(p => p._3 && p._1 != "clk_i").foreach { case (name, _, _) => in(name) := 0.U }
  in("rst_ni") := !reset
  in("scan_rst_ni") := 1.U
  in("test_en_i") := 1.U
  in("fetch_enable_i") := 5.U
  in("boot_addr_i") := "h80000000".U
  in("instr_gnt_i") := in("instr_req_o")
  in("data_gnt_i") := in("data_req_o")
  withClockAndReset(clock, reset.asAsyncReset) {
    in("instr_rvalid_i") := RegNext(in("instr_req_o"), 0.U)
    in("data_rvalid_i") := RegNext(in("data_req_o"), 0.U)
    in("instr_rdata_i") := RegNext(instruction)
    in("data_rdata_i") := RegNext(readData)
  }
  // Optional diagnostic forces fault witnesses to write a real destination.
  // The ordinary acceptance wrapper and its inputs remain unchanged.
  val faultMask = if (nonzeroFault) Mux(in("rvfi_rd_addr") =/= 0.U, 1.U, 0.U) else 1.U
  rvfi.elements.foreach { case (name, port) =>
    port := (if (fault && name == "rd_wdata") in("rvfi_" + name) ^ faultMask else in("rvfi_" + name))
  }
}

object EmitReferenceFormal {
  def main(args: Array[String]): Unit = {
    val directory = Path.of(args(0))
    val params = Files.readAllLines(directory.resolve("parameters.tsv")).toArray.toSeq.map { line =>
      val pair = line.toString.split("\t", 2)
      pair(0) -> RawParam(pair(1))
    }.toMap
    val fields = Files.readAllLines(directory.resolve("ports.tsv")).toArray.toSeq.map { line =>
      val p = line.toString.split("\t")
      (p(0), p(1).toInt, p(2) == "input")
    }
    val mode = args.lift(1).getOrElse("none")
    require(Set("none", "fault", "fault-nonzero").contains(mode), "Unknown formal adapter mode")
    ChiselStage.emitSystemVerilogFile(new ReferenceFormal(params, fields, mode != "none", mode == "fault-nonzero"),
      Array("--target-dir", directory.toString), Array("--disable-all-randomization"))
  }
}
