package deadhorse.aon_spi
import chisel3._
import _root_.circt.stage.ChiselStage

/** Arbitrary LocalBus requests and serial input; no protocol assumptions. */
class AonSpiFormal(variant: String) extends AonSpi("build/plan05/aon_spi/aon_spi_regs.json",formalChecks=true) {
  override protected def txWriteIndex(value: UInt): UInt=if(variant=="tx") value ^ 1.U else value
  override protected def rxWriteIndex(value: UInt): UInt=if(variant=="rx") value ^ 1.U else value
  override protected def frameSelected(value: Bool): Bool=if(variant=="frame") true.B else value
}
object EmitAonSpiFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","tx","rx","frame")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new AonSpiFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
