package deadhorse.dma
import chisel3._
import chisel3.util._
import deadhorse.lib._

class Dma(json: String,endpoints: DmaEndpoints,memoryBase: BigInt,memorySize: BigInt,base: BigInt=0) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val owner=IO(Input(UInt(3.W)))
  val bus=IO(new LocalBus);val memory=IO(Flipped(new LocalBus));val peripheral=IO(Flipped(new LocalBus))
  val requests=IO(Input(UInt(17.W)));val pwmAck=IO(Output(UInt(9.W)))
  val irq=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  protected def allowed(origin: UInt): Bool=origin===owner
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits;adapter.bus.bits.origin:=Mux(allowed(bus.bits.origin),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val engine=Module(new DmaEngine(endpoints,memoryBase,memorySize))
  engine.clk:=clk;engine.reset_n:=reset_n;engine.owner:=owner;engine.requests:=requests
  engine.start:=regs.hw("start_channels_pulse");engine.abort:=regs.hw("abort_channels_pulse")
  for(i<-0 until 4) {
    engine.settings(i).address:=regs.hw(s"address${i}_value_q")
    engine.settings(i).count:=regs.hw(s"count${i}_value_q")
    engine.settings(i).endpoint:=regs.hw(s"endpoint${i}_value_q")
    regs.hw(s"remaining${i}_value_d"):=engine.remaining(i)
    regs.hw(s"current${i}_value_d"):=engine.current(i)
    regs.hw(s"fault${i}_phase_d"):=engine.fault(i)
  }
  memory<>engine.memory;peripheral<>engine.peripheral;pwmAck:=engine.pwmAck;clockHold:=engine.clockHold
  regs.hw("busy_channels_d"):=engine.busy
  regs.hw("events_done_set"):=engine.done;regs.hw("events_error_set"):=engine.failed
  regs.hw("events_config_error_set"):=engine.rejected;regs.hw("events_aborted_set"):=engine.aborted
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val events=Cat(regs.hw("events_aborted_q"),regs.hw("events_config_error_q"),regs.hw("events_error_q"),regs.hw("events_done_q"))
    irq:=RegNext((events & regs.hw("irq_enable_events_q")).orR,false.B)
  }
}

object DmaStandalone {
  private val uarts=Seq(BigInt(0x40010000L),BigInt(0x40010100L),BigInt(0x40010200L))
  private val spi=BigInt(0x40010300L);private val pwm=BigInt(0x40030000L)
  val endpoints=DmaEndpoints(uarts.flatMap(b=>Seq(b+12,b+16))++Seq(spi+16,spi+20)++(0 until 9).map(i=>pwm+0xc0+4*i),
    uarts.flatMap(b=>Seq(b+8,b+8))++Seq(spi+12,spi+12)++Seq.fill(9)(pwm),
    Seq(0,2,0,2,0,2,0,4).map(BigInt(_))++(0 until 9).map(i=>BigInt(1)<<i),
    (0 until 9).map(i=>pwm+0x40+4*i),pwm+12)
  val memoryBase=BigInt(0x20000000L);val memorySize=BigInt(16384)
}
object EmitDma extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    new Dma(args(0),DmaStandalone.endpoints,DmaStandalone.memoryBase,DmaStandalone.memorySize),
    Array("--target-dir",args(1)),Array("--disable-all-randomization","--strip-debug-info",
      "--verification-flavor=immediate","--lower-to-core"))
}
