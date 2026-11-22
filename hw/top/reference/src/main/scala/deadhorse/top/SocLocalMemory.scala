package deadhorse.top

import chisel3._
import chisel3.util._
import chisel3.util.experimental.loadMemoryFromFileInline
import deadhorse.lib.LocalBus
import java.nio.file.Paths

/** Current-request arbitration, synchronous single-port word banks and a
  * retained MMIO slot. clientReset_n may assert without serviceReset_n.
  * Neither reset clears SRAM. The caller supplies shared-qualified releases.
  */
class SocLocalMemory(description: SocDescription, romImage: String,
                     banks: Int = 4, readLatency: Int = 1,
                     ramImages: Seq[String] = Seq.empty, dmaEnabled: Boolean = false,
                     xipEnabled: Boolean = false) extends RawModule {
  private val romRegion = description.region("boot_rom")
  private val ramRegion = description.region("performance_sram")
  require(banks >= 1 && isPow2(banks) && ramRegion.size % (4 * banks) == 0)
  require(readLatency >= 1 && readLatency <= 5)
  require(ramImages.isEmpty || ramImages.size == banks)
  ramImages.foreach(p => require(Paths.get(p).toAbsolutePath.normalize.startsWith(Paths.get("build").toAbsolutePath.normalize)))
  require(Paths.get(romImage).toAbsolutePath.normalize.startsWith(Paths.get("build").toAbsolutePath.normalize))
  val clk = IO(Input(Clock()))
  val serviceReset_n = IO(Input(Bool())); val clientReset_n = IO(Input(Bool()))
  val instruction = IO(new LocalBus); val data = IO(new LocalBus)
  val dma = if(dmaEnabled) Some(IO(new LocalBus)) else None
  val peripheral = IO(Flipped(new LocalBus))
  val xip = if(xipEnabled) Some(IO(Flipped(new LocalBus))) else None
  val epochReady = IO(Output(Bool()))
  protected def returned(value: UInt): UInt = value
  protected def instructionValid(value: Bool): Bool = value
  protected def xipResponseAllowed(ready: Bool): Bool = ready

  withClockAndReset(clk, (!serviceReset_n).asAsyncReset) {
    val dataBusy = RegInit(false.B)
    val offered = RegInit(false.B); val issued = RegInit(false.B)
    val request = Reg(chiselTypeOf(data.bits))
    peripheral.req := offered; peripheral.bits := request
    val terminal = issued && peripheral.rvalid
    when(offered && peripheral.gnt) { offered := false.B; issued := true.B }
    when(terminal) { issued := false.B }
    val xOffered=RegInit(false.B);val xIssued=RegInit(false.B);val xInstruction=RegInit(false.B)
    val iBusy=RegInit(false.B);val xPacket=Reg(chiselTypeOf(data.bits))
    val xTerminal=WireDefault(false.B)
    xip.foreach {port=>
      port.req:=xOffered;port.bits:=xPacket
      xTerminal:=xIssued && port.rvalid
      when(xOffered && port.gnt) {xOffered:=false.B;xIssued:=true.B}
      when(xTerminal) {xIssued:=false.B;when(xInstruction) {iBusy:=false.B}}
    }
    val xBusy=xOffered || xIssued
    def xAddress(address: UInt): Bool=if(xipEnabled) {
      val r=description.xipRegion;address>=r.base.U && address<(r.base+r.size).U
    } else false.B
    val iXip=xAddress(instruction.bits.addr);val dXip=xAddress(data.bits.addr)
    val iLocalPending=WireDefault(false.B)
    val iEligible= !iBusy && (!iXip || (!xBusy && !iLocalPending))

    val clientReset = (!(clientReset_n && serviceReset_n)).asAsyncReset
    val ready = withReset(clientReset) { RegInit(false.B) }
    when(!dataBusy && !offered && !issued && !xBusy) { ready := true.B }
    epochReady := ready
    // D65: arbitrate current requests, with registered round-robin preference.
    // A remote terminal clears dataBusy before its public response retires;
    // exclude that response cycle as well to keep one outstanding data beat.
    val preferData = withReset(clientReset) { RegInit(false.B) }
    val chooseData = ready && !dataBusy && !data.rvalid && data.req &&
      (!instruction.req || preferData || !iEligible) && (!dXip || !xBusy)
    val chooseDma = WireDefault(false.B)
    val fireM = WireDefault(false.B)
    if(dmaEnabled) {
      val port=dma.get
      val dmaBusy=RegInit(false.B);val preferDma=RegInit(false.B)
      val cpuWants=ready && ((instruction.req && iEligible) || chooseData)
      chooseDma:=port.req && !dmaBusy && (!cpuWants || preferDma)
      port.gnt:=chooseDma;fireM:=port.req && port.gnt
      when(fireM) {dmaBusy:=true.B;preferDma:=false.B}
      when((instruction.req && instruction.gnt) || (data.req && data.gnt)) {preferDma:=true.B}
      val complete=(0 until readLatency).foldLeft(fireM)((v,_)=>RegNext(v,false.B))
      when(complete) {dmaBusy:=false.B}
      port.rvalid:=complete
    }
    instruction.gnt := ready && !chooseData && !chooseDma && iEligible
    data.gnt := chooseData && !chooseDma
    val fireI = instruction.req && instruction.gnt
    val fireD = data.req && data.gnt
    when(fireI) { preferData := true.B }
    when(fireD) { preferData := false.B }

    val cpuSelected = Mux(fireD, data.bits, instruction.bits)
    val selected = if(dmaEnabled) Mux(fireM,dma.get.bits,cpuSelected) else cpuSelected
    val fire = fireI || fireD || fireM
    def inside(base: BigInt, size: BigInt): Bool = selected.addr >= base.U && selected.addr < (base + size).U
    val romHit = inside(romRegion.base, romRegion.size)
    val ramHit = inside(ramRegion.base, ramRegion.size)
    val xipHit=xAddress(selected.addr)
    val denied = selected.origin =/= description.origin("performance").U || selected.addr(1, 0).orR
    val invalid = denied || (fireI && (!romHit && !ramHit && !xipHit || selected.we)) ||
      ((romHit || xipHit) && selected.we) || (fireM && !ramHit)
    val nativeRead=(fireI || fireD) && xipHit && !invalid
    val mmio = fireD && !romHit && !ramHit && !xipHit && !denied
    val localD = fireD && !mmio && !nativeRead
    val localI=fireI && !nativeRead
    when(fireD) { dataBusy := true.B }
    when(mmio) { request := data.bits; offered := true.B }
    when(nativeRead) {xPacket:=selected;xOffered:=true.B;xInstruction:=fireI;when(fireI) {iBusy:=true.B}}

    val rom = SyncReadMem((romRegion.size / 4).toInt, UInt(32.W))
    loadMemoryFromFileInline(rom, romImage)
    val romWord = ((selected.addr - romRegion.base.U) >> 2).asUInt
    val romData = rom.read(romWord, fire && romHit && !invalid)
    val word = (selected.addr - ramRegion.base.U) >> 2
    val bankBits = log2Ceil(banks)
    val bankIndex = if(banks == 1) 0.U else word(bankBits - 1, 0)
    val row = word >> bankBits
    val laneData = selected.wdata.asTypeOf(Vec(4, UInt(8.W)))
    val laneMask = selected.be.asBools
    val outputs = (0 until banks).map { index =>
      val memory = SyncReadMem((ramRegion.size / (4 * banks)).toInt, Vec(4, UInt(8.W)))
      if(ramImages.nonEmpty) loadMemoryFromFileInline(memory, ramImages(index))
      memory.readWrite(row, laneData, laneMask,
        fire && ramHit && !invalid && bankIndex === index.U, (fireD || fireM) && selected.we).asUInt
    }
    val bankQ = RegNext(bankIndex)
    val romQ = RegNext(romHit)
    val writeQ = RegNext(selected.we)
    val badQ = RegNext(invalid)
    val bankData = if(banks == 1) outputs.head else VecInit(outputs)(bankQ)
    val firstData = Mux(badQ || writeQ, 0.U, Mux(romQ, romData, bankData))
    def pipe[T <: Data](value: T, stages: Int): T =
      (0 until stages).foldLeft(value)((previous, _) => RegNext(previous))
    def validPipe(value: Bool, stages: Int): Bool =
      (0 until stages).foldLeft(value)((previous, _) => RegNext(previous, false.B))
    val memoryData = pipe(firstData, readLatency - 1)
    val memoryError = pipe(badQ, readLatency - 1)
    dma.foreach {port=>port.rdata:=returned(memoryData);port.err:=memoryError}
    val localDone = validPipe(localD, readLatency)
    when(localDone || terminal || (xTerminal && !xInstruction)) { dataBusy := false.B }
    val localStages=(0 until readLatency).scanLeft(localI)((v,_)=>RegNext(v,false.B)).tail
    iLocalPending:=localStages.reduce(_||_)

    val peripheralData = Reg(UInt(32.W)); val peripheralError = Reg(Bool())
    when(terminal) {
      peripheralData := Mux(peripheral.err || request.we, 0.U, peripheral.rdata)
      peripheralError := peripheral.err
    }
    val xData=Reg(UInt(32.W));val xError=Reg(Bool());val xWasInstruction=Reg(Bool())
    xip.foreach {port=>when(xTerminal) {xData:=Mux(port.err,0.U,port.rdata);xError:=port.err;xWasInstruction:=xInstruction}}
    withReset(clientReset) {
      val iValid = validPipe(localI, readLatency)
      val dLocal = validPipe(localD, readLatency)
      val dRemote = RegNext(terminal && ready, false.B)
      val dValid = RegNext(validPipe(localD, readLatency - 1) || terminal && ready, false.B)
      val xValid=RegNext(xTerminal && xipResponseAllowed(ready),false.B)
      val iFlash=xValid && xWasInstruction;val dFlash=xValid && !xWasInstruction
      instruction.rvalid := instructionValid(iValid || iFlash)
      instruction.rdata := returned(Mux(iFlash,xData,memoryData))
      instruction.err := Mux(iFlash,xError,memoryError)
      data.rvalid := dValid || dFlash
      data.rdata := returned(Mux(dFlash,xData,Mux(dRemote, peripheralData, memoryData)))
      data.err := Mux(dFlash,xError,Mux(dRemote, peripheralError, memoryError))
      // Safety properties on the production composition, not environment assumptions.
      assert(!(fireI && fireD))
      assert(!(dLocal && dRemote))
      assert(!fireD || !dataBusy)
      assert(!mmio || !offered && !issued)
      if(xipEnabled) {
        assert(!(iValid && iFlash));assert(!(dValid && dFlash))
        assert(!nativeRead || !xBusy)
      }
    }
  }
}
