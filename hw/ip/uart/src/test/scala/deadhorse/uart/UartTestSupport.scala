package deadhorse.uart

import chisel3._
import deadhorse.lib.{LocalBus, ResetRelease}
import scala.collection.mutable.ArrayBuffer

/** Only production public ports cross this test wrapper. */
class UartBench(json: String, fifoDepth: Int = 8) extends RawModule {
  val hf = IO(Input(Clock())); val aon = IO(Input(Clock()))
  val reset_n = IO(Input(Bool())); val wakeReset_n = IO(Input(Bool()))
  val bus = IO(Vec(3, new LocalBus))
  val owner = IO(Input(Vec(3, UInt(3.W)))); val rx = IO(Input(Vec(3, Bool())))
  val sleepRequest = IO(Input(Vec(3, Bool()))); val sleepMode = IO(Input(Vec(3, UInt(2.W))))
  val tx = IO(Output(Vec(3, Bool()))); val txEnable = IO(Output(Vec(3, Bool())))
  val irq = IO(Output(Vec(3, Bool()))); val dmaTxRequest = IO(Output(Vec(3, Bool())))
  val dmaRxRequest = IO(Output(Vec(3, Bool()))); val clockHold = IO(Output(Vec(3, Bool())))
  val quiescent = IO(Output(Vec(3, Bool())))
  val armed = IO(Input(Bool())); val invert = IO(Input(Bool())); val clear = IO(Input(Bool()))
  val wake = IO(Output(Bool())); val wakeClockRequest = IO(Output(Bool()))
  val release = Module(new ResetRelease)
  release.clk := hf; release.reset_n := reset_n
  val bank = Module(new UartBank(json, fifoDepth, Seq.tabulate(3)(i => BigInt("40010000",16)+256*i)))
  bank.clk := hf; bank.reset_n := release.released; bank.bus <> bus
  bank.owner := owner; bank.rx := rx; bank.sleepRequest := sleepRequest; bank.sleepMode := sleepMode
  tx := bank.tx; txEnable := bank.txEnable; irq := bank.irq
  dmaTxRequest := bank.dmaTxRequest; dmaRxRequest := bank.dmaRxRequest
  clockHold := bank.clockHold; quiescent := bank.quiescent
  val monitor = Module(new UartWake)
  monitor.clk := aon; monitor.reset_n := wakeReset_n; monitor.rx := rx(0)
  monitor.armed := armed; monitor.invert := invert; monitor.clear := clear
  wake := monitor.wake; wakeClockRequest := monitor.clockRequest
}

object UartPinModel {
  def increment(hz: Int, baud: Int = 921600): Int = math.round(65536.0*baud/hz).toInt
  def frame(byte: Int, goodStop: Boolean = true): Seq[Boolean] =
    Seq(false) ++ (0 until 8).map(bit => ((byte >> bit)&1)!=0) ++ Seq(goodStop)
  def wave(bytes: Seq[Int], period: Double, inverted: Boolean, goodStop: Boolean = true, phase: Double = 0.0): Vector[Boolean] = {
    val bits = bytes.flatMap(frame(_,goodStop))
    bits.indices.flatMap { bit =>
      // The first observed HF edge is phase edges after the asynchronous start.
      val width = math.ceil((bit+1)*period-phase).toInt-math.ceil(bit*period-phase).toInt
      Seq.fill(width)(bits(bit) ^ inverted)
    }.toVector
  }
  /** Decode centers, then validate every observed bit period against arithmetic
    * edge positions. No replicated accumulator or private design signal. */
  def check(raw: Seq[Boolean], increment: Int, inverted: Boolean, expected: Seq[Int]): Unit = {
    val logical = raw.map(_ ^ inverted)
    val period = 65536.0/increment
    val decoded = ArrayBuffer.empty[Int]
    var cursor = 0
    while(cursor < logical.length) {
      if(logical(cursor)) cursor += 1
      else {
        val start = cursor
        val length = math.ceil(10*period).toInt
        require(start+length <= logical.length,"UART_PIN_MODEL truncated frame")
        val sampled = (0 until 10).map(bit => logical(start+math.floor((bit+0.5)*period).toInt))
        require(!sampled.head && sampled.last,"UART_PIN_MODEL start/stop")
        for(bit <- 0 until 10; offset <- math.ceil(bit*period).toInt until math.ceil((bit+1)*period).toInt)
          require(logical(start+offset)==sampled(bit),s"UART_PIN_MODEL bit boundary $bit at ${start+offset}")
        decoded += (0 until 8).map(bit => if(sampled(bit+1))1<<bit else 0).sum
        cursor += length
      }
    }
    require(decoded.toSeq==expected,s"UART_PIN_MODEL bytes ${decoded.toSeq} != $expected")
  }
  def checkHead(expected: Int, observed: BigInt): Unit =
    require(observed==expected,s"UART_QUEUE_MODEL $observed != $expected")
}

