package deadhorse.bus_bridge

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class LocalPermitFormal(variant: String) extends RawModule {
  val clk=IO(Input(Clock()));val observe=IO(Input(Clock()))
  val reset_n=IO(Input(Bool()));val request=IO(Input(Bool()))
  val d=Module(new LocalPermit {
    override protected def initialPermit: Boolean=variant=="reset"
    override protected def sampled(r: Bool): Bool=variant match {
      case "stuck"=>true.B
      case "late"=>withClockAndReset(this.clk,(!this.reset_n).asAsyncReset) {RegNext(r,false.B)}
      case _=>r
    }
  })
  d.clk:=clk;d.reset_n:=reset_n;d.request:=request
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val previousRequest=RegNext(request,false.B)
    val previousPermit=RegNext(d.permit,false.B)
    val revoked=RegInit(false.B)
    when(previousPermit && !d.permit) {revoked:=true.B}
    if(variant=="cover") {
      cover(d.permit && request)
      cover(previousPermit && !d.permit)
      cover(revoked && d.permit)
    } else assert(d.permit===previousRequest)
  }
  if(variant!="cover")withClockAndReset(observe,false.B) {
    assert(reset_n || !d.permit)
  }
}
object EmitLocalPermitFormal extends App {
  require(args.length==1)
  val root=Paths.get(args(0)).toAbsolutePath.normalize
  require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
  for(v<-Seq("correct","stuck","late","reset","cover")) {
    val dir=root.resolve(v);Files.createDirectories(dir)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new LocalPermitFormal(v)),
      Array("--target-dir",dir.toString),Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
  }
  ChiselStage.emitSystemVerilogFile(new LocalPermit,Array("--target-dir",root.resolve("block").toString),
    Array("--disable-all-randomization","--lower-to-core","-strip-debug-info"))
}
