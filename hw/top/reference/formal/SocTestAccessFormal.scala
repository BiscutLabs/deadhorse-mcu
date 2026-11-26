package deadhorse.top

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

/** Independent full-word serial oracle, not the implementation's bit matcher.
  * Observes the public output at positive TCK; half-edge placement is simulated.
  */
class SocTestAccessFormal(variant: String) extends RawModule {
  val tck=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val tms=IO(Input(Bool()));val tdi=IO(Input(Bool()))
  val bypass=IO(Input(Bool()));val source=IO(Input(Bool()));val scanReset_n=IO(Input(Bool()))
  val d=Module[SocTestAccess](variant match {
    case "early"=>new SocTestAccess {override protected def lastBit: UInt=30.U(5.W)}
    case "wrong-key"=>new SocTestAccess {override protected def key: BigInt=BigInt("D37A6C94",16)}
    case _=>new SocTestAccess
  })
  d.tck:=tck;d.externalReset_n:=reset_n;d.tms:=tms;d.tdi:=tdi
  d.porBypass:=bypass;d.aonClockSelect:=source;d.scanReset_n:=scanReset_n
  withClockAndReset(tck,(!reset_n).asAsyncReset) {
    val age=RegInit(0.U(6.W))
    val word=RegInit(0.U(32.W))
    val valid=RegInit(true.B)
    val expected=RegInit(false.B)
    when(age<34.U) {age:=age+1.U}
    when(age>=2.U && age<34.U) {
      word:=Cat(word(30,0),tdi)
      valid:=valid && tms && bypass && source && !scanReset_n
      when(age===33.U) {
        expected:=valid && tms && bypass && source && !scanReset_n &&
          Cat(word(30,0),tdi)===BigInt("D37A6C95",16).U
      }
    }
    assert(d.testMode===expected)
    cover(d.testMode)
    cover(age===34.U && !d.testMode)
  }
}

object EmitSocTestAccessFormal extends App {
  for(variant<-Seq("correct","early","wrong-key")) {
    val path=Paths.get(args(0),variant);Files.createDirectories(path)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new SocTestAccessFormal(variant)),
      Array("--target-dir",path.toString),Array("--disable-all-randomization","--disable-opt",
        "--verification-flavor=immediate","--lower-to-core","--strip-debug-info"))
  }
}
