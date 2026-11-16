package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** All-retirement JALR metadata; frozen RV32C checker spec_trap is constant false. */
class JalrMetadataProperty extends RawModule {
  val reset = IO(Input(Bool()))
  val valid = IO(Input(Bool()))
  val instruction = IO(Input(UInt(32.W)))
  val reportedAddress = IO(Input(UInt(5.W)))
  val reportedTrap = IO(Input(Bool()))
  val active = IO(Output(Bool()))
  val addressHolds = IO(Output(Bool()))
  val trapHolds = IO(Output(Bool()))
  val nonzero = IO(Output(Bool()))
  active := !reset && valid && instruction(6,0) === "h67".U && instruction(14,12) === 0.U
  addressHolds := !active || reportedAddress === instruction(11,7)
  trapHolds := !active || !reportedTrap
  nonzero := active && instruction(11,7) =/= 0.U
}

object EmitJalrMetadataProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrMetadataProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
