package deadhorse.sram

import chisel3._
import chisel3.util._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.ResetRelease
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SramPinAbortBench(resetReplyOnPin: Boolean=false) extends RawModule {
  val main=IO(Input(Clock()));val aon=IO(Input(Clock()))
  val cold=IO(Input(Bool()));val pin=IO(Input(Bool()));val transport=IO(Input(Bool()))
  val request=IO(Flipped(Decoupled(UInt(41.W))));val response=IO(Decoupled(UInt(34.W)))
  val held=IO(Output(Bool()));val mainWrite=IO(Output(Bool()));val aonWrite=IO(Output(Bool()))
  val mr=Module(new ResetRelease);val ar=Module(new ResetRelease)
  mr.clk:=main;ar.clk:=aon;mr.reset_n:=cold;ar.reset_n:=cold
  val owner=Module(new SramBist(16,8,qualifiedResets=true))
  owner.clk:=main;owner.aonClock:=aon;owner.cold_n:=cold;owner.epoch_n:=pin
  owner.domainReset.get.main:=mr.released;owner.domainReset.get.aon:=ar.released
  owner.authorized:=true.B;owner.mainReset_n:=false.B;owner.aonReset_n:=false.B
  owner.main.result:=0.U;owner.aon.result:=0.U
  val port=Module(new SramDmi("build/t20/i1/sram/sram_regs.json"))
  port.clk:=main;port.reset_n:=mr.released && (if(resetReplyOnPin) pin else true.B)
  port.epoch_n:=owner.commandOpen;port.clear:= !transport
  port.request<>request;response<>port.response
  owner.start:=port.start;owner.keyed:=port.keyed
  port.busy:=owner.busy;port.done:=owner.done;port.failed:=owner.failed;port.rejected:=owner.rejected
  port.resetAck:=owner.resetAck;port.failAddress:=owner.failAddress;port.result:=owner.result
  held:=owner.resetHold;mainWrite:=owner.main.enable;aonWrite:=owner.aon.enable
}

class SramPinAbortSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/sram-pin-abort").toAbsolutePath
  }
  def exercise(d: SramPinAbortBench): Unit={
    def high(b: Bool)=b.peek().litToBoolean
    def step(n: Int=1,remote: Boolean=true): Unit=for(_<-0 until n) {d.main.step();if(remote)d.aon.step()}
    d.cold.poke(false.B);d.pin.poke(false.B);d.transport.poke(false.B)
    d.request.valid.poke(false.B);d.request.bits.poke(0.U);d.response.ready.poke(false.B)
    step(4);d.cold.poke(true.B);d.pin.poke(true.B);d.transport.poke(true.B);step(16)
    def offer(address: Int,write: Boolean=false): Unit={
      val bits=(BigInt(address)<<34)|(BigInt(if(write)2 else 1)<<32)|(if(write)BigInt("42535431",16) else BigInt(0))
      d.request.bits.poke(bits.U);d.request.valid.poke(true.B)
      var n=0;while(!high(d.request.ready)&&n<32){step();n+=1};assert(n<32,"PIN_DMI_GRANT")
      step();d.request.valid.poke(false.B)
    }
    def reply(): BigInt={
      var n=0;while(!high(d.response.valid)&&n<32){step();n+=1}
      assert(n<32,"PIN_DMI_REPLY_LOST");d.response.bits.peek().litValue
    }
    def consume(): Unit={d.response.ready.poke(true.B);step();d.response.ready.poke(false.B)}
    // A produced DMI response belongs to cold debug and survives pin abort,
    // including a complete pulse with both clocks stopped.
    offer(0x71);val heldReply=reply()
    d.pin.poke(false.B);d.response.valid.expect(true.B,"PIN_DMI_REPLY_LOST")
    d.pin.poke(true.B);d.response.bits.expect(heldReply.U);step(8,remote=false)
    d.response.valid.expect(true.B);step(16);consume()
    // Pin arrives after admission but before the key reaches RegBlock. The
    // transaction still replies; its destructive command cannot run later.
    offer(0x70,true);d.pin.poke(false.B)
    // Evaluate the asserted level before releasing it; adjacent buffered pokes
    // alone coalesce and do not create an asynchronous event in ChiselSim.
    d.held.expect(false.B);d.mainWrite.expect(false.B);d.aonWrite.expect(false.B)
    d.pin.poke(true.B)
    step(8,remote=false);d.held.expect(false.B);d.mainWrite.expect(false.B);d.aonWrite.expect(false.B)
    assert(reply()==0);step(16);d.held.expect(false.B,"PIN_QUEUED_KEY_REPLAY");consume()
    offer(0x70,true);assert(reply()==0);d.held.expect(true.B);consume()
    // Transport flush clears custom CSR protocol state, not accepted BIST.
    d.transport.poke(false.B);step(3);d.held.expect(true.B,"TRANSPORT_ABORTED_OWNER")
    d.transport.poke(true.B);step(3);d.held.expect(true.B)
    offer(0x71);val busy=reply();assert((busy>>2&1)==1)
    d.pin.poke(false.B);d.held.expect(false.B);d.mainWrite.expect(false.B);d.aonWrite.expect(false.B)
    d.response.valid.expect(true.B,"PIN_DMI_REPLY_LOST");d.response.bits.expect(busy.U)
    d.pin.poke(true.B);step(8,remote=false);d.held.expect(false.B)
    step(16);d.held.expect(false.B);consume()
    offer(0x71);assert((reply()>>2&7)==0,"PIN_OWNER_STATE_REPLAY");consume()
    d.cold.poke(false.B);d.response.valid.expect(false.B);d.held.expect(false.B)
  }
  test("pin-only abort preserves cold DMI replies and cancels queued keys across stopped clocks") {
    simulateRaw(new SramPinAbortBench)(exercise)
  }
  test("resetting the cold reply bank on pin abort is rejected") {
    val e=intercept[Throwable] {simulateRaw(new SramPinAbortBench(resetReplyOnPin=true))(exercise)}
    assert(Iterator.iterate(e)(_.getCause).takeWhile(_!=null)
      .exists(x=>Option(x.getMessage).exists(_.contains("PIN_DMI_REPLY_LOST"))))
  }
}
