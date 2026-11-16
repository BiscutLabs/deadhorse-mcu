package deadhorse.lib

import chisel3._
import chisel3.util.circt.{ClockGate => CirctClockGate}

sealed trait ClockGateTarget
object ClockGateTarget {
  case object Asic extends ClockGateTarget
  case object Model extends ClockGateTarget
}

/** One physical ICG, with explicitly selected verification bindings. */
class ClockGate(val target: ClockGateTarget = ClockGateTarget.Asic) extends RawModule {
  val clk_i=IO(Input(Clock())); val en_i=IO(Input(Bool())); val test_en_i=IO(Input(Bool()))
  val clk_o=IO(Output(Clock()))
  target match {
    case ClockGateTarget.Model => clk_o:=CirctClockGate(clk_i,en_i || test_en_i)
    case _ =>
      val cell=Module(new Gf180ClockGateCell)
      cell.io.CLK:=clk_i; cell.io.E:=en_i; cell.io.TE:=test_en_i; clk_o:=cell.io.Q
  }
}

/** Standard-cell ports; sources remain the byte-exact pinned PDK dependency. */
class Gf180ClockGateCell extends BlackBox {
  override def desiredName="gf180mcu_fd_sc_mcu7t5v0__icgtp_1"
  val io=IO(new Bundle {
    val CLK=Input(Clock()); val E=Input(Bool()); val TE=Input(Bool()); val Q=Output(Clock())
  })
}

/** FPGA callers must consume enable_o on every register update. */
class FpgaClockEnable extends RawModule {
  val clk_i=IO(Input(Clock())); val en_i=IO(Input(Bool())); val test_en_i=IO(Input(Bool()))
  val clk_o=IO(Output(Clock())); val enable_o=IO(Output(Bool()))
  clk_o:=clk_i; enable_o:=en_i || test_en_i
}
