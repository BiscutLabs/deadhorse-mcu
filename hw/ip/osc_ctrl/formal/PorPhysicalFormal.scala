package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils

/** Digital composition only: rawGood and cold_n are arbitrary analog inputs.
  * Their voltage thresholds, initialization and pulse recognition are NOT
  * assumed proved by this harness.
  */
class PorPhysicalFormal(edges: Int=1000, bypass: Boolean=false) extends RawModule {
  val reference=IO(Input(Clock()))
  val cold_n=IO(Input(Bool()));val rawGood=IO(Input(Bool()))
  val threshold=IO(Input(UInt(2.W)))
  val dut=Module[PorQualifierPhysical](if(bypass) new PorQualifierPhysical(edges) {
    override protected def complete(count: UInt): Bool=count===0.U
  } else new PorQualifierPhysical(edges))
  dut.reference:=reference;dut.cold_n:=cold_n
  dut.rawGood:=rawGood;dut.threshold:=threshold
  withClockAndReset(reference,(!(cold_n && rawGood)).asAsyncReset) {
    // Independent elapsed-valid history; unlike the DUT it has no selector
    // acknowledgement or reset-release pipeline. Qualification cannot lead it.
    val elapsed=RegInit(0.U(log2Ceil(edges+1).W))
    when(elapsed<edges.U) {elapsed:=elapsed+1.U}
    assert(BoringUtils.bore(dut.count)<=elapsed)
    assert(!dut.supplyReset_n || elapsed===edges.U)
    // Proved strengthening facts, never assumptions: arbitrary induction
    // states above either saturation point are unreachable from cold reset.
    assert(elapsed<=edges.U)
    assert(BoringUtils.bore(dut.count)<edges.U)
    cover(dut.supplyReset_n)
  }
  withClockAndReset(reference,(!cold_n).asAsyncReset) {
    val past=RegNext(true.B,false.B)
    val powered=RegNext(dut.powerOn_n,false.B)
    val brown=RegNext(dut.brownout,false.B)
    val released=RegNext(dut.supplyReset_n,false.B)
    when(past) {
      assert(!powered || dut.powerOn_n)
      assert(!brown || dut.brownout)
      assert(!(powered && !released) || dut.brownout)
    }
    assert(dut.higher===(threshold===1.U))
    cover(dut.brownout && dut.supplyReset_n)
  }
}

object EmitPorPhysicalFormal extends App {
  require(args.length==1)
  for((name,edges,bypass)<-Seq(("correct",1000,false),("bypass",1000,true),("cover",9,false))) {
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
      chisel3.layer.elideBlocks(new PorPhysicalFormal(edges,bypass)),
      Array("--target-dir",s"${args(0)}/$name"),
      Array("--disable-all-randomization","--strip-debug-info",
        "--verification-flavor=immediate","--lower-to-core"))
  }
}
