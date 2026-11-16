package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** Verification-only predicate, sampled by the original combinational checker.
  * RV32, compressed enabled: JALR clears bit zero, so its spec cannot trap on
  * alignment. The runner proves these guards against the pinned checker.
  * Deliberately no condition on the core's reported trap bit.
  */
class JalrAddressProperty extends RawModule {
  val reset = IO(Input(Bool()))
  val valid = IO(Input(Bool()))
  val instruction = IO(Input(UInt(32.W)))
  val reportedAddress = IO(Input(UInt(5.W)))
  val active = IO(Output(Bool()))
  val holds = IO(Output(Bool()))
  active := !reset && valid && instruction(6, 0) === "h67".U &&
    instruction(14, 12) === 0.U && instruction(19, 15) =/= 0.U
  holds := !active || reportedAddress === instruction(19, 15)
}

object EmitJalrAddressProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrAddressProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