class UartDriver(val d: UartBench) extends chisel3.simulator.PeekPokeAPI {
  def high(b: Bool): Boolean = b.peek().litValue==1
  var clocks = 0
  var capture = false
  val traces = Array.fill(3)(ArrayBuffer.empty[Boolean])
  private val scripts = Array.fill[Vector[Boolean]](3)(Vector.empty)
  private val scriptIndex = Array.fill(3)(0)
  private val idle = Array.fill(3)(true)
  def step(n: Int = 1): Unit = {
    if(!capture && scripts.forall(_.isEmpty)) { d.hf.step(n); clocks += n }
    else for(_ <- 0 until n) {
      for(i <- 0 until 3 if scripts(i).nonEmpty) d.rx(i).poke(scripts(i)(scriptIndex(i)).B)
      d.hf.step(); clocks += 1
      if(capture) for(i <- 0 until 3) traces(i) += high(d.tx(i))
      for(i <- 0 until 3 if scripts(i).nonEmpty) {
        scriptIndex(i) += 1
        if(scriptIndex(i)==scripts(i).length) { scripts(i)=Vector.empty; d.rx(i).poke(idle(i).B) }
      }
    }
  }
  def reset(): Unit = {
    capture=false
    d.reset_n.poke(false.B); d.wakeReset_n.poke(false.B)
    d.armed.poke(false.B); d.invert.poke(false.B); d.clear.poke(false.B)
    for(i <- 0 until 3) {
      scripts(i)=Vector.empty; d.rx(i).poke(true.B); idle(i)=true
      d.owner(i).poke((i+1).U); d.sleepRequest(i).poke(false.B); d.sleepMode(i).poke(0.U)
      d.bus(i).req.poke(false.B); d.bus(i).bits.addr.poke(0.U)
      d.bus(i).bits.we.poke(false.B); d.bus(i).bits.be.poke(0.U)
      d.bus(i).bits.wdata.poke(0.U); d.bus(i).bits.origin.poke(0.U)
    }
    step(2); d.aon.step(2); d.reset_n.poke(true.B); d.wakeReset_n.poke(true.B)
    step(8); d.aon.step(8)
  }
  def access(i: Int, offset: Int, write: Boolean=false, data: BigInt=0, be: Int=15, origin: Int = -1): (BigInt,Boolean) = {
    val p=d.bus(i)
    p.req.poke(true.B); p.bits.addr.poke((BigInt("40010000",16)+256*i+offset).U)
    p.bits.we.poke(write.B); p.bits.wdata.poke(data.U); p.bits.be.poke(be.U)
    p.bits.origin.poke((if(origin<0)i+1 else origin).U)
    var granted=false; var done=false; var answer=BigInt(0); var error=false
    for(_ <- 0 until 64 if !done) {
      val accepted=high(p.req)&&high(p.gnt)
      if(high(p.rvalid)) {
        require(granted,"UART_BUS_MODEL unsolicited response")
        answer=p.rdata.peek().litValue; error=high(p.err); done=true
      }
      step()
      if(accepted) { require(!granted,"UART_BUS_MODEL duplicate grant"); granted=true; p.req.poke(false.B) }
    }
    require(done,"UART_BUS_MODEL deadline")
    if(write||error) require(answer==0,"UART_BUS_MODEL write/error data")
    p.req.poke(false.B); step(4); (answer,error)
  }
  def rd(i: Int, offset: Int): BigInt = {val(v,e)=access(i,offset);require(!e,"UART_BUS_MODEL read error");v}
  def wr(i: Int, offset: Int, data: BigInt, be: Int=15): Unit =
    require(!access(i,offset,true,data,be)._2,"UART_BUS_MODEL write error")
  def configure(i: Int, increment: Int, tx: Boolean=true, rx: Boolean=true, inverted: Boolean=false): Unit = {
    d.rx(i).poke((!inverted).B); idle(i)= !inverted
    val config=(if(tx)1 else 0)|(if(rx)2 else 0)|(if(inverted)4 else 0)
    wr(i,0,config); wr(i,4,increment); wr(i,8,1)
    require(rd(i,0x20)==((BigInt(increment)<<16)|config),"UART_CONFIG_MODEL apply")
  }
  def beginCapture(): Unit = {
    for(i <- 0 until 3) {traces(i).clear();traces(i)+=high(d.tx(i))}
    capture=true
  }
  def schedule(i: Int, bytes: Seq[Int], period: Double, inverted: Boolean=false, goodStop: Boolean=true, phase: Double=0.0): Int = {
    require(scripts(i).isEmpty,"UART_TEST overlapping peer sender")
    scripts(i)=UartPinModel.wave(bytes,period,inverted,goodStop,phase);scriptIndex(i)=0;idle(i)= !inverted
    scripts(i).length
  }
  def send(i: Int, bytes: Seq[Int], period: Double, inverted: Boolean=false, goodStop: Boolean=true, phase: Double=0.0): Unit = {
    val duration=schedule(i,bytes,period,inverted,goodStop,phase)
    step(duration+math.ceil(period).toInt+8)
  }
  def pop(i: Int): Unit = wr(i,8,2)
  def checkBytes(i: Int, bytes: Seq[Int]): Unit = {
    for(byte <- bytes) {UartPinModel.checkHead(byte,rd(i,0x10));UartPinModel.checkHead(byte,rd(i,0x10));pop(i)}
    require(rd(i,0x10)==0 && ((rd(i,0x14)>>16)&31)==0,"UART_QUEUE_MODEL empty")
  }
}
