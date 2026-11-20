package deadhorse.usb

import chisel3._
import chisel3.util._
import java.nio.file.{Files, Paths}
import _root_.circt.stage.ChiselStage

/** Extra D50 witnesses; inherited real-model covers remain present. */
class UsbSmallInCovers(bytes: Int) extends UsbInFormal("cover",None,true,false,bytes) {
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val p=d.proof.get
    val oldTail=RegNext(p.tail,0.U);val oldHead=RegNext(p.head,0.U)
    val hadData=RegInit(false.B);when(!d.empty){hadData:=true.B}
    val seenRead=RegInit(false.B);val retried=RegInit(false.B)
    val byteRead=cadence.enable && d.consume && !d.request && !d.acknowledge && d.valid
    when(byteRead){seenRead:=true.B}
    when(cadence.enable && d.acknowledge){seenRead:=false.B;retried:=false.B}
    when(cadence.enable && d.request && p.pending && seenRead){retried:=true.B}
    def distance(a: UInt,b: UInt): UInt=Mux(b>=a,b-a,(bytes+1).U+b-a)
    cover(distance(p.head,p.tail)===bytes.U && p.stagingValid && !d.appReady)
    cover(hadData && d.empty)
    cover(oldTail===bytes.U && p.tail===0.U)
    cover(p.head<oldHead)
    cover(retried && byteRead)
    cover(cadence.enable && d.acknowledge && !d.request && distance(p.head,p.speculative)===bytes.U)
  }
}

class UsbSmallOutCovers(bytes: Int) extends UsbOutFormal("cover",None,true,false,false,bytes) {
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val p=d.proof.get
    val oldSpec=RegNext(p.speculative,0.U);val oldHead=RegNext(p.head,0.U)
    val lastByte=RegNext(cadence.enable && d.receiveReady && d.receiveValid && !d.receiveError && !d.nak,false.B)
    val hadData=RegInit(false.B);when(!d.empty){hadData:=true.B}
    val rolledBack=RegInit(false.B)
    when(cadence.enable && d.receiveReady && d.receiveError && p.speculative=/=p.tail){rolledBack:=true.B}
    def distance(a: UInt,b: UInt): UInt=Mux(b>=a,b-a,(bytes+1).U+b-a)
    val commit=cadence.enable && d.receiveReady && !d.receiveValid && !d.receiveError && !d.nak
    cover(distance(p.head,p.tail)===bytes.U && d.appValid)
    cover(hadData && d.empty)
    cover(lastByte && oldSpec===bytes.U && p.speculative===0.U)
    cover(oldHead===bytes.U && p.head===0.U)
    cover(rolledBack && commit && p.speculative=/=p.tail)
    cover(commit && distance(p.tail,p.speculative)===bytes.U)
  }
}

/** E1 restricts only the encoded protocol operation to the proved pre-enable
  * phase. Application inputs, OUT data and symbolic selection stay arbitrary.
  * Both cadence instances are production UsbBitEnable with the same clock/reset.
  */
class UsbAlignedPacketFormal(direction: String,variant: String,bytes: Int,sparse: Boolean,smallCovers: Boolean=false) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val data=IO(Input(UInt(8.W)));val operation=IO(Input(UInt(2.W)));val choose=IO(Input(Bool()))
  val push=IO(Input(Bool()));val ready=IO(Input(Bool()))
  val forgotten=if(sparse && variant=="correct") Some(IO(Input(UInt(8.W)))) else None
  val phase=Module(new UsbBitEnable);phase.clk:=clock;phase.reset_n:=reset_n
  val alignedOperation=withClockAndReset(clock,(!reset_n).asAsyncReset){RegEnable(operation,0.U(2.W),phase.preEnable)}
  if(direction=="in") {
    val subject=Module(if(smallCovers) new UsbSmallInCovers(bytes) else new UsbInFormal(variant,None,true,sparse && variant=="correct",bytes))
    subject.clock:=clock;subject.reset_n:=reset_n;subject.operation:=alignedOperation
    subject.data:=data;subject.push:=push;subject.choose:=choose
    subject.forgotten.foreach(_:=forgotten.get)
  } else {
    val subject=Module(if(smallCovers) new UsbSmallOutCovers(bytes) else new UsbOutFormal(variant,None,true,sparse && variant=="correct",false,bytes))
    subject.clock:=clock;subject.reset_n:=reset_n;subject.operation:=alignedOperation
    subject.data:=data;subject.ready:=ready;subject.choose:=choose
    subject.forgotten.foreach(_:=forgotten.get)
  }
}

/** Dedicated proof elaboration: production constructors and unchanged oracles.
  * No reset restriction or environment assumption is introduced here.
  */
object EmitUsbPacketProof {
  def main(args: Array[String]): Unit = {
    require(args.length == 4 || args.length == 5)
    val root=Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val direction=args(1);val bytes=args(2).toInt;val sparse=args(3)=="sparse"
    val environment=args.lift(4).getOrElse("original")
    require(Set("original","E1").contains(environment))
    require(Set("in","out","memory").contains(direction))
    require(Set(8,16).contains(bytes))
    require(Set("real","sparse","small-covers").contains(args(3)))
    for(variant <- (if(args(3)=="small-covers") Seq("cover") else Seq("correct","cover","corrupt"))) {
      val dir=root.resolve(variant);Files.createDirectories(dir)
      def design: RawModule = if(environment=="E1") {
        require(direction!="memory")
        new UsbAlignedPacketFormal(direction,variant,bytes,sparse,args(3)=="small-covers")
      } else if(direction=="memory") {
        require(args(3)=="real")
        new UsbPacketMemoryRefinement(variant,bytes)
      } else if(args(3)=="small-covers") {
        require(bytes==8)
        if(direction=="in") new UsbSmallInCovers(bytes) else new UsbSmallOutCovers(bytes)
      } else if(direction=="in")
        new UsbInFormal(variant,None,true,sparse && variant=="correct",bytes)
      else new UsbOutFormal(variant,None,true,sparse && variant=="correct",false,bytes)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(design),
        Array("--target-dir",dir.toString),
        Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
    }
  }
}
