package deadhorse.spi_host

import chisel3._
import deadhorse.lib.{LocalBus, ResetRelease}
import scala.collection.mutable.ArrayBuffer

class SpiBadData(json: String, depth: Int) extends SpiHost(json, depth, BigInt("40011000",16)) {
  override protected def outputBit(value: Bool): Bool = !value
}
class SpiBench(json: String, depth: Int = 16, corrupt: Boolean = false) extends RawModule {
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new LocalBus); val owner = IO(Input(UInt(3.W)))
  val miso = IO(Input(Bool())); val sclk = IO(Output(Bool())); val mosi = IO(Output(Bool()))
  val cs_n = IO(Output(UInt(2.W))); val pinsEnable = IO(Output(Bool()))
  val timeNow = IO(Input(UInt(32.W))); val sleepRequest = IO(Input(Bool())); val sleepEnable = IO(Input(Bool()))
  val irq = IO(Output(Bool())); val dmaTxRequest = IO(Output(Bool())); val dmaRxRequest = IO(Output(Bool()))
  val clockHold = IO(Output(Bool())); val quiescent = IO(Output(Bool()))
  val release = Module(new ResetRelease); release.clk := clk; release.reset_n := reset_n
  val dut = Module(if(corrupt) new SpiBadData(json,depth) else new SpiHost(json,depth,BigInt("40011000",16)))
  dut.clk := clk; dut.reset_n := release.released; dut.bus <> bus; dut.owner := owner
  dut.miso := miso; dut.timeNow := timeNow; dut.sleepRequest := sleepRequest; dut.sleepEnable := sleepEnable
  sclk := dut.sclk; mosi := dut.mosi; cs_n := dut.cs_n; pinsEnable := dut.pinsEnable
  irq := dut.irq; dmaTxRequest := dut.dmaTxRequest; dmaRxRequest := dut.dmaRxRequest
  clockHold := dut.clockHold; quiescent := dut.quiescent
}

/** Pin protocol model: counts externally visible edges, never DUT state. */
class SpiPeer(val mode3: Boolean, val cs: Int, val half: Int, val sent: Seq[Int], val replies: Seq[Int]) {
  require(sent.nonEmpty && sent.size == replies.size)
  var start = -1; var end = -1; var edges = 0; var samples = 0
  var lastClock = mode3; var lastSelect = 3; var lastEdge = -1
  val observed = ArrayBuffer.empty[Int]
  private var byte = 0
  def bit(index: Int): Boolean = index < replies.size*8 && ((replies(index/8) >> (7-index%8))&1)!=0
  def checkByte(expected: Int, actual: Int): Unit =
    require(expected == actual,s"SPI_PIN_MODEL byte $actual != $expected")
  def edge(cycle: Int, clock: Boolean, data: Boolean, selects: Int): Option[Boolean] = {
    var drive: Option[Boolean] = None
    require(selects != 0,"SPI_PIN_MODEL simultaneous CS")
    if(lastSelect==3 && selects!=3) {
      require(start<0 && selects==(if(cs==0)2 else 1),"SPI_PIN_MODEL wrong/new CS")
      require(clock==mode3,"SPI_PIN_MODEL idle polarity")
      start=cycle;lastEdge=cycle
      if(!mode3)drive=Some(bit(0))
    }
    if(selects!=3) {
      require(selects==(if(cs==0)2 else 1),"SPI_PIN_MODEL CS changed")
      if(clock!=lastClock) {
        require(cycle-lastEdge==half,"SPI_PIN_MODEL edge interval")
        val leading=clock!=mode3
        require(leading==(edges%2==0),"SPI_PIN_MODEL edge order")
        if(leading==mode3) drive=Some(bit(samples))
        else {
          byte=(byte<<1)|(if(data)1 else 0);samples+=1
          if(samples%8==0) { observed+=byte;checkByte(sent(observed.size-1),byte);byte=0 }
        }
        lastEdge=cycle;edges+=1
      }
    }
    if(lastSelect!=3 && selects==3) {
      require(cycle-lastEdge==half,"SPI_PIN_MODEL CS hold")
      require(edges==16*sent.size && observed.toSeq==sent,"SPI_PIN_MODEL incomplete transfer")
      end=cycle;drive=Some(false)
    }
    lastClock=clock;lastSelect=selects;drive
  }
}

