package deadhorse.aon_spi

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** LF-domain framed SPI. SCLK is an output datum, never an RTL clock.
  * MISO uses the shared synchronizer. Sample/byte tokens follow its latency,
  * allowing a one-AON-edge half-period without sampling the previous bit.
  */
class AonSpi(json: String,base: BigInt=0,formalChecks: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val miso=IO(Input(Bool()));val sclk=IO(Output(Bool()));val mosi=IO(Output(Bool()))
  val cs_n=IO(Output(Bool()));val pinsEnable=IO(Output(Bool()));val irq=IO(Output(Bool()))
  protected def transmit(value: Bool): Bool=value
  protected def receive(value: UInt): UInt=value
  protected def txWriteIndex(value: UInt): UInt=value
  protected def rxWriteIndex(value: UInt): UInt=value
  protected def frameSelected(value: Bool): Bool=value
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus<>bus;regs.bus<>adapter.registers
  val input=Module(new CdcSync(1));input.clk:=clk;input.reset_n:=reset_n;input.in:=miso.asUInt
  def offset(name: String): UInt=regs.description.fields.find(_.register==name).get.offset.U
  def q(name: String): UInt=regs.hw(name+"_q")
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val active=RegInit(false.B);val draining=RegInit(false.B)
    val cp=RegInit(false.B);val dp=RegInit(false.B);val select=RegInit(true.B)
    val phase=RegInit(0.U(4.W));val ticks=RegInit(0.U(16.W));val half=RegInit(1.U(16.W))
    val mode=RegInit(false.B);val left=RegInit(0.U(4.W))
    val tx=Reg(Vec(8,UInt(8.W)));val rx=Reg(Vec(8,UInt(8.W)))
    val tr=RegInit(0.U(3.W));val tw=RegInit(0.U(3.W))
    val rr=RegInit(0.U(3.W));val rw=RegInit(0.U(3.W))
    val tc=RegInit(0.U(4.W));val rc=RegInit(0.U(4.W))
    val txShift=RegInit(0.U(8.W));val rxShift=RegInit(0.U(8.W))
    val busy=active || draining
    val request=adapter.registers
    val configWrite=request.req_write && Seq("control","divider","length").map(n=>request.req_addr===offset(n)).reduce(_||_)
    val txWrite=request.req_write && request.req_addr===offset("tx_data") && request.req_wstrb(0)
    val rxRead= !request.req_write && request.req_addr===offset("rx_data")
    val deny=busy && configWrite || txWrite && tc===8.U || rxRead && rc===0.U
    // Invalid access goes through the generated unmapped-address response.
    // No generated register or FIFO is updated by a rejected request.
    regs.bus.req_addr:=Mux(deny,255.U,request.req_addr)
    val accepted=request.req_valid && regs.bus.req_ready
    val denied=RegNext(accepted && deny,false.B)
    val pop=accepted && rxRead && !deny
    val push=regs.hw("tx_data_value_we").asBool
    val command=regs.hw("start_go_pulse").asBool
    val length=q("length_bytes")
    val start=command && !busy && q("control_enable").asBool && q("divider_ticks")=/=0.U &&
      length=/=0.U && length<=8.U && tc>=length && (rc+&length)<=8.U
    val edge=active && ticks===0.U
    val byteEnd=edge && phase===15.U
    val sample=edge && phase(0)===mode
    val sampleDelayed=RegNext(RegNext(sample,false.B),false.B)
    val byteDelayed=RegNext(RegNext(byteEnd,false.B),false.B)
    val lastDelayed=RegNext(RegNext(byteEnd && left===1.U,false.B),false.B)
    val receiveWord=Cat(rxShift(6,0),input.out.asBool)
    val consume=start || byteEnd && left>1.U
    when(!busy) {cp:=q("control_mode3").asBool;dp:=false.B}
    when(start) {
      active:=true.B;select:=false.B;mode:=q("control_mode3").asBool
      half:=q("divider_ticks");ticks:=q("divider_ticks")-1.U;phase:=0.U;left:=length
      txShift:=tx(tr);dp:=transmit(Mux(q("control_mode3").asBool,false.B,tx(tr)(7)))
      rxShift:=0.U
    }
    when(active) {
      when(ticks=/=0.U) {ticks:=ticks-1.U}.otherwise {
        ticks:=half-1.U;phase:=phase+1.U;cp:=Mux(phase(0),mode,!mode)
        when(!phase(0) && mode) {dp:=transmit(txShift(7));txShift:=Cat(txShift(6,0),0.U(1.W))}
        when(phase(0) && !mode && !byteEnd) {dp:=transmit(txShift(6));txShift:=Cat(txShift(6,0),0.U(1.W))}
        when(byteEnd) {
          left:=left-1.U
          when(left===1.U) {active:=false.B;draining:=true.B}
            .otherwise {txShift:=tx(tr);when(!mode) {dp:=transmit(tx(tr)(7))}}
        }
      }
    }
    when(sampleDelayed) {rxShift:=receiveWord}
    when(byteDelayed) {
      rx(rxWriteIndex(rw)):=receive(Mux(mode,receiveWord,rxShift));rw:=rw+1.U;rxShift:=0.U
    }
    when(lastDelayed) {draining:=false.B;select:=true.B;dp:=false.B}
    when(push) {tx(txWriteIndex(tw)):=regs.hw("tx_data_value_wdata");tw:=tw+1.U}
    when(consume) {tr:=tr+1.U}
    when(push =/= consume) {tc:=Mux(push,tc+1.U,tc-1.U)}
    when(pop) {rr:=rr+1.U}
    when(byteDelayed =/= pop) {rc:=Mux(byteDelayed,rc+1.U,rc-1.U)}
    regs.hw("status_busy_d"):=busy.asUInt
    regs.hw("status_tx_level_d"):=tc;regs.hw("status_rx_level_d"):=rc
    regs.hw("rx_data_value_d"):=Mux(rc=/=0.U,rx(rr),0.U)
    regs.hw("events_complete_set"):=lastDelayed.asUInt
    regs.hw("events_error_set"):=(denied || command && !start).asUInt
    irq:=RegNext((Cat(q("events_error"),q("events_complete")) & q("irq_enable_events")).orR,false.B)
    sclk:=cp;mosi:=dp;cs_n:=frameSelected(select)
    pinsEnable:=RegNext(q("control_enable").asBool,false.B)
    assert(tc<=8.U && rc<=8.U)
    assert(!consume || tc=/=0.U)
    assert(!pop || rc=/=0.U)
    assert(!byteDelayed || rc<8.U || pop)
    assert(!active || !select)
    if(formalChecks) {
      // Independent shift queues: prove every live FIFO byte, including wrap
      // and simultaneous read/write, against the ring implementation.
      val txReference=Reg(Vec(8,UInt(8.W)));val rxReference=Reg(Vec(8,UInt(8.W)))
      for(i<-0 until 8) {
        when(consume) {txReference(i):=(if(i==7) 0.U else txReference(i+1))}
        when(pop) {rxReference(i):=(if(i==7) 0.U else rxReference(i+1))}
        when(push && (tc-consume.asUInt)===i.U) {txReference(i):=regs.hw("tx_data_value_wdata")}
        when(byteDelayed && (rc-pop.asUInt)===i.U) {rxReference(i):=Mux(mode,receiveWord,rxShift)}
        when(i.U<tc) {assert(tx((tr+i.U)(2,0))===txReference(i))}
        when(i.U<rc) {assert(rx((rr+i.U)(2,0))===rxReference(i))}
      }
      // The data oracle checks queue ordering; wire sampling is independently
      // checked by AonSpiSpec's radio model, not assumed here.
      val framing=RegInit(false.B)
      when(start) {framing:=true.B}
      when(lastDelayed) {framing:=false.B}
      assert(cs_n=== !framing)
      assert(active || draining || cs_n)
      assert(!busy || pinsEnable)
      cover(tc===8.U && tr=/=0.U)
      cover(rc===8.U && rr=/=0.U)
      cover(lastDelayed)
    }
  }
}
