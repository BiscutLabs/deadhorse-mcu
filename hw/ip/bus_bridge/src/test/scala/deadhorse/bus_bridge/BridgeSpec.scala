package deadhorse.bus_bridge

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class BridgeTest(local: Boolean=false,fault: String="") extends RawModule {
  val sc = IO(Input(Bool())); val tc = IO(Input(Bool()))
  val sn = IO(Input(Bool())); val tn = IO(Input(Bool()))
  val source = IO(new LocalBus); val target = IO(Flipped(new LocalBus))
  val offer = IO(Input(Bool())); val permit = IO(Input(Bool())); val quiet = IO(Input(Bool()))
  val ask = IO(Output(Bool())); val admit = IO(Output(Bool())); val wake = IO(Output(Bool())); val isolated = IO(Output(Bool()))
  val hold = IO(Output(Bool()))
  val d = Module(if(fault=="data") new BridgeBad(128) else new BusBridge(128))
  d.sourceClock := sc.asClock; d.targetClock := tc.asClock
  d.sourceReset_n := sn; d.targetReset_n := tn
  d.source <> source; d.target <> target
  d.offer := offer; d.quiescent := quiet
  if(local) {
    val grant=Module(new LocalPermit);grant.clk:=sc.asClock
    grant.reset_n:=chisel3.util.experimental.BoringUtils.bore(d.sourceUp)
    grant.request:=d.permitRequest;d.permit:=grant.permit
  } else d.permit:=permit
  if(fault=="drop")source.rvalid:=false.B
  if(fault=="duplicate")withClockAndReset(sc.asClock,(!sn).asAsyncReset) {
    source.rvalid:=d.source.rvalid || RegNext(d.source.rvalid,false.B)
  }
  if(fault=="stale")withClockAndReset(sc.asClock,(!sn).asAsyncReset) {
    val last=RegInit(0.U(32.W))
    when(d.source.rvalid && !d.source.err) {last:=d.source.rdata}
    // Replay the preceding successful response instead of the reset error.
    source.rdata:=Mux(d.source.err,last,d.source.rdata);source.err:=false.B
  }
  ask := d.permitRequest; admit := d.admit; wake := d.clockRequest; isolated := d.isolated
  hold := d.targetClockHold
}

class BridgeSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t14/bridge-simulation").toAbsolutePath
  }
  private def exercise(local: Boolean=false,fault: String=""): Unit = {
    simulateRaw(new BridgeTest(local,fault),subdirectory=Some(s"transactions-$local-$fault")){ d =>
      def yes(b: Bool) = b.peek().litValue == 1
      var backend: Option[(BigInt,Int)] = None
      var freezeReply = false
      var granted = 0
      d.sc.poke(false.B);d.tc.poke(false.B);d.sn.poke(true.B);d.tn.poke(true.B)
      d.source.req.poke(false.B);d.source.bits.addr.poke(0.U);d.source.bits.wdata.poke(0.U)
      d.source.bits.be.poke(0.U);d.source.bits.we.poke(false.B);d.source.bits.origin.poke(0.U)
      d.offer.poke(false.B);d.permit.poke(false.B);d.quiet.poke(true.B)
      d.target.gnt.poke(false.B);d.target.rvalid.poke(false.B);d.target.rdata.poke(0.U);d.target.err.poke(false.B)
      d.ask.peek();d.sn.poke(false.B);d.tn.poke(false.B);d.ask.peek();d.sn.poke(true.B);d.tn.poke(true.B)
      def step(s: Boolean=true,t: Boolean=true): (Boolean,Boolean,BigInt,Boolean) = {
        d.permit.poke(yes(d.ask).B)
        d.quiet.poke(backend.isEmpty.B)
        val replying=backend.exists(_._2==0) && !freezeReply
        d.target.gnt.poke(backend.isEmpty.B)
        d.target.rvalid.poke(replying.B);d.target.rdata.poke(backend.map(_._1).getOrElse(BigInt(0)).U)
        val accept=s && yes(d.source.req) && yes(d.source.gnt)
        val valid=s && yes(d.source.rvalid);val data=d.source.rdata.peek().litValue;val error=yes(d.source.err)
        val issue=t && yes(d.target.req) && yes(d.target.gnt)
        if(t){
          if(replying) backend=None
          else backend=backend.map{case(v,n)=>(v,math.max(0,n-1))}
          if(issue){
            assert(d.target.bits.addr.peek().litValue==0x1234 && d.target.bits.be.peek().litValue==5 &&
              d.target.bits.origin.peek().litValue==3,"BRIDGE_MODEL_MISMATCH request metadata")
            backend=Some((d.target.bits.wdata.peek().litValue ^ BigInt("937a2b51",16),3));granted+=1
          }
        }
        d.sc.poke(s.B);d.tc.poke(t.B);d.ask.peek();d.sc.poke(false.B);d.tc.poke(false.B);d.ask.peek()
        (accept,valid,data,error)
      }
      for(_<-0 until 20)step()
      if(local) {
        // Withdraw a speculative offer without ever presenting a transaction.
        d.offer.poke(true.B);for(_<-0 until 3)step();d.offer.poke(false.B)
        for(_<-0 until 24) {val(_,v,_,_)=step();assert(!v,"BRIDGE_MODEL_MISMATCH unsolicited response")}
        assert(granted==0,"BRIDGE_MODEL_MISMATCH withdrawn offer issued")
      }
      def transaction(value: BigInt, error: Boolean=false, stopped: Int=0, peerReset: Boolean=false): Unit = {
        val priorGrants=granted
        d.offer.poke(true.B);d.source.req.poke(true.B)
        d.source.bits.addr.poke(0x1234.U);d.source.bits.wdata.poke(value.U)
        d.source.bits.be.poke(5.U);d.source.bits.we.poke(false.B);d.source.bits.origin.poke(3.U)
        var accepted=false;var completed=false;var resets=0
        for(i<-0 until 250 if !completed){
          val(a,v,data,failed)=step(t=i>=stopped)
          if(a){assert(!accepted);accepted=true;d.source.req.poke(false.B)}
          if(accepted && peerReset && resets==0){
            // Pulse peer reset without either clock: the surviving source must remember.
            d.tn.poke(false.B);d.ask.peek();d.tn.poke(true.B);d.ask.peek();resets+=1
          }
          if(i==stopped-1)assert(yes(d.wake),"BRIDGE_MODEL_MISMATCH lost stopped-clock wake")
          if(v){
            assert(accepted,"BRIDGE_MODEL_MISMATCH response without grant")
            assert(failed==error,"BRIDGE_MODEL_MISMATCH error")
            assert(data==(if(error)BigInt(0) else value ^ BigInt("937a2b51",16)),"BRIDGE_MODEL_MISMATCH stale/data")
            completed=true;d.offer.poke(false.B)
          }
        }
        assert(completed,"BRIDGE_MODEL_MISMATCH deadline")
        for(_<-0 until 24){val(_,v,_,_)=step();assert(!v,"BRIDGE_MODEL_MISMATCH duplicate")}
        if(!error)assert(granted==priorGrants+1,"BRIDGE_MODEL_MISMATCH duplicated downstream effect")
      }
      transaction(0x91,stopped=24)
      transaction(0x19)
      transaction(0x4321,error=true,peerReset=true)
      transaction(0xabcd)
      freezeReply=true
      transaction(0x9988,error=true) // timeout after downstream acceptance
      assert(yes(d.isolated),"BRIDGE_MODEL_MISMATCH missing quarantine")
      val before=granted
      transaction(0x1177,error=true) // bounded error service; no new target operation
      assert(granted==before,"BRIDGE_MODEL_MISMATCH issued into quarantine")
      freezeReply=false
      for(_<-0 until 20)step()
      transaction(0x22dd)
      // Source reset after target grant: retained endpoint work must drain.
      freezeReply=true
      d.offer.poke(true.B);d.source.req.poke(true.B);d.source.bits.wdata.poke(0x8899.U)
      val old=granted
      for(_<-0 until 40 if granted==old){val(a,_,_,_)=step();if(a)d.source.req.poke(false.B)}
      assert(granted==old+1)
      d.sn.poke(false.B);d.ask.peek();d.offer.poke(false.B);d.source.req.poke(false.B)
      d.sn.poke(true.B);d.ask.peek()
      for(_<-0 until 20)step()
      transaction(0x77,error=true)
      freezeReply=false;for(_<-0 until 20)step()
      transaction(0x4455)
      // Reset before a newly forwarded target request can receive its grant.
      d.offer.poke(true.B);d.source.req.poke(true.B);d.source.bits.wdata.poke(0x5151.U)
      var reached=false
      for(_<-0 until 40 if !reached){val(a,_,_,_)=step();if(a)d.source.req.poke(false.B);reached=yes(d.target.req)}
      assert(reached && yes(d.hold),"BRIDGE_MODEL_MISMATCH first-request clock hold")
      d.sn.poke(false.B);d.ask.peek();d.offer.poke(false.B);d.source.req.poke(false.B)
      assert(yes(d.hold),"BRIDGE_MODEL_MISMATCH source reset lost target hold")
      d.sn.poke(true.B);d.ask.peek();for(_<-0 until 24)step()
      transaction(0x6161)
    }
  }
  test("bridge preserves payload, wakes a stopped clock, aborts timeout and rejects stale responses after reset") {exercise()}
  test("local grant preserves transport, stopped-clock wake, reset and timeout drainage") {exercise(true)}
  for((fault,message)<-Seq("data"->"stale/data","drop"->"deadline","duplicate"->"duplicate","stale"->"error"))
    test(s"local-grant oracle rejects $fault fault") {
      val error=intercept[org.scalatest.exceptions.TestFailedException] {exercise(true,fault)}
      assert(error.getMessage.contains("BRIDGE_MODEL_MISMATCH "+message))
    }
}
