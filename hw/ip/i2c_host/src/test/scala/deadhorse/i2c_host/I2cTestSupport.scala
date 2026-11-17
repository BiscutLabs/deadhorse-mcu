package deadhorse.i2c_host

import chisel3._
import deadhorse.lib.{LocalBus, ResetRelease}
import scala.collection.mutable.ArrayBuffer

class I2cBadBit(json: String) extends I2cHost(json, BigInt("40012000", 16)) {
  override protected def outputBit(value: Bool): Bool = !value
}

class I2cBadRead(json: String) extends I2cHost(json, BigInt("40012000", 16)) {
  override protected def receiveByte(value: UInt): UInt = value ^ 1.U
}

/** Resolve only public open-drain ports; no private DUT signal is exposed. */
class I2cBench(json: String, corrupt: Boolean = false, corruptRead: Boolean = false) extends RawModule {
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new LocalBus); val owner = IO(Input(UInt(3.W)))
  val peerSclLow = IO(Input(Bool())); val peerSdaLow = IO(Input(Bool()))
  val scl = IO(Output(Bool())); val sda = IO(Output(Bool()))
  val sclLow = IO(Output(Bool())); val sdaLow = IO(Output(Bool()))
  val pinsEnable = IO(Output(Bool())); val irq = IO(Output(Bool()))
  val clockHold = IO(Output(Bool())); val quiescent = IO(Output(Bool()))
  val sleepRequest = IO(Input(Bool())); val sleepEnable = IO(Input(Bool()))
  val release = Module(new ResetRelease)
  release.clk := clk; release.reset_n := reset_n
  val dut = Module(if(corrupt) new I2cBadBit(json) else if(corruptRead) new I2cBadRead(json)
    else new I2cHost(json, BigInt("40012000", 16)))
  dut.clk := clk; dut.reset_n := release.released; dut.bus <> bus; dut.owner := owner
  dut.sclIn := !(dut.sclLow || peerSclLow); dut.sdaIn := !(dut.sdaLow || peerSdaLow)
  dut.sleepRequest := sleepRequest; dut.sleepEnable := sleepEnable
  scl := dut.sclIn; sda := dut.sdaIn; sclLow := dut.sclLow; sdaLow := dut.sdaLow
  pinsEnable := dut.pinsEnable; irq := dut.irq; clockHold := dut.clockHold; quiescent := dut.quiescent
}

case class I2cTiming(hold: Int, low: Int, high: Int, free: Int) {
  def word: BigInt = BigInt(hold) | (BigInt(low) << 8) | (BigInt(high) << 16) | (BigInt(free) << 24)
}
case class I2cSample(cycle: Int, scl: Boolean, sda: Boolean, sclLow: Boolean, sdaLow: Boolean)
class I2cFrame(val reading: Boolean, val byte: Int, val ack: Boolean) {
  val rises = ArrayBuffer.empty[Int]; val falls = ArrayBuffer.empty[Int]
  var observed = 0
}

/** A software target that decodes resolved wire edges and supplies bytes/ACKs.
  * Expectations are explicit transaction bytes, not a replica of host state. */
class I2cPeer {
  var dataLow = false
  var current: Option[I2cFrame] = None
  val frames = ArrayBuffer.empty[I2cFrame]
  val starts = ArrayBuffer.empty[Int]; val stops = ArrayBuffer.empty[Int]
  val rises = ArrayBuffer.empty[Int]; val falls = ArrayBuffer.empty[Int]
  private var oldScl = true; private var oldSda = true
  private def bit(byte: Int, index: Int): Boolean = ((byte >> (7 - index)) & 1) != 0
  def arm(reading: Boolean, byte: Int, ack: Boolean): I2cFrame = {
    require(current.isEmpty && !oldScl, "I2C_PEER_MODEL byte armed outside owned-low gap")
    val f = new I2cFrame(reading, byte, ack)
    current = Some(f); dataLow = reading && !bit(byte, 0); f
  }
  def settled(scl: Boolean, sda: Boolean): Unit = { oldScl = scl; oldSda = sda }
  def observe(cycle: Int, scl: Boolean, sda: Boolean): Unit = {
    if(oldScl && scl && oldSda != sda) {
      require(current.isEmpty, "I2C_PEER_MODEL unexpected START/STOP within byte")
      if(sda) stops += cycle else starts += cycle
    }
    if(!oldScl && scl) {
      rises += cycle
      current.foreach { f =>
        val index = f.rises.size; require(index < 9, "I2C_PEER_MODEL extra clock")
        f.rises += cycle
        if(index < 8) {
          f.observed = (f.observed << 1) | (if(sda) 1 else 0)
          if(f.reading) require(sda == bit(f.byte, index), "I2C_PEER_MODEL read wire contention")
        } else {
          require((!sda) == f.ack, "I2C_PEER_MODEL wrong ninth-clock ACK/NACK")
          require(f.observed == f.byte, s"I2C_PEER_DATA byte ${f.observed} != ${f.byte}")
        }
      }
    }
    if(oldScl && !scl) {
      falls += cycle
      current.foreach { f =>
        f.falls += cycle
        require(f.falls.size == f.rises.size, "I2C_PEER_MODEL falling edge without bit")
        val sampled = f.rises.size
        if(sampled == 9) { frames += f; current = None; dataLow = false }
        else if(f.reading) dataLow = sampled < 8 && !bit(f.byte, sampled)
        else dataLow = sampled == 8 && f.ack
      }
    }
    settled(scl, sda)
  }
}

