package deadhorse.fpu

import chisel3._
import _root_.circt.stage.ChiselStage

class FpuAddFormal(width: Int, fault: Boolean) extends RawModule {
  val a = IO(Input(UInt(width.W))); val b = IO(Input(UInt(width.W)))
  val cin = IO(Input(Bool())); val equal = IO(Output(Bool()))
  val expected = (a +& b) + cin
  equal := FpuAdd(a,b,width,if(fault) false.B else cin) === expected(width-1,0)
}

class FpuExponentSubtractFormal(fault: Int) extends RawModule {
  val a = IO(Input(SInt(11.W))); val b = IO(Input(SInt(10.W)))
  val equal = IO(Output(Bool()))
  val actual = if (fault == 1) FpuAdd(a.asUInt, ~b.asUInt, 11, true.B).asSInt
    else if (fault == 2) FpuAdd(a.asUInt, ~(b.pad(11).asUInt), 11).asSInt
    else FpuExponentSubtract(a, b, 11)
  equal := actual === (a - b)
}

object EmitFpuAddFormal extends App {
  require(args.length==1)
  for(fault <- 0 to 2) {
    ChiselStage.emitSystemVerilogFile(new FpuExponentSubtractFormal(fault),
      Array("--target-dir",s"${args(0)}/subtract-$fault"),
      Array("--disable-all-randomization","--strip-debug-info"))
  }
  for(width<-Seq(11,25,26,28,32,51); fault<-Seq(false,true)) {
    ChiselStage.emitSystemVerilogFile(new FpuAddFormal(width,fault),
      Array("--target-dir",s"${args(0)}/$width-${if(fault) "fault" else "normal"}"),
      Array("--disable-all-randomization","--strip-debug-info"))
  }
}