class SpiDriver(val d: SpiBench) extends chisel3.simulator.PeekPokeAPI {
  var cycles = 0
  var peer: Option[SpiPeer] = None
  var stampBase = BigInt(0)
  def high(pin: Bool): Boolean = pin.peek().litValue==1
  def step(n: Int = 1): Unit = for(_ <- 0 until n) {
    d.timeNow.poke(((stampBase+cycles)&BigInt("ffffffff",16)).U)
    d.clk.step();cycles+=1
    peer.foreach(p => p.edge(cycles,high(d.sclk),high(d.mosi),d.cs_n.peek().litValue.toInt)
      .foreach(value => d.miso.poke(value.B)))
  }
  def reset(): Unit = {
    peer=None;d.reset_n.poke(false.B);d.owner.poke(3.U);d.miso.poke(false.B)
    d.sleepRequest.poke(false.B);d.sleepEnable.poke(false.B);d.timeNow.poke(0.U)
    d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
    d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(0.U);d.bus.bits.origin.poke(0.U)
    step(2);d.reset_n.poke(true.B);step(6)
  }
  def access(offset: Int, write: Boolean=false, data: BigInt=0, be: Int=15, origin: Int=3): (BigInt,Boolean) = {
    val p=d.bus;p.req.poke(true.B);p.bits.addr.poke((BigInt("40011000",16)+offset).U)
    p.bits.we.poke(write.B);p.bits.wdata.poke(data.U);p.bits.be.poke(be.U);p.bits.origin.poke(origin.U)
    var granted=false;var done=false;var answer=BigInt(0);var error=false
    for(_ <- 0 until 64 if !done) {
      val accept=high(p.req)&&high(p.gnt)
      if(high(p.rvalid)) { require(granted,"SPI_BUS_MODEL unsolicited response");done=true;answer=p.rdata.peek().litValue;error=high(p.err) }
      step()
      if(accept) {require(!granted,"SPI_BUS_MODEL duplicate grant");granted=true;p.req.poke(false.B)}
    }
    require(done,"SPI_BUS_MODEL timeout")
    if(write||error)require(answer==0,"SPI_BUS_MODEL write/error data")
    p.req.poke(false.B);step(2);(answer,error)
  }
  def rd(offset: Int): BigInt = {val(v,e)=access(offset);require(!e,"SPI_BUS_MODEL read");v}
  def wr(offset: Int, data: BigInt, be: Int=15): Unit = require(!access(offset,true,data,be)._2,"SPI_BUS_MODEL write")
  def configure(mode3: Boolean=false, cs: Int=0, half: Int=3, enable: Boolean=true): Unit = {
    val bits=(if(enable)1 else 0)|(if(mode3)2 else 0)|(cs<<2)
    wr(0,bits);wr(4,half);wr(12,1)
    require(rd(0x24)==((half<<8)|bits),"SPI_CONFIG_MODEL apply")
  }
  def prepare(sent: Seq[Int], replies: Seq[Int], mode3: Boolean=false, cs: Int=0, half: Int=3): SpiPeer = {
    configure(mode3,cs,half);sent.foreach(value => wr(0x10,value));wr(8,sent.size)
    val p=new SpiPeer(mode3,cs,half,sent,replies);peer=Some(p);p
  }
  def finish(p: SpiPeer): Unit = {
    val deadline=cycles+(16*p.sent.size+5)*p.half+32
    while(p.end<0 && cycles<deadline)step()
    require(p.end>=0,"SPI_PIN_MODEL completion deadline")
    step(p.half+3);peer=None
    require(d.cs_n.peek().litValue==3 && high(d.quiescent),"SPI_SLEEP_MODEL not quiescent")
  }
  def checkRx(bytes: Seq[Int]): Unit = {
    for(byte <- bytes) {
      require(rd(0x14)==byte && rd(0x14)==byte,"SPI_QUEUE_MODEL head/order")
      wr(12,4)
    }
    require(rd(0x14)==0 && ((rd(0x18)>>16)&31)==0,"SPI_QUEUE_MODEL empty")
  }
}

object SpiTestFiles {
  def json: String = {
    os.proc("python3","hw/regmap/regmap.py","hw/ip/spi_host/spi_host.regmap.yaml","--out","build/t16/test-regmap").call()
    "build/t16/test-regmap/spi_host_regs.json"
  }
}