class I2cDriver(val d: I2cBench) extends chisel3.simulator.PeekPokeAPI {
  var cycles = 0; var peer = new I2cPeer
  var forceScl = false; var forceSda = false
  var beforeStep: Int => Unit = _ => ()
  var afterStep: () => Unit = () => ()
  val samples = ArrayBuffer.empty[I2cSample]
  def high(pin: Bool): Boolean = pin.peek().litValue == 1
  private def drive(): Unit = {
    d.peerSclLow.poke(forceScl.B); d.peerSdaLow.poke((forceSda || peer.dataLow).B)
  }
  def step(n: Int = 1): Unit = for(_ <- 0 until n) {
    beforeStep(cycles + 1); drive(); d.clk.step(); cycles += 1
    peer.observe(cycles, high(d.scl), high(d.sda))
    afterStep(); drive()
    peer.settled(high(d.scl), high(d.sda))
    samples += I2cSample(cycles, high(d.scl), high(d.sda), high(d.sclLow), high(d.sdaLow))
  }
  def reset(): Unit = {
    peer = new I2cPeer; forceScl = false; forceSda = false
    beforeStep = _ => (); afterStep = () => (); samples.clear(); cycles = 0
    d.reset_n.poke(false.B); d.owner.poke(3.U)
    d.sleepRequest.poke(false.B); d.sleepEnable.poke(false.B)
    d.bus.req.poke(false.B); d.bus.bits.addr.poke(0.U); d.bus.bits.we.poke(false.B)
    d.bus.bits.wdata.poke(0.U); d.bus.bits.be.poke(0.U); d.bus.bits.origin.poke(0.U)
    step(2); d.reset_n.poke(true.B); step(12)
    peer = new I2cPeer; peer.settled(high(d.scl), high(d.sda)); samples.clear()
  }
  def access(offset: Int, write: Boolean = false, data: BigInt = 0, be: Int = 15, origin: Int = 3): (BigInt, Boolean) = {
    val p = d.bus
    p.req.poke(true.B); p.bits.addr.poke((BigInt("40012000", 16) + offset).U)
    p.bits.we.poke(write.B); p.bits.wdata.poke(data.U); p.bits.be.poke(be.U); p.bits.origin.poke(origin.U)
    var granted = false; var done = false; var answer = BigInt(0); var error = false
    for(_ <- 0 until 64 if !done) {
      val accepted = high(p.req) && high(p.gnt)
      if(high(p.rvalid)) { require(granted, "I2C_BUS_MODEL unsolicited response"); answer = p.rdata.peek().litValue; error = high(p.err); done = true }
      step()
      if(accepted) { require(!granted, "I2C_BUS_MODEL duplicate grant"); granted = true; p.req.poke(false.B) }
    }
    require(done, "I2C_BUS_MODEL response deadline")
    if(write || error) require(answer == 0, "I2C_BUS_MODEL write/error data")
    p.req.poke(false.B); step(2); (answer, error)
  }
  def rd(offset: Int): BigInt = { val (value, error) = access(offset); require(!error, "I2C_BUS_MODEL read error"); value }
  def wr(offset: Int, value: BigInt, be: Int = 15): Unit = require(!access(offset, true, value, be)._2, "I2C_BUS_MODEL write error")
  def configure(timing: I2cTiming = I2cTiming(3, 12, 8, 16), timeout: Int = 65535, enable: Boolean = true): Unit = {
    wr(0, if(enable) 1 else 0); wr(4, timing.word); wr(8, timeout); wr(12, 32)
    require(rd(0x24) == timing.word && rd(0x28) == timeout && ((rd(0x18) & 64) != 0) == enable, "I2C_CONFIG_MODEL apply")
  }
  def waitEvent(bound: Int = 10000): Int = {
    val deadline = cycles + bound
    var events = rd(0x1c).toInt
    while((events & 0x5d) == 0 && cycles < deadline) { step(); events = rd(0x1c).toInt }
    require((events & 0x5d) != 0, "I2C_COMMAND_MODEL completion deadline")
    events
  }
  def command(mask: Int, bound: Int = 10000): Int = { wr(0x1c, 127); wr(12, mask); waitEvent(bound) }
  def start(): Unit = { require(command(1) == 1, "I2C_COMMAND_MODEL START"); require((rd(0x18) & 2) != 0 && high(d.clockHold), "I2C_COMMAND_MODEL ownership") }
  def stop(): Unit = { require(command(8) == 1, "I2C_COMMAND_MODEL STOP"); require((rd(0x18) & 3) == 0 && !high(d.clockHold), "I2C_COMMAND_MODEL release") }
  def writeByte(value: Int, ack: Boolean = true): I2cFrame = {
    val f = peer.arm(false, value, ack); wr(0x10, value)
    require(command(2) == (if(ack) 1 else 3), "I2C_COMMAND_MODEL WRITE result")
    require(((rd(0x18) & 8) != 0) == ack, "I2C_COMMAND_MODEL ACK status")
    require(peer.current.isEmpty, "I2C_PEER_MODEL unfinished WRITE"); f
  }
  def readByte(value: Int, ack: Boolean): I2cFrame = {
    val f = peer.arm(true, value, ack)
    require(command(4 | (if(ack) 64 else 0)) == 1, "I2C_COMMAND_MODEL READ result")
    require((rd(0x18) & 4) != 0 && rd(0x14) == value && rd(0x14) == value, "I2C_RX_MODEL retained byte")
    require(peer.current.isEmpty, "I2C_PEER_MODEL unfinished READ"); f
  }
}

object I2cTestFiles {
  def json: String = {
    os.proc("python3", "hw/regmap/regmap.py", "hw/ip/i2c_host/i2c_host.regmap.yaml", "--out", "build/t17/test-regmap").call()
    "build/t17/test-regmap/i2c_host_regs.json"
  }
}
