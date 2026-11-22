package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class BadI1Error extends SocErrorTarget {
  override protected def responseValid(value: Bool): Bool= !value
}
class BadI1Slot extends SocResetSlot {
  override protected def responseValid(value: Bool): Bool= !value
}
class BadI1Memory(d: SocDescription) extends SocRetainedMemory(d) {
  override protected def completion(value: Bool): Bool= !value
}

/** Contract monitors with a generated legal, stable, one-outstanding requester.
  * This requester restriction is an explicit environment premise, not a claim
  * about arbitrary malformed bus traffic. Resets are otherwise unconstrained.
  * Memory data is unobserved: this proves full-geometry admission and completion,
  * not byte integrity or retention. The slot uses a real finite error backend.
  */
class SocI1Formal(kind: String, variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val peerReset_n=IO(Input(Bool()))
  val offer=IO(Input(Bool()));val command=IO(Input(new BusPayload))
  val halted=IO(Input(Bool()));val started=IO(Input(Bool()));val locked=IO(Input(Bool()))
  val loaderBusy=IO(Input(Bool()));val loaderOffer=IO(Input(Bool()))
  val loaderOffset=IO(Input(UInt(32.W)));val loaderWord=IO(Input(UInt(32.W)))
  val bus=Wire(new LocalBus)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val active=RegInit(false.B);val req=RegInit(false.B);val packet=Reg(new BusPayload)
    when(!active && offer) {packet:=command;active:=true.B;req:=true.B}
    when(bus.req && bus.gnt) {req:=false.B}
    when(bus.rvalid) {active:=false.B}
    bus.req:=req;bus.bits:=packet
    val accepted=bus.req && bus.gnt
    val pending=RegInit(false.B)
    when(accepted) {pending:=true.B}
    when(bus.rvalid) {pending:=false.B}
    assert(!bus.rvalid || pending,"I1_RESPONSE_REQUIRES_ACCEPT")
    assert(!accepted || !pending,"I1_ONE_OUTSTANDING")
    if(kind=="error") {
      val d=Module(if(variant=="corrupt") new BadI1Error else new SocErrorTarget)
      d.clk:=clock;d.reset_n:=reset_n;d.bus<>bus
      val credit=Module(new SocDrainCredit)
      credit.clk:=clock;credit.reset_n:=reset_n;credit.accepted:=accepted;credit.response:=bus.rvalid
      assert(bus.rvalid===RegNext(accepted,false.B),"I1_ERROR_LATENCY")
      assert(!bus.rvalid || bus.err && bus.rdata===0.U,"I1_ERROR_VALUE")
      assert(credit.empty=== !pending,"I1_DRAIN_CREDIT")
      if(variant=="cover") {cover(bus.rvalid)}
    } else if(kind=="slot") {
      val d=Module(if(variant=="corrupt") new BadI1Slot else new SocResetSlot)
      val release=Module(new ResetRelease)
      release.clk:=clock;release.reset_n:=reset_n && peerReset_n
      val backend=Module(new SocErrorTarget)
      backend.clk:=clock;backend.reset_n:=release.released
      d.clk:=clock;d.reset_n:=reset_n;d.endpointReset_n:=reset_n && peerReset_n
      d.endpointReady:=release.released;d.bus<>bus;backend.bus<>d.target
      val expected=RegEnable(bus.bits,accepted);val sent=RegInit(false.B)
      val fire=d.target.req && d.target.gnt
      when(accepted) {sent:=false.B}
      when(fire) {sent:=true.B}
      assert(!fire || pending && !sent,"I1_SLOT_SINGLE_DISPATCH")
      assert(!fire || d.target.bits.asUInt===expected.asUInt,"I1_SLOT_PAYLOAD")
      assert(!bus.rvalid || bus.err && bus.rdata===0.U,"I1_SLOT_ERROR_VALUE")
      assert(!d.quiescent || !pending && !d.target.req && !bus.gnt && !bus.rvalid,"I1_SLOT_QUIESCENCE")
      val age=RegInit(0.U(4.W))
      when(pending && !bus.rvalid) {age:=age+1.U}.otherwise {age:=0.U}
      assert(!pending || age<12.U,"I1_SLOT_FINITE_BACKEND_BOUND")
      val cancelled=RegInit(false.B)
      when(pending && !peerReset_n) {cancelled:=true.B}
      if(variant=="cover") {cover(cancelled && bus.rvalid);cover(fire)}
    } else {
      require(kind=="memory")
      val description=new SocDescription("build/t20/map/soc.json")
      val d=Module(if(variant=="corrupt") new BadI1Memory(description) else new SocRetainedMemory(description))
      d.clk:=clock;d.reset_n:=reset_n;d.bus<>bus
      d.halted:=halted;d.started:=started;d.locked:=locked;d.loaderBusy:=loaderBusy
      d.memValid:=loaderOffer;d.memOffset:=loaderOffset;d.memWord:=loaderWord
      // Independent architectural permissions from docs/spec/soc.md.
      val program=bus.bits.addr>="h30000000".U && bus.bits.addr<"h30000800".U
      val work=bus.bits.addr>="h30000800".U && bus.bits.addr<"h30000c00".U
      val lite=bus.bits.origin===0.U;val main=bus.bits.origin===1.U
      val allowed= !bus.bits.addr(1,0).orR && (
        program && !bus.bits.we && (lite && (halted || started) || main && halted && !loaderBusy) ||
        work && !loaderBusy && (lite || main && halted))
      val expectedError=RegEnable(!allowed,accepted);val wasWrite=RegEnable(bus.bits.we,accepted)
      val quick=RegNext(accepted && (!allowed || bus.bits.we),false.B)
      val read=RegNext(RegNext(accepted && allowed && !bus.bits.we,false.B),false.B)
      assert(bus.rvalid===(quick || read),"I1_RETAINED_RESPONSE_TIMING")
      assert(!bus.rvalid || bus.err===expectedError,"I1_RETAINED_PERMISSION")
      assert(!bus.rvalid || !(wasWrite || bus.err) || bus.rdata===0.U,"I1_RETAINED_ZERO_REPLY")
      val load=loaderOffer && d.memReady
      val earned=load && halted && !locked && loaderOffset<2048.U && !loaderOffset(1,0).orR
      assert(d.memDone===RegNext(earned,false.B),"I1_LOADER_EARNED_DONE")
      assert(!(accepted && load),"I1_MEMORY_EXCLUSIVE_PORT")
      if(variant=="cover") {cover(d.memDone);cover(bus.rvalid && !bus.err && !wasWrite)}
    }
  }
}

object EmitSocI1Formal extends App {
  require(args.length==2,"kind output")
  for(variant<-Seq("correct","cover","corrupt")) {
    val directory=Paths.get(args(1),variant);Files.createDirectories(directory)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new SocI1Formal(args(0),variant)),
      Array("--target-dir",directory.toString),
      Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
  }
}
