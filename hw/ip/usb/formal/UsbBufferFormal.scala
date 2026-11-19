package deadhorse.usb

import chisel3._
import chisel3.util._

class UsbMissingCommit extends UsbInBuffer {
  override protected def commit(head: UInt,speculative: UInt): UInt=head
}
class UsbWithheldValid extends UsbInBuffer {
  override protected def offer(value: Bool): Bool=false.B
}

/** Symbolically select one accepted application byte. Track its logical queue
  * position through speculative reads, replay and ACK; never inspect DUT RAM
  * or pointers. Arbitrary selection proves integrity at every queue position.
  */
class UsbInFormal(variant: String,lane: Option[Int]=None) extends RawModule {
  def same(a: UInt,b: UInt): Bool=lane.map(i=>a(i)===b(i)).getOrElse(a===b)
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val data=IO(Input(UInt(8.W)));val push=IO(Input(Bool()));val choose=IO(Input(Bool()))
  val operation=IO(Input(UInt(2.W))) // idle, read byte, new IN request, qualified ACK
  val cadence=Module(new UsbBitEnable);cadence.clk:=clock;cadence.reset_n:=reset_n
  val d=Module(if(variant=="corrupt") new UsbMissingCommit else if(variant=="withheld") new UsbWithheldValid else new UsbInBuffer)
  d.clk:=clock;d.reset_n:=reset_n;d.bitEnable:=cadence.enable;d.appData:=data;d.appValid:=push
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val queued=RegInit(0.U(7.W));val offset=RegInit(0.U(7.W))
    val selected=RegInit(false.B);val watching=RegInit(false.B)
    val watched=Reg(UInt(8.W));val position=RegInit(0.U(7.W));val seen=RegInit(false.B)
    val read=operation===1.U && d.valid
    val request=operation===2.U
    val ack=operation===3.U && offset=/=0.U
    d.consume:=read || request || ack;d.request:=request;d.acknowledge:=ack
    val put=push && d.appReady
    val take=cadence.enable && read
    val commit=cadence.enable && ack
    val removed=Mux(commit,offset,0.U)
    queued:=queued+put.asUInt-removed
    when(cadence.enable) {
      when(request || ack) {offset:=0.U}.elsewhen(read) {offset:=offset+1.U}
    }
    when(commit && watching) {
      when(position<offset) {watching:=false.B}.otherwise {position:=position-offset}
    }
    when(put && choose && !selected) {
      selected:=true.B;watching:=true.B;watched:=data;position:=queued-removed
    }
    val matchPosition=take && watching && position===offset
    when(matchPosition) {seen:=true.B}
    val priorValid=RegInit(false.B);val priorData=Reg(UInt(8.W));val priorIdle=RegInit(false.B)
    // A newly accepted staging byte may miss the current IN token. Once the
    // unACKed queue has remained nonempty for twelve sample edges, a new IN
    // request must expose a byte by the following protocol edge (four samples).
    val age=RegInit(0.U(4.W));val service=RegInit(0.U(3.W))
    when(queued===0.U || commit){age:=0.U}.elsewhen(age=/=15.U){age:=age+1.U}
    when(service=/=0.U){service:=service-1.U}
    when(cadence.enable && request && queued=/=0.U && age>=12.U){service:=4.U}
    when(cadence.enable) {
      priorValid:=d.valid;priorData:=d.data;priorIdle:= !d.consume
    }
    if(variant=="cover") {
      cover(matchPosition)
      cover(matchPosition && seen)
      cover(commit && watching && position<offset)
      cover(service===1.U && d.valid)
    } else {
      assert(queued<=65.U)
      when(take){assert(offset<queued)}
      when(matchPosition){assert(same(d.data,watched))}
      when(cadence.enable && priorValid && priorIdle){assert(d.valid);assert(same(d.data,priorData))}
      when(service===1.U){assert(d.valid)}
    }
  }
}

class UsbMissingPublish extends UsbOutBuffer {
  override protected def publish(committed: UInt,speculative: UInt): UInt=committed
}

/** OUT oracle tracks packet commit/rollback and one symbolic byte selected at
  * the packet input. A packet is at most the public 64-byte bulk MPS.
  */
class UsbOutFormal(variant: String,lane: Option[Int]=None) extends RawModule {
  def same(a: UInt,b: UInt): Bool=lane.map(i=>a(i)===b(i)).getOrElse(a===b)
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val data=IO(Input(UInt(8.W)));val operation=IO(Input(UInt(2.W)))
  val choose=IO(Input(Bool()));val ready=IO(Input(Bool()))
  val cadence=Module(new UsbBitEnable);cadence.clk:=clock;cadence.reset_n:=reset_n
  val d=Module(if(variant=="corrupt") new UsbMissingPublish else new UsbOutBuffer)
  d.clk:=clock;d.reset_n:=reset_n;d.bitEnable:=cadence.enable;d.received:=data;d.appReady:=ready
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val queued=RegInit(0.U(7.W));val packet=RegInit(0.U(7.W))
    val selected=RegInit(false.B);val watching=RegInit(false.B);val inPacket=RegInit(false.B)
    val watched=Reg(UInt(8.W));val position=RegInit(0.U(8.W))
    d.receiveReady:=operation=/=0.U
    d.receiveValid:=operation===1.U && packet<64.U
    d.receiveError:=operation===3.U
    val put=cadence.enable && d.receiveReady && d.receiveValid && !d.receiveError
    val end=cadence.enable && d.receiveReady && (!d.receiveValid || d.receiveError)
    val commit=end && !d.receiveError && !d.nak
    val take=d.appValid && ready
    queued:=queued+Mux(commit,packet,0.U)-take.asUInt
    when(end){packet:=0.U}.elsewhen(put){packet:=packet+1.U}
    when(take && watching){position:=position-1.U;when(position===0.U){watching:=false.B}}
    when(end && watching && inPacket){inPacket:=false.B;when(!commit){watching:=false.B}}
    when(put && choose && !selected){
      selected:=true.B;watching:=true.B;inPacket:=true.B;watched:=data
      position:=queued+&packet-take.asUInt
    }
    val held=RegNext(d.appValid && !ready,false.B);val oldData=RegNext(d.appData)
    // Bounded progress in running application edges: after a committed byte,
    // the next four-edge read opportunity plus three RAM stages fit in eight.
    val waitForData=RegInit(0.U(4.W))
    when(queued=/=0.U && !d.appValid){waitForData:=waitForData+1.U}.otherwise{waitForData:=0.U}
    if(variant=="cover") {
      cover(take && watching && position===0.U)
      cover(end && d.receiveError && watching && inPacket)
      cover(held && take)
    } else {
      assert(queued<=65.U)
      when(d.appValid){assert(queued=/=0.U)}
      when(d.appValid && watching && position===0.U){assert(same(d.appData,watched))}
      when(held){assert(d.appValid);assert(same(d.appData,oldData))}
      assert(waitForData<8.U)
    }
  }
}
