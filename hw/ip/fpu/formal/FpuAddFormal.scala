package deadhorse.fpu

import chisel3._
import _root_.circt.stage.ChiselStage

class FpuAddFormal(width: Int, fault: Boolean) extends RawModule {
  val a = IO(Input(UInt(width.W))); val b = IO(Input(UInt(width.W)))
  val cin = IO(Input(Bool())); val equal = IO(Output(Bool()))
  val expected = (a +& b) + cin
  equal := FpuAdd(a,b,width,if(fault) false.B else cin) === expected(width-1,0)
}

object EmitFpuAddFormal extends App {
  require(args.length==1)
  for(width<-Seq(25,26,28,32,51); fault<-Seq(false,true)) {
    ChiselStage.emitSystemVerilogFile(new FpuAddFormal(width,fault),
      Array("--target-dir",s"${args(0)}/$width-${if(fault) "fault" else "normal"}"),
      Array("--disable-all-randomization","--strip-debug-info"))
  }
}
