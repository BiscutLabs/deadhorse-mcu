package deadhorse.usb

import chisel3._
import chisel3.util._
import deadhorse.lib.ResetRelease

class UsbEarlyBufferValid extends UsbInBuffer(true) {
  override protected def offer(value: Bool): Bool=true.B
}

/** Independent transport-reset release while the production cadence runs.
  * Only qualified observations require initialized RAM read stages. The
  * original common-reset packet assertions below remain unchanged.
  */
class UsbBufferResetFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val transportReset_n=IO(Input(Bool()));val data=IO(Input(UInt(8.W)))
  val push=IO(Input(Bool()));val ready=IO(Input(Bool()))
  val operation=IO(Input(UInt(2.W)));val receiveOperation=IO(Input(UInt(2.W)))
  val cadence=Module(new UsbBitEnable);cadence.clk:=clock;cadence.reset_n:=reset_n
  val release=Module(new ResetRelease);release.clk:=clock
  release.reset_n:=reset_n && transportReset_n
  val in=Module(if(variant=="corrupt") new UsbEarlyBufferValid else new UsbInBuffer(true))
  val out=Module(new UsbOutBuffer(true))
  in.proofMemory.get:=0.U.asTypeOf(new UsbMemoryProofInputs)
  out.proofMemory.get:=0.U.asTypeOf(new UsbMemoryProofInputs)
  in.clk:=clock;out.clk:=clock;in.reset_n:=release.released;out.reset_n:=release.released
  in.bitEnable:=cadence.enable;out.bitEnable:=cadence.enable
  in.appData:=data;in.appValid:=push;out.appReady:=ready;out.received:=data
  in.request:=operation===2.U;in.acknowledge:=operation===3.U
  in.consume:=(operation===1.U && in.valid) || operation===2.U || operation===3.U
  out.receiveReady:=receiveOperation=/=0.U
  out.receiveValid:=receiveOperation===1.U;out.receiveError:=receiveOperation===3.U
  withClockAndReset(clock,(!release.released).asAsyncReset) {
    val age=RegInit(0.U(2.W));when(age=/=3.U){age:=age+1.U}
    val previousHead=RegNext(out.proof.get.head,0.U)
    val previousCapture=RegNext(out.proof.get.capture,false.B)
    if(variant!="cover") {
      when(release.released && cadence.enable && in.valid){assert(age===3.U)}
      when(release.released && out.proof.get.capture){assert(age===3.U)}
      when(release.released){assert(previousCapture===(out.proof.get.head=/=previousHead))}
    }
  }
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val phase=RegInit(0.U(2.W));phase:=phase+1.U
    val priorReleased=RegNext(release.released,false.B)
    val seenRelease=RegInit(false.B);when(release.released){seenRelease:=true.B}
    val seenResetAgain=RegInit(false.B)
    when(seenRelease && !release.released){seenResetAgain:=true.B}
    if(variant=="cover") {
      for(p<-0 until 4){cover(release.released && !priorReleased && phase===p.U)}
      cover(seenRelease && !release.released)
      cover(seenResetAgain && release.released && cadence.enable && in.valid)
      cover(seenResetAgain && release.released && out.proof.get.capture)
    }
  }
}

class UsbMissingCommit(proofView: Boolean=false, packetBytes: Int=UsbPacketSizing.bulkMaxPacketBytes) extends UsbInBuffer(proofView,packetBytes=packetBytes) {
  override protected def commit(head: UInt,speculative: UInt): UInt=head
}
class UsbWithheldValid(proofView: Boolean=false, packetBytes: Int=UsbPacketSizing.bulkMaxPacketBytes) extends UsbInBuffer(proofView,packetBytes=packetBytes) {
  override protected def offer(value: Bool): Bool=false.B
}

/** Symbolically select one accepted application byte. Track its logical queue
  * position through speculative reads, replay and ACK; never inspect DUT RAM
  * or pointers. Arbitrary selection proves integrity at every queue position.
  */
