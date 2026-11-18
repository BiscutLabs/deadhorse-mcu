package deadhorse.i2c_recovery_loader

import chisel3._
import java.util.zip.CRC32

class CorruptRecoveryLoader extends RecoveryLoader(32, 16, 256) {
  override protected def storeWord(value: UInt): UInt = value ^ 1.U
}

/** Resolve public pins and count one-edge output pulses while the host clocks the wire. */
class RecoveryPeerBench(corrupt: Boolean = false, val capacity: Int = 32) extends Module {
  val powerOk = IO(Input(Bool()))
  val systemOk = IO(Input(Bool()))
  val scl = IO(Input(Bool()))
  val hostLow = IO(Input(Bool()))
  val sda = IO(Output(Bool()))
  val pullLow = IO(Output(Bool()))
  val ready = IO(Input(Bool()))
  val done = IO(Input(Bool()))
  val halt = IO(Input(Bool()))
  val resetReason = IO(Input(UInt(32.W)))
  val crashCount = IO(Input(UInt(32.W)))
  val request = IO(Output(Bool()))
  val offset = IO(Output(UInt(32.W)))
  val word = IO(Output(UInt(32.W)))
  val validImage = IO(Output(Bool()))
  val locked = IO(Output(Bool()))
  val busy = IO(Output(Bool()))
  val hold = IO(Output(Bool()))
  val starts = IO(Output(UInt(8.W)))
  val wakes = IO(Output(UInt(8.W)))
  val wakePulse = IO(Output(Bool()))
  val lastEntry = IO(Output(UInt(32.W)))
  val writes = IO(Output(UInt(8.W)))
  val dut = Module(if (corrupt) new CorruptRecoveryLoader else new RecoveryLoader(capacity, 16, 256))
  dut.clk := clock
  dut.por_n := powerOk
  dut.reset_n := systemOk
  dut.halted := halt
  dut.resetReason := resetReason
  dut.crashCount := crashCount
  dut.sclIn := scl
  sda := !(hostLow || dut.sdaLow)
  dut.sdaIn := sda
  pullLow := dut.sdaLow
  dut.memReady := ready
  dut.memDone := done
  request := dut.memValid
  offset := dut.memOffset
  word := dut.memWord
  busy := dut.busy
  hold := dut.clockHold
  validImage := dut.programmed
  locked := dut.locked
  val startCount = RegInit(0.U(8.W))
  val wakeCount = RegInit(0.U(8.W))
  val entryOnStart = RegInit(0.U(32.W))
  val writeCount = RegInit(0.U(8.W))
  when(dut.start) {
    startCount := startCount + 1.U
    entryOnStart := dut.entry
  }
  when(dut.wake) { wakeCount := wakeCount + 1.U }
  when(dut.memValid && ready) { writeCount := writeCount + 1.U }
  starts := startCount
  wakes := wakeCount
  wakePulse := dut.wake
  lastEntry := entryOnStart
  writes := writeCount
}

/** Immutable host encoding and checksum independent of the loader. */
object RecoveryImage {
  def bytes(word: Long): Seq[Int] = (0 until 4).map(i => ((word >>> (8 * i)) & 255L).toInt)
  def checksum(words: Seq[Long]): Long = {
    val crc = new CRC32
    words.flatMap(bytes).foreach(crc.update)
    crc.getValue
  }
}

