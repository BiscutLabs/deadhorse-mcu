package deadhorse.usb

import chisel3._
import chisel3.util._

/** Verification-only over-approximation. A tracked physical slot is exact once
  * written; a current-address cache preserves stalled-data stability. Forgotten
  * contents come from an unconstrained input, never a protocol assumption.
  * Acceptance requires the separate real-memory refinement proof.
  */
class UsbSparsePacketMemory extends UsbPacketMemoryPort(true) {
  protected def finish(value: UInt): UInt=RegNext(value)
  val cacheAddressView=IO(Output(UInt(7.W)));val cacheValidView=IO(Output(Bool()));val cacheValueView=IO(Output(UInt(8.W)))
  val trackedValidView=IO(Output(Bool()));val trackedValueView=IO(Output(UInt(8.W)))
  val readQueryView=IO(Output(UInt(7.W)))
  val track=proof.get.track;val trackAddress=proof.get.trackAddress
  val forgotten=proof.get.forgotten
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val pendingWrite=RegNext(write && writeAddress<72.U,false.B)
    val pendingAddress=RegNext(writeAddress)
    val pendingData=RegNext(writeData)
    val effectiveWrite=pendingWrite && reset_n
    val lastTrackAddress=RegNext(trackAddress)
    val trackedKnown=RegInit(false.B);val trackedValue=Reg(UInt(8.W))
    val cacheValid=RegInit(false.B);val cacheAddress=Reg(UInt(7.W));val cacheValue=Reg(UInt(8.W))
    val sameTracked=track && trackedKnown && trackAddress===lastTrackAddress
    cacheAddressView:=cacheAddress;cacheValidView:=cacheValid;cacheValueView:=cacheValue
    trackedValidView:=sameTracked;trackedValueView:=trackedValue
    // The emitted SyncReadMem registers the address, then reads the current
    // array contents. A simultaneous write is visible after that same edge.
    val query=RegNext(readAddress);readQueryView:=query
    val oldRead=Mux(query>=72.U,0.U,
      Mux(sameTracked && query===trackAddress,trackedValue,
        Mux(cacheValid && query===cacheAddress,cacheValue,forgotten)))
    val r1=RegNext(oldRead);readData:=finish(r1)
    observed.get.trackedValid:=sameTracked;observed.get.trackedValue:=trackedValue
    observed.get.query:=query;observed.get.stage:=r1;observed.get.output:=readData
    observed.get.pendingWrite:=effectiveWrite;observed.get.pendingAddress:=pendingAddress;observed.get.pendingData:=pendingData
    cacheValid:=query<72.U;cacheAddress:=query
    cacheValue:=Mux(effectiveWrite && pendingAddress===query,pendingData,oldRead)
    when(!track || trackAddress=/=lastTrackAddress){trackedKnown:=false.B}
    when(track && effectiveWrite && pendingAddress===trackAddress){trackedValue:=pendingData;trackedKnown:=true.B}
  }
}

class UsbMisphasedSparseMemory extends UsbSparsePacketMemory {
  override protected def finish(value: UInt): UInt=RegNext(RegNext(value))
}

/** Existence-witness refinement: generated binding connects the three witness
  * words to actual production RAM cells at the specified addresses. No assume
  * is added: the abstract model may choose exactly these actual words.
  */
class UsbPacketMemoryRefinement(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val write=IO(Input(Bool()));val writeAddress=IO(Input(UInt(7.W)));val writeData=IO(Input(UInt(8.W)))
  val readAddress=IO(Input(UInt(7.W)));val track=IO(Input(Bool()));val trackAddress=IO(Input(UInt(7.W)))
  val witnessRead=IO(Input(UInt(8.W)));val witnessCache=IO(Input(UInt(8.W)));val witnessTracked=IO(Input(UInt(8.W)))
  val cacheAddress=IO(Output(UInt(7.W)))
  val readQuery=IO(Output(UInt(7.W)))
  val real=Module(new UsbPacketMemory)
  val sparse=Module(if(variant=="corrupt") new UsbMisphasedSparseMemory else new UsbSparsePacketMemory)
  for(m<-Seq(real,sparse)) {
    m.clk:=clock;m.reset_n:=reset_n;m.write:=write;m.writeAddress:=writeAddress;m.writeData:=writeData;m.readAddress:=readAddress
  }
  sparse.proof.get.track:=track;sparse.proof.get.trackAddress:=trackAddress;sparse.proof.get.forgotten:=witnessRead
  cacheAddress:=sparse.cacheAddressView
  readQuery:=sparse.readQueryView
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val age=RegInit(0.U(2.W));when(age=/=3.U){age:=age+1.U}
    if(variant=="cover") {
      cover(age===3.U && sparse.trackedValidView && write && readAddress===trackAddress && real.readData===writeData && sparse.readData===real.readData)
      cover(age===3.U && sparse.cacheValidView && !write && readAddress===cacheAddress && real.readData===writeData && sparse.readData===real.readData)
    } else {
      when(sparse.cacheValidView){assert(sparse.cacheValueView===witnessCache)}
      when(sparse.trackedValidView && trackAddress<72.U){assert(sparse.trackedValueView===witnessTracked)}
      when(age===3.U){assert(sparse.readData===real.readData)}
    }
  }
}

object EmitUsbMemoryRefinement {
  def main(args: Array[String]):Unit={
    val root=java.nio.file.Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(java.nio.file.Paths.get("build").toAbsolutePath.normalize))
    for(variant<-Seq("correct","cover","corrupt")) {
      val out=root.resolve(variant);java.nio.file.Files.createDirectories(out)
      _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new UsbPacketMemoryRefinement(variant)),
        Array("--target-dir",out.toString),Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
    }
  }
}