class UsbInFormal(variant: String,lane: Option[Int]=None,helpers: Boolean=false,sparse: Boolean=false,packetBytes: Int=UsbPacketSizing.bulkMaxPacketBytes) extends RawModule {
  private val g=UsbPacketGeometry(packetBytes)
  def same(a: UInt,b: UInt): Bool=lane.map(i=>a(i)===b(i)).getOrElse(a===b)
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val data=IO(Input(UInt(8.W)));val push=IO(Input(Bool()));val choose=IO(Input(Bool()))
  val operation=IO(Input(UInt(2.W))) // idle, read byte, new IN request, qualified ACK
  val cadence=Module(new UsbBitEnable);cadence.clk:=clock;cadence.reset_n:=reset_n
  require(!sparse || (helpers && variant=="correct"))
  val forgotten=if(sparse) Some(IO(Input(UInt(8.W)))) else None
  val d=Module(if(variant=="corrupt") new UsbMissingCommit(helpers,packetBytes) else if(variant=="withheld") new UsbWithheldValid(helpers,packetBytes) else new UsbInBuffer(helpers,n=>if(sparse) new UsbSparsePacketMemory(n) else new UsbPacketMemory(n),packetBytes))
  d.proofMemory.foreach(_:=0.U.asTypeOf(new UsbMemoryProofInputs(packetBytes)))
  d.clk:=clock;d.reset_n:=reset_n;d.bitEnable:=cadence.enable;d.appData:=data;d.appValid:=push
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val queued=RegInit(0.U(g.pointerBits.W));val offset=RegInit(0.U(g.pointerBits.W))
    val selected=RegInit(false.B);val watching=RegInit(false.B)
    val watched=Reg(UInt(8.W));val position=RegInit(0.U(g.pointerBits.W));val seen=RegInit(false.B)
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
    val slot=if(helpers) Some(Reg(UInt(g.pointerBits.W))) else None
    slot.foreach(s=>when(put && choose && !selected){s:=d.proof.get.tail})
    if(sparse) {
      d.proofMemory.get.track:=selected;d.proofMemory.get.trackAddress:=slot.get;d.proofMemory.get.forgotten:=forgotten.get
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
      if(helpers) {
        val memoryAge=RegInit(0.U(2.W));when(memoryAge=/=3.U){memoryAge:=memoryAge+1.U}
        assert(!cadence.enable || memoryAge===3.U)
        val p=d.proof.get
        def distance(a:UInt,b:UInt):UInt=Mux(b>=a,b-a,g.slots.U((g.pointerBits+1).W)+b-a)
        assert(p.head<=packetBytes.U && p.tail<=packetBytes.U && p.speculative<=packetBytes.U && p.visibleTail<=packetBytes.U)
        assert(!p.stagingVisible || p.stagingValid)
        assert(!d.appReady || !p.stagingValid)
        assert(queued===distance(p.head,p.tail)+p.stagingValid.asUInt)
        assert(offset===distance(p.head,p.speculative))
        assert(distance(p.head,p.speculative)<=distance(p.head,p.visibleTail))
        assert(distance(p.head,p.visibleTail)<=distance(p.head,p.tail))
        assert(!watching || position<queued)
        assert(!watching || position===distance(p.head,slot.get))
        assert(!watching || selected)
        when(selected){assert(slot.get<=packetBytes.U)}
        if(sparse) {
          val ram=d.proofRam.get
          when(watching && p.stagingValid && p.tail===slot.get){assert(p.stagingData===watched)}
          when(watching && ram.pendingWrite && ram.pendingAddress===slot.get){assert(ram.pendingData===watched)}
          when(watching && ram.trackedValid){assert(ram.trackedValue===watched)}
          when(watching && position<distance(p.head,p.tail)) {
            assert((ram.pendingWrite && ram.pendingAddress===slot.get) || ram.trackedValid)
          }
          when(cadence.enable && watching && position<distance(p.head,p.tail)) {
            assert(ram.trackedValid && ram.trackedValue===watched)
          }
          val tag=RegNext(RegNext(RegNext(p.speculative)))
          when(cadence.enable){assert(tag===p.speculative)}
          val stageSeen=RegNext(watching && ram.trackedValid && ram.query===slot.get,false.B)
          val outputSeen=RegNext(stageSeen,false.B)
          when(stageSeen){assert(ram.stage===watched)}
          when(outputSeen){assert(ram.output===watched)}
        }
      }
      assert(queued<=g.slots.U)
      when(take){assert(offset<queued)}
      when(matchPosition){assert(same(d.data,watched))}
      when(cadence.enable && priorValid && priorIdle){assert(d.valid);assert(same(d.data,priorData))}
      when(service===1.U){assert(d.valid)}
    }
  }
}

class UsbMissingPublish(proofView: Boolean=false, packetBytes: Int=UsbPacketSizing.bulkMaxPacketBytes) extends UsbOutBuffer(proofView,packetBytes=packetBytes) {
  override protected def publish(committed: UInt,speculative: UInt): UInt=committed
}

/** OUT oracle tracks packet commit/rollback and one symbolic byte selected at
  * the packet input. A packet is at most the configured bulk MPS.
  */