class RecoveryPeer(val d: RecoveryPeerBench) extends chisel3.simulator.PeekPokeAPI {
  import RecoveryImage._
  val memory: Array[Int] = Array.fill(d.capacity)(0xaa)
  private var accepted: Option[(Int, Long)] = None
  def step(cycles: Int = 1): Unit = d.clock.step(cycles)
  def initialize(): Unit = {
    d.scl.poke(true.B); d.hostLow.poke(false.B)
    d.ready.poke(false.B); d.done.poke(false.B); d.halt.poke(false.B)
    d.resetReason.poke(1.U); d.crashCount.poke(0.U)
    reset(power = true)
  }
  def reset(power: Boolean): Unit = {
    // A cold reset drives both inputs. A warm reset drives only the
    // whole-domain reset, so an erroneously cleared lock is observable.
    d.systemOk.poke(false.B)
    d.powerOk.poke((!power).B)
    step(5)
    d.pullLow.expect(false.B); d.request.expect(false.B)
    accepted = None // Backend flush discards uncommitted work.
    d.powerOk.poke(true.B); step(2)
    d.systemOk.poke(true.B); step(8)
  }
  def drive(sclHigh: Boolean, hostLow: Boolean): Unit = {
    d.scl.poke(sclHigh.B); d.hostLow.poke(hostLow.B); step(5)
  }
  def start(): Unit = {
    drive(true, false); drive(true, true); drive(false, true)
  }
  def stop(): Unit = {
    drive(false, true); drive(true, true); drive(true, false)
    step(8)
  }
  def bit(low: Boolean): Unit = {
    drive(false, low); drive(true, low); drive(false, low)
  }
  def send(value: Int, ack: Boolean = true): Unit = {
    (7 to 0 by -1).foreach(i => bit((value & (1 << i)) == 0))
    drive(false, false); drive(true, false)
    d.sda.expect((!ack).B); drive(false, false)
  }
  def receive(last: Boolean): Int = {
    var value = 0
    for (_ <- 0 until 8) {
      drive(false, false); drive(true, false)
      value = (value << 1) | (if (d.sda.peek().litToBoolean) 1 else 0)
      drive(false, false)
    }
    bit(!last)
    // Release ACK before forming a repeated START/STOP.
    drive(false, false)
    value
  }
  def frame(payload: Seq[Int]): Unit = {
    start(); send(0x6a); payload.foreach(b => send(b))
  }
  def command(op: Int, words: Long*): Unit = {
    frame(Seq(op) ++ words.flatMap(bytes)); stop()
  }
  def begin(length: Long, entry: Long, crc: Long, abi: Long = 0x10000,
      ram: Long = 16, gpio: Long = 0, channels: Long = 0, id: Long = 0xdecafbadL): Unit =
    command(1, length, entry, crc, abi, ram, gpio, channels, id)
  def selectRead(space: Int, instance: Int, index: Int): Unit = {
    frame(Seq(0, space, instance, index))
    start(); send(0x6b)
  }
  def readWords(count: Int): Seq[Long] = {
    val data = (0 until count * 4).map(i => receive(last = i == count * 4 - 1))
    stop()
    data.grouped(4).map(_.zipWithIndex.map { case (b, i) => b.toLong << (8 * i) }.sum).toVector
  }
  def read(space: Int, index: Int, count: Int = 1, instance: Int = 0): Seq[Long] = {
    selectRead(space, instance, index)
    readWords(count)
  }
  /** Four edges low and four high, with one edge of host data hold after fall. */
  def minimumRatioBit(hostLow: Boolean): Int = {
    d.scl.poke(false.B); step()
    d.hostLow.poke(hostLow.B); step(3)
    d.scl.poke(true.B)
    val seen = d.sda.peek().litToBoolean
    step(4)
    assert(d.sda.peek().litToBoolean == seen, "SDA changed during the high phase")
    if (seen) 1 else 0
  }
  def fastSnapshot(index: Int)(afterAddress: => Unit): Seq[Long] = {
    frame(Seq(0, 0, 0, index))
    start()
    for (bit <- 7 to 0 by -1) minimumRatioBit((0x6b & (1 << bit)) == 0)
    assert(minimumRatioBit(false) == 0, "target did not ACK read address")
    afterAddress
    val data = (0 until 36).map { i =>
      var byte = 0
      for (_ <- 0 until 8) byte = (byte << 1) | minimumRatioBit(false)
      minimumRatioBit(i < 35)
      byte
    }
    stop()
    data.grouped(4).map(_.zipWithIndex.map { case (b, i) => b.toLong << (8 * i) }.sum).toVector
  }
  def expectError(code: Int): Unit = assert(read(1, 5).head == code, s"expected loader error $code")
  def awaitRequest(): Unit = {
    var remaining = 256
    while (!d.request.peek().litToBoolean && remaining > 0) {
      step()
      remaining -= 1
    }
    d.request.expect(true.B)
  }
  def acceptWord(expectedOffset: Int, expectedWord: Long): Unit = {
    require(accepted.isEmpty)
    awaitRequest()
    val offset = d.offset.peek().litValue.toInt
    val word = d.word.peek().litValue.toLong
    require(offset == expectedOffset && word == expectedWord, "RECOVERY_MEMORY_MODEL")
    d.ready.poke(true.B); step(); d.ready.poke(false.B)
    accepted = Some(offset -> word)
  }
  def completeOnNextEdge(): Unit = {
    val (address, word) = accepted.get
    bytes(word).zipWithIndex.foreach { case (b, i) => memory(address + i) = b }
    d.done.poke(true.B); step(); d.done.poke(false.B)
    accepted = None
  }
  def complete(): Unit = { completeOnNextEdge(); step() }
  def pulseDone(): Unit = { d.done.poke(true.B); step(); d.done.poke(false.B); step() }
  def upload(words: Seq[Long], entry: Int): Unit = {
    begin(words.length * 4, entry, checksum(words))
    words.zipWithIndex.foreach { case (word, i) =>
      command(2, i * 4, word); acceptWord(i * 4, word); complete()
    }
    command(3)
    assert(read(1, 0, 2) == Seq(2, 1))
    assert(memory.take(words.size * 4).toSeq == words.flatMap(bytes))
  }
}
