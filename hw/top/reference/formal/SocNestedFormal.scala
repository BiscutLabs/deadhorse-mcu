package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib._
import deadhorse.bus.{BusFabric,BusRegion}
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class BadNestedDrain extends SocNestedDrain {
  override protected def acknowledgement(value: Bool): Bool=true.B
}
/** Actual child fabric and drain glue, with a legal variable-latency endpoint.
  * No restrictions on upstream requests, admission or sampled resets.
  * Endpoint delay is chosen on acceptance and may outlast the real 128-edge
  * fabric watchdog. This is a protocol-model premise, not an endpoint proof.
  */
class SocNestedFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val peerReset_n=IO(Input(Bool()))
  val bus=IO(new LocalBus);val admit=IO(Input(Bool()));val delay=IO(Input(UInt(8.W)))
  val f=Module(new BusFabric(1,Seq(BusRegion(BigInt("40000000",16),256))))
  f.clk:=clock;f.reset_n:=reset_n;f.master(0)<>bus;f.admit(0):=admit;f.allow(0):=true.B
  f.quiescent(0):=false.B
  val d=Module(if(variant=="corrupt") new BadNestedDrain else new SocNestedDrain)
  d.clk:=clock;d.reset_n:=reset_n;d.request:=bus.req;d.grant:=bus.gnt;d.response:=bus.rvalid
  d.waiting:=f.waiting(0);d.isolated:=f.isolated(0)
  d.targetRequest:=f.target(0).req;d.targetResponse:=f.target(0).rvalid
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val pending=RegInit(false.B);val grant=RegInit(false.B);val response=RegInit(false.B)
    val remaining=Reg(UInt(8.W))
    grant:= !pending && !grant && !response && f.target(0).req
    response:=false.B
    when(grant && f.target(0).req) {pending:=true.B;remaining:=delay}
    when(pending) {
      when(remaining===0.U) {response:=true.B;pending:=false.B}
        .otherwise {remaining:=remaining-1.U}
    }
    f.target(0).gnt:=grant;f.target(0).rvalid:=response
    f.target(0).rdata:=0.U;f.target(0).err:=true.B
    assert(!d.quiescent || !pending,"I1_NESTED_NO_ORPHAN_ACK")
    val hadResponse=RegInit(false.B);when(response) {hadResponse:=true.B}
    if(variant=="cover") {cover(response);cover(hadResponse && d.quiescent)}
  }
}

object EmitSocNestedFormal extends App {
  require(args.length==1,"output")
  for(variant<-Seq("correct","cover","corrupt")) {
    val directory=Paths.get(args(0),variant);Files.createDirectories(directory)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new SocNestedFormal(variant)),
      Array("--target-dir",directory.toString),
      Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
  }
}
