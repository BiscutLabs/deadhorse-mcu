package deadhorse.aon_gpio

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Lite-owned retained pads. Main ownership request/ack are independent
  * single-bit handshakes per shared pad, not an unqualified data-bus crossing.
  */
class AonGpio(json: String,base: BigInt=0) extends RawModule {
  protected def capture(): CdcPulseCapture=new CdcPulseCapture
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val pinsIn=IO(Input(UInt(6.W)));val pinsOut=IO(Output(UInt(6.W)));val pinsEnable=IO(Output(UInt(6.W)))
  val mainEnables=IO(Input(UInt(3.W)));val mainAck=IO(Input(UInt(3.W)));val mainAvailable=IO(Input(Bool()))
  val ownerRequest=IO(Output(UInt(3.W)));val ownerActive=IO(Output(UInt(3.W)))
  val ownershipBusy=IO(Output(Bool()))
  val spiEnabled=IO(Input(Bool()));val spiBusy=IO(Input(Bool()))
  val spiSelected=IO(Output(Bool()));val irq=IO(Output(Bool()));val wake=IO(Output(Bool()))
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus<>bus;regs.bus<>adapter.registers
  val inputs=Module(new CdcSync(6));inputs.clk:=clk;inputs.reset_n:=reset_n;inputs.in:=pinsIn
  val mainDrive=Module(new CdcSync(3));mainDrive.clk:=clk;mainDrive.reset_n:=reset_n;mainDrive.in:=mainEnables
  val ack=Module(new CdcSync(3));ack.clk:=clk;ack.reset_n:=reset_n;ack.in:=mainAck
  def q(name: String): UInt=regs.hw(name+"_q")
  def offset(name: String): UInt=regs.description.fields.find(_.register==name).get.offset.U
  val pending=Wire(Vec(6,Bool()));val armed=Wire(Vec(6,Bool()))
  for(i<-0 until 6) {
    val c=Module(capture());c.clk:=clk;c.reset_n:=reset_n;c.input:=pinsIn(i)
    c.enable:=q("event_enable_pins")(i);c.falling:=q("polarity_falling")(i)
    c.clear:=regs.hw("clear_events_pins_pulse")(i);pending(i):=c.pending;armed(i):=c.armed
  }
  val request=adapter.registers
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val active=RegInit(0.U(3.W));val spi=RegInit(false.B);val changing=RegInit(false.B)
    val desired=q("mux_aon_owner");val wantSpi=q("mux_spi_enable").asBool
    val newOwner=request.req_wdata(2,0);val newSpi=request.req_wdata(3)
    val muxWrite=request.req_write && request.req_addr===offset("mux") && request.req_wstrb(0)
    val different=newOwner=/=desired || newSpi=/=wantSpi
    val captureChange=request.req_write && request.req_addr===offset("polarity") && request.req_wstrb(0) &&
      ((request.req_wdata(5,0)^q("polarity_falling")) & q("event_enable_pins")).orR
    val unsafeMux=different && (!mainAvailable || changing || mainDrive.out.orR ||
      q("output_enable_pins")(3,0).orR || q("event_enable_pins")(3,0).orR || spiEnabled || spiBusy)
    val deny=captureChange || muxWrite && (unsafeMux || newSpi && newOwner=/=7.U)
    regs.bus.req_addr:=Mux(deny,255.U,request.req_addr)
    val accept=request.req_valid && regs.bus.req_ready
    when(accept && muxWrite && !deny && different) {changing:=true.B}
    val settled=ack.out===desired
    when(changing && settled) {active:=desired;spi:=wantSpi;changing:=false.B}
    // A mux write acknowledges only after the main-domain ownership return.
    // RegBlock retains its response until this handshake completes.
    adapter.registers.rsp_valid:=regs.bus.rsp_valid && !changing
    regs.bus.rsp_ready:=adapter.registers.rsp_ready && !changing
    ownerRequest:=desired;ownerActive:=active;spiSelected:=spi;ownershipBusy:=changing
    val owned=Cat(7.U(3.W),active)
    pinsOut:=q("output_value_pins") & owned
    pinsEnable:=q("output_enable_pins") & owned & Mux(spi,48.U(6.W),63.U(6.W))
    regs.hw("input_value_pins_d"):=inputs.out
    regs.hw("pending_pins_d"):=pending.asUInt;regs.hw("armed_pins_d"):=armed.asUInt
    irq:=RegNext(pending.asUInt.orR,false.B);wake:=RegNext(pending.asUInt.orR,false.B)
  }
}
