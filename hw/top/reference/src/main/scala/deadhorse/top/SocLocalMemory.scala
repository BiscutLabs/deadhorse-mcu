package deadhorse.top

import chisel3._
import chisel3.util._
import chisel3.util.experimental.loadMemoryFromFileInline
import deadhorse.lib.LocalBus
import java.nio.file.Paths

/** Registered grant arbitration, synchronous single-port word banks and a
  * retained MMIO slot. clientReset_n may assert without serviceReset_n.
  * Neither reset clears SRAM. The caller supplies shared-qualified releases.
  */
class SocLocalMemory(description: SocDescription, romImage: String,
                     banks: Int = 4, readLatency: Int = 1) extends RawModule {
  private val romRegion = description.region("boot_rom")
  private val ramRegion = description.region("performance_sram")
  require(banks >= 1 && isPow2(banks) && ramRegion.size % (4 * banks) == 0)
  require(readLatency >= 1 && readLatency <= 5)
  require(Paths.get(romImage).toAbsolutePath.normalize.startsWith(Paths.get("build").toAbsolutePath.normalize))
  val clk = IO(Input(Clock()))
  val serviceReset_n = IO(Input(Bool())); val clientReset_n = IO(Input(Bool()))
  val instruction = IO(new LocalBus); val data = IO(new LocalBus)
  val peripheral = IO(Flipped(new LocalBus))
  val epochReady = IO(Output(Bool()))
  protected def returned(value: UInt): UInt = value
  protected def instructionValid(value: Bool): Bool = value

  withClockAndReset(clk, (!serviceReset_n).asAsyncReset) {
    val dataBusy = RegInit(false.B)
    val offered = RegInit(false.B); val issued = RegInit(false.B)
    val request = Reg(chiselTypeOf(data.bits))
    peripheral.req := offered; peripheral.bits := request
    val terminal = issued && peripheral.rvalid
    when(offered && peripheral.gnt) { offered := false.B; issued := true.B }
    when(terminal) { issued := false.B }

    val clientReset = (!(clientReset_n && serviceReset_n)).asAsyncReset
    val ready = withReset(clientReset) { RegInit(false.B) }
    when(!dataBusy && !offered && !issued) { ready := true.B }
    epochReady := ready
    val grantI = withReset(clientReset) { RegInit(false.B) }
    val grantD = withReset(clientReset) { RegInit(false.B) }
    instruction.gnt := grantI; data.gnt := grantD
    val fireI = instruction.req && grantI
    val fireD = data.req && grantD
    val nextData = ready && !dataBusy && !fireD && data.req && (!grantD || !instruction.req)
    grantD := nextData
    grantI := ready && !nextData

    val selected = Mux(fireD, data.bits, instruction.bits)
    val fire = fireI || fireD
    def inside(base: BigInt, size: BigInt): Bool = selected.addr >= base.U && selected.addr < (base + size).U
    val romHit = inside(romRegion.base, romRegion.size)
    val ramHit = inside(ramRegion.base, ramRegion.size)
    val denied = selected.origin =/= description.origin("performance").U || selected.addr(1, 0).orR
    val invalid = denied || (fireI && (!romHit && !ramHit || selected.we)) || (romHit && selected.we)
    val mmio = fireD && !romHit && !ramHit && !denied
    val localD = fireD && !mmio
    when(fireD) { dataBusy := true.B }
    when(mmio) { request := data.bits; offered := true.B }

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
      memory.readWrite(row, laneData, laneMask,
        fire && ramHit && !invalid && bankIndex === index.U, fireD && selected.we).asUInt
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
    val localDone = validPipe(localD, readLatency)
    when(localDone || terminal) { dataBusy := false.B }

    val peripheralData = Reg(UInt(32.W)); val peripheralError = Reg(Bool())
    when(terminal) {
      peripheralData := Mux(peripheral.err || request.we, 0.U, peripheral.rdata)
      peripheralError := peripheral.err
    }
    withReset(clientReset) {
      val iValid = validPipe(fireI, readLatency)
      val dLocal = validPipe(localD, readLatency)
      val dRemote = RegNext(terminal && ready, false.B)
      val dValid = RegNext(validPipe(localD, readLatency - 1) || terminal && ready, false.B)
      instruction.rvalid := instructionValid(iValid)
      instruction.rdata := returned(memoryData)
      instruction.err := memoryError
      data.rvalid := dValid
      data.rdata := returned(Mux(dRemote, peripheralData, memoryData))
      data.err := Mux(dRemote, peripheralError, memoryError)
      // Safety properties on the production composition, not environment assumptions.
      assert(!(fireI && fireD))
      assert(!(dLocal && dRemote))
      assert(!fireD || !dataBusy)
      assert(!mmio || !offered && !issued)
    }
  }
}
