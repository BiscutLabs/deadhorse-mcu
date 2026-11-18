package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import chisel3.util.Cat
import deadhorse.fpu.{Fpu, FpuOp}
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Connect the same two MAC clients and intermediate-value registers as the faithful core. */
class SharedMultiplyHarness extends RawModule {
  val tick = IO(Input(Bool()))
  val reset = IO(Input(Bool()))
  val issueFloat = IO(Input(Bool()))
  val acceptFloat = IO(Input(Bool()))
  val cancelFloat = IO(Input(Bool()))
  val issueInteger = IO(Input(Bool()))
  val acceptInteger = IO(Input(Bool()))
  val corruptMac = IO(Input(Bool()))
  val floatOwnsMac = IO(Output(Bool()))
  val floatValid = IO(Output(Bool()))
  val floatResult = IO(Output(UInt(32.W)))
  val floatFlags = IO(Output(UInt(5.W)))
  val integerValid = IO(Output(Bool()))
  val integerResult = IO(Output(UInt(32.W)))
  val integerWrite = IO(Output(Bool()))

  val fp = withClockAndReset(tick.asClock, reset.asAsyncReset) { Module(new Fpu(shareIntegerMac = true)) }
  val md = Module(new IbexMultdivFast(shareIntegerMac = true))
  md.sharedMac.get <> fp.sharedMac.get
  fp.sharedMac.get.result := Mux(corruptMac, 0.U, md.sharedMac.get.result)
  fp.io.req.valid := issueFloat
  fp.io.req.bits.op := FpuOp("MUL")
  fp.io.req.bits.a := "h3fc00000".U  // 1.5
  fp.io.req.bits.b := "hc0200000".U  // -2.5
  fp.io.req.bits.c := 0.U
  fp.io.req.bits.rm := 0.U
  fp.io.rsp.ready := acceptFloat
  fp.io.cancel := cancelFloat
  floatOwnsMac := fp.sharedMac.get.owner
  floatValid := fp.io.rsp.valid
  floatResult := fp.io.rsp.bits.result
  floatFlags := fp.io.rsp.bits.flags

  md.clk_i := tick.asClock
  md.rst_ni := !reset
  md.mult_en_i := issueInteger
  md.mult_sel_i := issueInteger
  md.div_en_i := false.B
  md.div_sel_i := false.B
  md.data_ind_timing_i := false.B
  md.multdiv_ready_id_i := acceptInteger
  md.operator_i := 1.U // MULH
  md.signed_mode_i := 3.U
  md.op_a_i := "hd2345678".U
  md.op_b_i := "h83c45678".U
  md.alu_adder_ext_i := 0.U
  md.alu_adder_i := 0.U
  md.equal_to_zero_i := false.B
  withClockAndReset(tick.asClock, reset.asAsyncReset) {
    val intermediate = RegInit(0.U(34.W))
    when(md.imd_val_we_o(0)) { intermediate := md.imd_val_d_o(67, 34) }
    md.imd_val_q_i := Cat(intermediate, 0.U(34.W))
  }
  integerValid := md.valid_o
  integerResult := md.multdiv_result_o
  integerWrite := md.imd_val_we_o(0)
}

class SharedMultiplySpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t13/shared-multiply").toAbsolutePath
  }

  test("registered MAC ownership survives backpressure and releases on completion, cancel or reset") {
    simulateRaw(new SharedMultiplyHarness, subdirectory = Some("owner")) { d =>
      def edge(): Unit = {
        d.tick.poke(true.B)
        d.floatOwnsMac.peek()
        d.tick.poke(false.B)
        d.floatOwnsMac.peek()
      }
      d.tick.poke(false.B)
      d.reset.poke(true.B)
      d.issueFloat.poke(false.B)
      d.acceptFloat.poke(false.B)
      d.cancelFloat.poke(false.B)
      d.issueInteger.poke(false.B)
      d.acceptInteger.poke(false.B)
      d.corruptMac.poke(false.B)
      edge()
      d.reset.poke(false.B)
      def launchFloat(): Unit = {
        d.floatOwnsMac.expect(false.B)
        d.issueFloat.poke(true.B)
        d.floatOwnsMac.expect(false.B)
        edge()
        d.issueFloat.poke(false.B)
        d.floatOwnsMac.expect(true.B)
      }
      def checkInteger(): Unit = {
        val a = BigInt("d2345678", 16) - (BigInt(1) << 32)
        val b = BigInt("83c45678", 16) - (BigInt(1) << 32)
        d.issueInteger.poke(true.B)
        var edges = 0
        while (!d.integerValid.peek().litToBoolean && edges < 5) { edge(); edges += 1 }
        for (_ <- 0 until 3) {
          d.integerValid.expect(true.B)
          d.integerResult.expect((a * b >> 32).U)
          edge()
        }
        d.acceptInteger.poke(true.B)
        edge()
        d.issueInteger.poke(false.B)
        d.acceptInteger.poke(false.B)
      }
      // Exercise each cycle up to the existing T12 MUL deadline, including
      // acquisition, all four partials, rounding, and an unconsumed response.
      for (offset <- 0 to 38; useReset <- Seq(false, true)) {
        launchFloat()
        d.issueInteger.poke(true.B)
        for (_ <- 0 until offset) {
          d.floatOwnsMac.expect(true.B)
          d.integerWrite.expect(false.B)
          edge()
        }
        if (useReset) d.reset.poke(true.B) else d.cancelFloat.poke(true.B)
        edge()
        d.reset.poke(false.B)
        d.cancelFloat.poke(false.B)
        d.floatOwnsMac.expect(false.B)
        d.floatValid.expect(false.B)
        checkInteger()
      }
      for (bad <- Seq(false, true)) {
        d.corruptMac.poke(bad.B)
        launchFloat()
        d.issueInteger.poke(true.B)
        var edges = 0
        while (!d.floatValid.peek().litToBoolean && edges < 38) {
          d.integerWrite.expect(false.B)
          edge()
          edges += 1
        }
        d.floatValid.expect(true.B)
        for (_ <- 0 until 3) {
          d.floatOwnsMac.expect(true.B)
          d.integerWrite.expect(false.B)
          val matched = d.floatResult.peek().litValue == BigInt("c0700000", 16)
          assert(matched == !bad, "1.5 × -2.5 or stuck-MAC control")
          if (!bad) d.floatFlags.expect(0.U)
          edge()
        }
        d.acceptFloat.poke(true.B)
        edge()
        d.acceptFloat.poke(false.B)
        d.floatOwnsMac.expect(false.B)
        checkInteger()
      }
    }
  }
}
