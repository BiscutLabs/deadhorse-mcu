package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib.LocalBus
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

class SocMemoryBadValid(config: String, image: String)
    extends SocLocalMemory(new SocDescription(config), image) {
  override protected def instructionValid(value: Bool): Bool = !value
}
/** Control composition on the full production memory geometry. Memory data is
  * unobserved in these properties and can be removed by cone reduction.
  * No protocol, reset-spacing or peripheral-response assumptions are made.
  */
class SocMemoryFormal(config: String, image: String, variant: String) extends RawModule {
  val clock=IO(Input(Clock()))
  val serviceReset_n=IO(Input(Bool())); val clientReset_n=IO(Input(Bool()))
  val instruction=IO(new LocalBus); val data=IO(new LocalBus)
  val peripheral=IO(Flipped(new LocalBus))
  val d=Module(if(variant=="corrupt") new SocMemoryBadValid(config,image)
    else new SocLocalMemory(new SocDescription(config), image))
  d.clk:=clock; d.serviceReset_n:=serviceReset_n; d.clientReset_n:=clientReset_n
  d.instruction<>instruction; d.data<>data; d.peripheral<>peripheral
  val clientReset=(!(clientReset_n && serviceReset_n)).asAsyncReset
  withClockAndReset(clock,clientReset) {
    val fetched=RegNext(instruction.req && instruction.gnt,false.B)
    val pending=RegInit(false.B)
    when(data.req && data.gnt) { pending:=true.B }
    when(data.rvalid) { pending:=false.B }
    assert(!(instruction.gnt && data.gnt))
    assert(instruction.rvalid===fetched)
    assert(!data.rvalid || pending)
    assert(!(data.req && data.gnt) || !pending)
    assert(d.epochReady || (!instruction.gnt && !data.gnt && !data.rvalid && !instruction.rvalid))
    if(variant=="cover") {
      cover(instruction.rvalid && peripheral.req)
      cover(data.rvalid && !data.err)
    }
  }
  withClockAndReset(clock,(!serviceReset_n).asAsyncReset) {
    val stalled=RegNext(peripheral.req && !peripheral.gnt,false.B)
    val held=RegEnable(peripheral.bits,peripheral.req)
    when(stalled) { assert(peripheral.req); assert(peripheral.bits.asUInt===held.asUInt) }
    val resetWhileOffered=RegInit(false.B)
    val acceptedAfterReset=RegInit(false.B)
    when(peripheral.req && !clientReset_n) { resetWhileOffered:=true.B }
    when(resetWhileOffered && peripheral.req && peripheral.gnt) { acceptedAfterReset:=true.B }
    if(variant=="cover") { cover(acceptedAfterReset && d.epochReady && !peripheral.req) }
  }
}

object EmitSocMemoryFormal extends App {
  require(args.length==3,"config image output")
  for(variant<-Seq("correct","cover","corrupt")) {
    val directory=Paths.get(args(2),variant); Files.createDirectories(directory)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new SocMemoryFormal(args(0),args(1),variant)),
      Array("--target-dir",directory.toString),
      Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
  }
}
