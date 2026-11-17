package deadhorse.bus_bridge

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils
import deadhorse.lib._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class BridgeBadSource(limit:Int) extends BridgeSource(limit){override protected def readResult(value:UInt):UInt=value ^ 1.U}
class BridgeBad(limit:Int) extends BusBridge(limit){override protected def sourceEndpoint():BridgeSource=new BridgeBadSource(limit)}

/** Actual two-clock bridge with a legal delayed/error-capable untagged target. */
class BridgeFormal(variant:String) extends RawModule {
  val sc=IO(Input(Clock()));val tc=IO(Input(Clock()))
  val sn=IO(Input(Bool()));val tn=IO(Input(Bool()));val en=IO(Input(Bool()))
  val req=IO(Input(Bool()));val data=IO(Input(UInt(32.W)));val addr=IO(Input(UInt(32.W)))
  val write=IO(Input(Bool()));val be=IO(Input(UInt(4.W)))
  val allowGrant=IO(Input(Bool()));val replyNow=IO(Input(Bool()));val replyError=IO(Input(Bool()))
  val cancelEndpoint=IO(Input(Bool()));val grantPermit=IO(Input(Bool()))
  def design:BusBridge=if(variant=="corrupt")new BridgeBad(32) else new BusBridge(32)
  val d=Module(design)
  d.sourceClock:=sc;d.targetClock:=tc;d.sourceReset_n:=sn;d.targetReset_n:=tn
  d.source.req:=req;d.source.bits.addr:=addr;d.source.bits.wdata:=data;d.source.bits.we:=write
  d.source.bits.be:=be;d.source.bits.origin:=3.U
  val pending=withClockAndReset(sc,(!sn).asAsyncReset){RegInit(false.B)}
  // Observation-only taps of public production-module ports. No FSM or FIFO
  // storage/pointer state enters the oracle and no production port is added.
  val sourcePush=BoringUtils.bore(d.producer.requestPush)
  val sourceReady=BoringUtils.bore(d.producer.requestReady)
  val sourceData=BoringUtils.bore(d.producer.requestData)
  val targetLink=BoringUtils.bore(d.consumer.linkUp)
  val targetValid=BoringUtils.bore(d.consumer.requestValid)
  val targetPop=BoringUtils.bore(d.consumer.requestPop)
  val targetData=BoringUtils.bore(d.consumer.requestData)
  val targetResponsePush=BoringUtils.bore(d.consumer.responsePush)
  val targetResponseReady=BoringUtils.bore(d.consumer.responseReady)
  // Compose at actual production endpoint ports. A latest-source ticket is
  // unsound across source reset: an older target offer may survive a stopped
  // target clock while arbitrarily many newer source epochs are cancelled.
  // The separately proved 72-bit CdcFifo supplies ordering/data preservation
  // between these two checked boundaries, under arbitrary inputs and resets.
  withClockAndReset(sc,(!sn).asAsyncReset){
    val sourceCredit=RegInit(false.B);val pushed=RegInit(false.B)
    val sourcePayload=Reg(new BusPayload)
    when(d.source.rvalid){sourceCredit:=false.B}
    when(req&&d.source.gnt){sourceCredit:=true.B;pushed:=false.B;sourcePayload:=d.source.bits}
    if(variant!="cover"){
      assert(!sourcePush||sourceCredit)
      assert(!sourcePush||sourceData===sourcePayload.asUInt)
      when(sourcePush&&sourceReady){assert(!pushed)}
    }
    when(sourcePush&&sourceReady){pushed:=true.B}
  }
  withClockAndReset(tc,(!tn).asAsyncReset){
    val targetCredit=RegInit(false.B);val issued=RegInit(false.B)
    val targetPayload=Reg(new BusPayload)
    // Clear only when the target observes transport flush. A grant on that
    // same edge still consumes its pre-edge credit; the old offer is legal.
    when(!targetLink||(targetResponsePush&&targetResponseReady)){targetCredit:=false.B}
    when(targetValid&&targetPop){
      targetCredit:=true.B;issued:=false.B
      targetPayload:=targetData.asTypeOf(new BusPayload)
    }
    when(d.target.req&&d.target.gnt){
      if(variant!="cover"){
        assert(targetCredit&& !issued)
        assert(d.target.bits.asUInt===targetPayload.asUInt)
      }
      issued:=true.B
    }
  }
  d.offer:=req||pending
  val cancelSeen=withClockAndReset(sc,(!(sn&&tn)).asAsyncReset){RegInit(true.B)}
  withClockAndReset(sc,(!sn).asAsyncReset){
    val granted=RegInit(false.B)
    when(!d.permitRequest){granted:=false.B}.elsewhen(grantPermit){granted:=true.B}
    d.permit:=granted
    val held=RegNext(req&& !d.source.gnt,false.B)
    val previous=RegNext(Cat(addr,data,be,write))
    when(held){assume(req);assume(Cat(addr,data,be,write)===previous)}
    val age=RegInit(0.U(6.W));val expected=Reg(UInt(32.W))
    val warm=RegInit(0.U(3.W));when(warm=/=4.U){warm:=warm+1.U}
    val previousOffer=RegNext(d.offer,false.B)
    val cancelAge=RegInit(0.U(3.W))
    // Cancellation observed on the result-commit edge must win. A reset
    // simultaneous with publishing a response cannot retroactively revoke it.
    val cancelBeforeReply=RegNext(pending&&cancelSeen,false.B)
    when(pending){age:=age+1.U}
    when(pending&&cancelSeen){cancelAge:=cancelAge+1.U}.otherwise{cancelAge:=0.U}
    when(d.source.rvalid){pending:=false.B}
    when(req&&d.source.gnt){
      pending:=true.B;age:=1.U;expected:=Mux(write,0.U,data^addr);cancelSeen:=false.B
    }
    if(variant!="cover"){
      assert(!(req&&d.source.gnt)|| !pending)
      assert(!d.source.rvalid||pending)
      assert(!d.source.rvalid||d.source.rdata===Mux(d.source.err,0.U,expected))
      assert(!pending||age<=32.U)
      assert(!pending||d.clockRequest)
      assert(warm<4.U|| !previousOffer||d.clockRequest)
      assert(!d.source.rvalid|| !cancelBeforeReply||d.source.err)
      assert(cancelAge<4.U)
    }else{
      cover(d.source.rvalid&& !d.source.err)
      cover(d.source.rvalid&&d.source.err&&age===32.U)
      cover(d.source.rvalid&&cancelSeen)
      cover(d.source.rvalid&&d.source.err&& !cancelSeen&&age<32.U)
    }
  }
  withClockAndReset(tc,(!en).asAsyncReset){
    val active=RegInit(false.B);val value=Reg(UInt(32.W))
    d.target.gnt:=allowGrant&& !active
    d.target.rvalid:=active&&replyNow;d.target.rdata:=value;d.target.err:=replyError
    d.quiescent:= !active
    when(active&&(replyNow||cancelEndpoint)){active:=false.B}
    when(d.target.req&&d.target.gnt){active:=true.B;value:=d.target.bits.wdata^d.target.bits.addr}
    if(variant!="cover")assert(!active||d.targetClockHold)
    else{
      cover(active&& !sn)
      cover(active&&d.isolated&&replyNow)
    }
  }
}

object EmitBridgeFormal {
  def main(args:Array[String]):Unit={
    require(args.length==1);val root=Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for(v<-Seq("correct","corrupt","cover")){
      val dir=root.resolve(v);Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new BridgeFormal(v)),Array("--target-dir",dir.toString),
        Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
    }
  }
}