class UsbOutFormal(variant: String,lane: Option[Int]=None,helpers: Boolean=false,sparse: Boolean=false,ownership: Boolean=false,packetBytes: Int=UsbPacketSizing.bulkMaxPacketBytes) extends RawModule {
  private val g=UsbPacketGeometry(packetBytes)
  def same(a: UInt,b: UInt): Bool=lane.map(i=>a(i)===b(i)).getOrElse(a===b)
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val data=IO(Input(UInt(8.W)));val operation=IO(Input(UInt(2.W)))
  val choose=IO(Input(Bool()));val ready=IO(Input(Bool()))
  val cadence=Module(new UsbBitEnable);cadence.clk:=clock;cadence.reset_n:=reset_n
  require(!sparse || (helpers && variant=="correct"))
  val forgotten=if(sparse) Some(IO(Input(UInt(8.W)))) else None
  val d=Module(if(variant=="corrupt") new UsbMissingPublish(helpers,packetBytes) else new UsbOutBuffer(helpers,n=>if(sparse) new UsbSparsePacketMemory(n) else new UsbPacketMemory(n),packetBytes))
  d.proofMemory.foreach(_:=0.U.asTypeOf(new UsbMemoryProofInputs(packetBytes)))
  d.clk:=clock;d.reset_n:=reset_n;d.bitEnable:=cadence.enable;d.received:=data;d.appReady:=ready
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    // Retain overflow in the independent oracle: capacity + a wrongly committed
    // maximum packet must not wrap below the unchanged capacity assertion.
    val queued=RegInit(0.U((g.pointerBits+1).W));val packet=RegInit(0.U(g.pointerBits.W))
    val selected=RegInit(false.B);val watching=RegInit(false.B);val inPacket=RegInit(false.B)
    val watched=Reg(UInt(8.W));val position=RegInit(0.U((g.pointerBits+1).W))
    d.receiveReady:=operation=/=0.U
    d.receiveValid:=operation===1.U && packet<packetBytes.U
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
    val slot=if(helpers) Some(Reg(UInt(g.pointerBits.W))) else None
    slot.foreach(s=>when(put && choose && !selected){s:=d.proof.get.speculative})
    if(sparse) {
      d.proofMemory.get.track:=selected;d.proofMemory.get.trackAddress:=slot.get;d.proofMemory.get.forgotten:=forgotten.get
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
      if(helpers) {
        val memoryAge=RegInit(0.U(2.W));when(memoryAge=/=3.U){memoryAge:=memoryAge+1.U}
        assert(!cadence.enable || memoryAge===3.U)
        val p=d.proof.get
        def distance(a:UInt,b:UInt):UInt=Mux(b>=a,b-a,g.slots.U((g.pointerBits+1).W)+b-a)
        assert(p.head<=packetBytes.U && p.tail<=packetBytes.U && p.speculative<=packetBytes.U)
        assert(queued===distance(p.head,p.tail)+d.appValid.asUInt)
        assert(p.reject || packet===distance(p.tail,p.speculative))
        assert(!watching || inPacket || position<queued)
        if(ownership){assert(!(watching && inPacket) || position<(queued+&packet))}
        when(watching && (!inPacket || !p.reject) && (inPacket || position=/=0.U || !d.appValid)) {
          assert(position===distance(p.head,slot.get)+d.appValid.asUInt)
        }
        assert(!watching || selected)
        when(selected){assert(slot.get<=packetBytes.U)}
        if(sparse) {
          val ram=d.proofRam.get
          val owned=watching && (!inPacket || !p.reject) && !(position===0.U && d.appValid)
          when(owned && ram.pendingWrite && ram.pendingAddress===slot.get){assert(ram.pendingData===watched)}
          when(owned && ram.trackedValid){assert(ram.trackedValue===watched)}
          when(owned){assert((ram.pendingWrite && ram.pendingAddress===slot.get) || ram.trackedValid)}
          when(cadence.enable && watching && (!inPacket || !p.reject) && !(position===0.U && d.appValid)) {
            assert(ram.trackedValid && ram.trackedValue===watched)
          }
          val tag=RegNext(RegNext(RegNext(p.head)))
          when(cadence.enable){assert(tag===p.head)}
          val stageSeen=RegNext(watching && ram.trackedValid && ram.query===slot.get,false.B)
          val outputSeen=RegNext(stageSeen,false.B)
          when(stageSeen){assert(ram.stage===watched)}
          when(outputSeen){assert(ram.output===watched)}
        }
      }
      assert(queued<=g.slots.U)
      when(d.appValid){assert(queued=/=0.U)}
      when(d.appValid && watching && position===0.U){assert(same(d.appData,watched))}
      when(held){assert(d.appValid);assert(same(d.appData,oldData))}
      assert(waitForData<8.U)
    }
  }
}
