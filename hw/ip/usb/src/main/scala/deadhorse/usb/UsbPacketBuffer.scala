// SPDX-License-Identifier: MIT
// Single-clock adaptation of ulixxe USB FIFOs; upstream provenance/license in hw/vendor/usb.
package deadhorse.usb

import chisel3._
import chisel3.util._

/** Registered banked packet RAM. All three read stages complete between bit-enable
  * edges; no combinationally addressed storage larger than eight words.
  */
class UsbMemoryProofInputs(packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends Bundle {
  val track=Bool();val trackAddress=UInt(UsbPacketGeometry(packetBytes).pointerBits.W);val forgotten=UInt(8.W)
}
class UsbMemoryProofState(packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends Bundle {
  private val bits=UsbPacketGeometry(packetBytes).pointerBits
  val trackedValid=Bool();val trackedValue=UInt(8.W);val query=UInt(bits.W)
  val stage=UInt(8.W);val output=UInt(8.W)
  val pendingWrite=Bool();val pendingAddress=UInt(bits.W);val pendingData=UInt(8.W)
}
abstract class UsbPacketMemoryPort(packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes, sparseInterface: Boolean=false) extends RawModule {
  val geometry=UsbPacketGeometry(packetBytes)
  val proof=if(sparseInterface) Some(IO(Input(new UsbMemoryProofInputs(packetBytes)))) else None
  val observed=if(sparseInterface) Some(IO(Output(new UsbMemoryProofState(packetBytes)))) else None
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val write = IO(Input(Bool())); val writeAddress = IO(Input(UInt(geometry.pointerBits.W)))
  val writeData = IO(Input(UInt(8.W))); val readAddress = IO(Input(UInt(geometry.pointerBits.W)))
  val readData = IO(Output(UInt(8.W)))
}
class UsbPacketMemory(packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends UsbPacketMemoryPort(packetBytes) {
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val banks = Seq.fill(geometry.banks)(SyncReadMem(geometry.bankWords, UInt(8.W)))
    val wordAddress = RegNext(writeAddress(geometry.wordBits-1,0))
    val wordData = RegNext(writeData)
    val words = banks.zipWithIndex.map { case (memory, bank) =>
      val writeBank = RegNext(write && writeAddress(geometry.pointerBits-1,geometry.wordBits) === bank.U,false.B)
      when(writeBank && reset_n) { memory.write(wordAddress,wordData) }
      RegNext(memory.read(readAddress(geometry.wordBits-1,0), true.B))
    }
    val selection = RegNext(RegNext(readAddress(geometry.pointerBits-1,geometry.wordBits)))
    readData := RegNext(Mux(selection < geometry.banks.U, VecInit(words)(selection), 0.U))
  }
}

/** USB IN queue: ACK commits consumption; a new IN token replays unacked data. */
class UsbInProofState(packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends Bundle {
  private val bits=UsbPacketGeometry(packetBytes).pointerBits
  val head=UInt(bits.W);val tail=UInt(bits.W);val speculative=UInt(bits.W);val visibleTail=UInt(bits.W)
  val stagingValid=Bool();val stagingVisible=Bool();val pending=Bool()
  val stagingData=UInt(8.W)
}
class UsbInBuffer(proofView: Boolean=false, memoryFactory: Int=>UsbPacketMemoryPort=n=>new UsbPacketMemory(n),
                  packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends RawModule {
  private val geometry=UsbPacketGeometry(packetBytes)
  val proof=if(proofView) Some(IO(Output(new UsbInProofState(packetBytes)))) else None
  val proofMemory=if(proofView) Some(IO(Input(new UsbMemoryProofInputs(packetBytes)))) else None
  val proofRam=if(proofView) Some(IO(Output(new UsbMemoryProofState(packetBytes)))) else None
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool())); val bitEnable = IO(Input(Bool()))
  val appData = IO(Input(UInt(8.W))); val appValid = IO(Input(Bool())); val appReady = IO(Output(Bool()))
  val request = IO(Input(Bool())); val acknowledge = IO(Input(Bool())); val consume = IO(Input(Bool()))
  val data = IO(Output(UInt(8.W))); val valid = IO(Output(Bool())); val empty = IO(Output(Bool()))
  protected def commit(head: UInt, speculative: UInt): UInt = speculative
  protected def offer(value: Bool): Bool = value
  protected def retainPacket(pending: Bool): Bool = pending
  val memory = Module(memoryFactory(packetBytes)); memory.clk := clk; memory.reset_n := reset_n
  memory.proof.foreach(_:=proofMemory.get)
  proofRam.foreach(_:=0.U.asTypeOf(new UsbMemoryProofState(packetBytes)))
  memory.observed.foreach(s=>proofRam.get:=s)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    def advance(pointer: UInt): UInt = Mux(pointer === packetBytes.U,0.U,pointer + 1.U)
    val head = RegInit(0.U(geometry.pointerBits.W)); val speculative = RegInit(0.U(geometry.pointerBits.W))
    val tail = RegInit(0.U(geometry.pointerBits.W)); val visibleTail = RegInit(0.U(geometry.pointerBits.W))
    val pending = RegInit(false.B)
    val stagingData = RegInit(0.U(8.W)); val stagingValid = RegInit(false.B)
    val stagingVisible = RegInit(false.B); val ready = RegInit(false.B)
    proof.foreach { p=>p.head:=head;p.tail:=tail;p.speculative:=speculative;p.visibleTail:=visibleTail
      p.stagingValid:=stagingValid;p.stagingVisible:=stagingVisible;p.stagingData:=stagingData;p.pending:=pending }
    val nextTail = RegNext(advance(tail),1.U)
    val nextSpeculative = RegNext(advance(speculative),1.U)
    val full = RegNext(head === nextTail,false.B)
    memory.readAddress := speculative; memory.writeAddress := tail; memory.writeData := stagingData
    memory.write := bitEnable && !full && stagingVisible && reset_n
    appReady := ready
    valid := offer(RegNext(speculative =/= visibleTail,false.B))
    data := memory.readData
    empty := RegNext(head === tail && !stagingVisible && !stagingValid,true.B)
    when(bitEnable) {
      when(consume) {
        when(request) {
          speculative := head
          when(!retainPacket(pending)) {
            // Include a same-edge RAM write in the first offer, then keep
            // that packet immutable across retries and later app writes.
            val boundary = Mux(!full && stagingVisible,nextTail,tail)
            visibleTail := boundary
            pending := boundary =/= head
          }
        }
          .elsewhen(acknowledge) { head := commit(head,speculative); pending := false.B }
          .otherwise { speculative := nextSpeculative }
      }
      stagingVisible := stagingValid
      when(!full && stagingVisible) {
        tail := nextTail; stagingValid := false.B; stagingVisible := false.B; ready := true.B
      }
    }
    when(!stagingValid) { ready := true.B }
    when(appValid && ready) {
      stagingData := appData; stagingValid := true.B; ready := false.B
      when(bitEnable) { stagingVisible := true.B }
    }
  }
}

/** USB OUT queue: bad CRC/overflow rolls back all speculative packet bytes. */
class UsbOutProofState(packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends Bundle {
  private val bits=UsbPacketGeometry(packetBytes).pointerBits
  val head=UInt(bits.W);val tail=UInt(bits.W);val speculative=UInt(bits.W);val reject=Bool()
  val capture=Bool()
}
class UsbOutBuffer(proofView: Boolean=false, memoryFactory: Int=>UsbPacketMemoryPort=n=>new UsbPacketMemory(n),
                   packetBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends RawModule {
  private val geometry=UsbPacketGeometry(packetBytes)
  val proof=if(proofView) Some(IO(Output(new UsbOutProofState(packetBytes)))) else None
  val proofMemory=if(proofView) Some(IO(Input(new UsbMemoryProofInputs(packetBytes)))) else None
  val proofRam=if(proofView) Some(IO(Output(new UsbMemoryProofState(packetBytes)))) else None
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool())); val bitEnable = IO(Input(Bool()))
  val received = IO(Input(UInt(8.W))); val receiveValid = IO(Input(Bool()))
  val receiveError = IO(Input(Bool())); val receiveReady = IO(Input(Bool()))
  val nak = IO(Output(Bool())); val appReady = IO(Input(Bool()))
  val appData = IO(Output(UInt(8.W))); val appValid = IO(Output(Bool())); val empty = IO(Output(Bool()))
  protected def publish(committed: UInt, speculative: UInt): UInt = speculative
  val memory = Module(memoryFactory(packetBytes)); memory.clk := clk; memory.reset_n := reset_n
  memory.proof.foreach(_:=proofMemory.get)
  proofRam.foreach(_:=0.U.asTypeOf(new UsbMemoryProofState(packetBytes)))
  memory.observed.foreach(s=>proofRam.get:=s)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    def advance(pointer: UInt): UInt = Mux(pointer === packetBytes.U,0.U,pointer + 1.U)
    val head = RegInit(0.U(geometry.pointerBits.W)); val tail = RegInit(0.U(geometry.pointerBits.W)); val speculative = RegInit(0.U(geometry.pointerBits.W))
    val reject = RegInit(false.B); val valid = RegInit(false.B); val value = RegInit(0.U(8.W))
    proof.foreach { p=>p.head:=head;p.tail:=tail;p.speculative:=speculative;p.reject:=reject }
    val nextSpeculative = RegNext(advance(speculative),1.U)
    val nextHead = RegNext(advance(head),1.U)
    val full = RegNext(head === nextSpeculative,false.B)
    val available = RegNext(head =/= tail,false.B)
    proof.foreach(_.capture:=bitEnable && available && (!valid || appReady))
    memory.readAddress := head; memory.writeAddress := speculative; memory.writeData := received
    memory.write := bitEnable && receiveReady && receiveValid && !receiveError && !full && !reject && reset_n
    nak := reject; appData := value; appValid := valid
    empty := RegNext(head === tail && !valid,true.B)
    when(appReady && valid) { valid := false.B }
    when(bitEnable) {
      when(receiveReady) {
        when(receiveError) { speculative := tail; reject := false.B }
          .elsewhen(!receiveValid) {
            when(reject) { speculative := tail }.otherwise { tail := publish(tail,speculative) }
            reject := false.B
          }.elsewhen(full || reject) { reject := true.B }
          .otherwise { speculative := nextSpeculative; reject := false.B }
      }
      when(available && (!valid || appReady)) {
        value := memory.readData; valid := true.B; head := nextHead
      }
    }
  }
}
