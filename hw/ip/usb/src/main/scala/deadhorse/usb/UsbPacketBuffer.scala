// SPDX-License-Identifier: MIT
// Single-clock adaptation of ulixxe USB FIFOs; upstream provenance/license in hw/vendor/usb.
package deadhorse.usb

import chisel3._
import chisel3.util._

/** Registered banked packet RAM. All three read stages complete between bit-enable
  * edges; no combinationally addressed storage larger than eight words.
  */
class UsbMemoryProofInputs extends Bundle {
  val track=Bool();val trackAddress=UInt(7.W);val forgotten=UInt(8.W)
}
class UsbMemoryProofState extends Bundle {
  val trackedValid=Bool();val trackedValue=UInt(8.W);val query=UInt(7.W)
  val stage=UInt(8.W);val output=UInt(8.W)
  val pendingWrite=Bool();val pendingAddress=UInt(7.W);val pendingData=UInt(8.W)
}
abstract class UsbPacketMemoryPort(sparseInterface: Boolean=false) extends RawModule {
  val proof=if(sparseInterface) Some(IO(Input(new UsbMemoryProofInputs))) else None
  val observed=if(sparseInterface) Some(IO(Output(new UsbMemoryProofState))) else None
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val write = IO(Input(Bool())); val writeAddress = IO(Input(UInt(7.W)))
  val writeData = IO(Input(UInt(8.W))); val readAddress = IO(Input(UInt(7.W)))
  val readData = IO(Output(UInt(8.W)))
}
class UsbPacketMemory extends UsbPacketMemoryPort {
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val banks = Seq.fill(9)(SyncReadMem(8, UInt(8.W)))
    val wordAddress = RegNext(writeAddress(2,0))
    val wordData = RegNext(writeData)
    val words = banks.zipWithIndex.map { case (memory, bank) =>
      val writeBank = RegNext(write && writeAddress(6,3) === bank.U,false.B)
      when(writeBank && reset_n) { memory.write(wordAddress,wordData) }
      RegNext(memory.read(readAddress(2,0), true.B))
    }
    val selection = RegNext(RegNext(readAddress(6,3)))
    readData := RegNext(Mux(selection < 9.U, VecInit(words)(selection), 0.U))
  }
}

/** USB IN queue: ACK commits consumption; a new IN token replays unacked data. */
class UsbInProofState extends Bundle {
  val head=UInt(7.W);val tail=UInt(7.W);val speculative=UInt(7.W);val visibleTail=UInt(7.W)
  val stagingValid=Bool();val stagingVisible=Bool()
  val stagingData=UInt(8.W)
}
class UsbInBuffer(proofView: Boolean=false, memoryFactory: ()=>UsbPacketMemoryPort=()=>new UsbPacketMemory) extends RawModule {
  val proof=if(proofView) Some(IO(Output(new UsbInProofState))) else None
  val proofMemory=if(proofView) Some(IO(Input(new UsbMemoryProofInputs))) else None
  val proofRam=if(proofView) Some(IO(Output(new UsbMemoryProofState))) else None
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool())); val bitEnable = IO(Input(Bool()))
  val appData = IO(Input(UInt(8.W))); val appValid = IO(Input(Bool())); val appReady = IO(Output(Bool()))
  val request = IO(Input(Bool())); val acknowledge = IO(Input(Bool())); val consume = IO(Input(Bool()))
  val data = IO(Output(UInt(8.W))); val valid = IO(Output(Bool())); val empty = IO(Output(Bool()))
  protected def commit(head: UInt, speculative: UInt): UInt = speculative
  protected def offer(value: Bool): Bool = value
  val memory = Module(memoryFactory()); memory.clk := clk; memory.reset_n := reset_n
  memory.proof.foreach(_:=proofMemory.get)
  proofRam.foreach(_:=0.U.asTypeOf(new UsbMemoryProofState))
  memory.observed.foreach(s=>proofRam.get:=s)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    def advance(pointer: UInt): UInt = Mux(pointer === 64.U,0.U,pointer + 1.U)
    val head = RegInit(0.U(7.W)); val speculative = RegInit(0.U(7.W))
    val tail = RegInit(0.U(7.W)); val visibleTail = RegInit(0.U(7.W))
    val stagingData = RegInit(0.U(8.W)); val stagingValid = RegInit(false.B)
    val stagingVisible = RegInit(false.B); val ready = RegInit(false.B)
    proof.foreach { p=>p.head:=head;p.tail:=tail;p.speculative:=speculative;p.visibleTail:=visibleTail
      p.stagingValid:=stagingValid;p.stagingVisible:=stagingVisible;p.stagingData:=stagingData }
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
        when(request) { speculative := head }
          .elsewhen(acknowledge) { head := commit(head,speculative) }
          .otherwise { speculative := nextSpeculative }
        visibleTail := tail
      }
      stagingVisible := stagingValid
      when(!full && stagingVisible) {
        tail := nextTail; stagingValid := false.B; stagingVisible := false.B; ready := true.B
        when(consume) { visibleTail := nextTail }
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
class UsbOutProofState extends Bundle {
  val head=UInt(7.W);val tail=UInt(7.W);val speculative=UInt(7.W);val reject=Bool()
}
class UsbOutBuffer(proofView: Boolean=false, memoryFactory: ()=>UsbPacketMemoryPort=()=>new UsbPacketMemory) extends RawModule {
  val proof=if(proofView) Some(IO(Output(new UsbOutProofState))) else None
  val proofMemory=if(proofView) Some(IO(Input(new UsbMemoryProofInputs))) else None
  val proofRam=if(proofView) Some(IO(Output(new UsbMemoryProofState))) else None
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool())); val bitEnable = IO(Input(Bool()))
  val received = IO(Input(UInt(8.W))); val receiveValid = IO(Input(Bool()))
  val receiveError = IO(Input(Bool())); val receiveReady = IO(Input(Bool()))
  val nak = IO(Output(Bool())); val appReady = IO(Input(Bool()))
  val appData = IO(Output(UInt(8.W))); val appValid = IO(Output(Bool())); val empty = IO(Output(Bool()))
  protected def publish(committed: UInt, speculative: UInt): UInt = speculative
  val memory = Module(memoryFactory()); memory.clk := clk; memory.reset_n := reset_n
  memory.proof.foreach(_:=proofMemory.get)
  proofRam.foreach(_:=0.U.asTypeOf(new UsbMemoryProofState))
  memory.observed.foreach(s=>proofRam.get:=s)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    def advance(pointer: UInt): UInt = Mux(pointer === 64.U,0.U,pointer + 1.U)
    val head = RegInit(0.U(7.W)); val tail = RegInit(0.U(7.W)); val speculative = RegInit(0.U(7.W))
    val reject = RegInit(false.B); val valid = RegInit(false.B); val value = RegInit(0.U(8.W))
    proof.foreach { p=>p.head:=head;p.tail:=tail;p.speculative:=speculative;p.reject:=reject }
    val nextSpeculative = RegNext(advance(speculative),1.U)
    val nextHead = RegNext(advance(head),1.U)
    val full = RegNext(head === nextSpeculative,false.B)
    val available = RegNext(head =/= tail,false.B)
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
