package deadhorse.pinmux
import chisel3._
import chisel3.util._
import deadhorse.lib._

/** One registered pad; selection changes insert one disabled sample interval. */
class PinmuxPad(watchdog: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val select=IO(Input(UInt(2.W)));val values=IO(Input(UInt(3.W)));val enables=IO(Input(UInt(3.W)))
  val active=IO(Output(UInt(2.W)));val settling=IO(Output(Bool()))
  val value=IO(Output(Bool()));val enable=IO(Output(Bool()))
  val watchdogReset_n=if(watchdog) Some(IO(Input(Bool()))) else None
  protected def outputEnable(v: Bool): Bool=v
  protected def resetEnable: Bool=false.B
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val chosen=RegInit(0.U(2.W));val changing=select=/=chosen
    val selectedEnable=MuxLookup(select,false.B)((1 to 3).map(i=>i.U->enables(i-1)))
    val selectedValue=MuxLookup(select,false.B)((1 to 3).map(i=>i.U->values(i-1)))
    chosen:=select;active:=chosen;settling:=RegNext(changing,false.B)
    if(watchdog) {
      // Separate banks avoid a selection decode in the asynchronous reset tree.
      val otherEnable=RegNext(outputEnable(!changing && select===1.U && selectedEnable),resetEnable)
      val otherValue=RegNext(!changing && select===1.U && selectedEnable && selectedValue,false.B)
      val (pwmEnable,pwmValue)=withReset((!(reset_n && watchdogReset_n.get)).asAsyncReset) {
        (RegNext(outputEnable(!changing && select>=2.U && selectedEnable),false.B),
         RegNext(!changing && select>=2.U && selectedEnable && selectedValue,false.B))
      }
      enable:=otherEnable || pwmEnable;value:=otherValue || pwmValue
    } else {
      enable:=RegNext(outputEnable(!changing && selectedEnable),resetEnable)
      value:=RegNext(!changing && selectedEnable && selectedValue,false.B)
    }
  }
}

class Pinmux(json: String,base: BigInt=0,watchdog: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val owner=IO(Input(UInt(3.W)))
  val bus=IO(new LocalBus)
  // Source order: GPIO, timer compare, PWM. Each source provides all three pads.
  val values=IO(Input(Vec(3,UInt(3.W))));val enables=IO(Input(Vec(3,UInt(3.W))))
  val timerValues=IO(Input(UInt(12.W)));val timerEnables=IO(Input(UInt(12.W)));val timerRunning=IO(Input(UInt(12.W)))
  val timerInputs=IO(Input(UInt(4.W)))
  val timerOut=IO(Output(UInt(13.W)));val timerEnable=IO(Output(UInt(13.W)))
  val captures=IO(Output(UInt(12.W)));val captureValid=IO(Output(UInt(12.W)))
  val pinsOut=IO(Output(UInt(3.W)));val pinsEnable=IO(Output(UInt(3.W)));val clockHold=IO(Output(Bool()))
  val watchdogReset_n=if(watchdog) Some(IO(Input(Bool()))) else None
  protected def allowed(origin: UInt): Bool=origin===owner
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits;adapter.bus.bits.origin:=Mux(allowed(bus.bits.origin),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  def offset(name: String): UInt=regs.description.fields.find(_.register==name).get.offset.U
  def q(name: String): UInt=regs.hw(name+"_q")
  val routeBusy=WireDefault(false.B)
  val request=adapter.registers
  val invalidRoute=Wire(Vec(17,Bool()))
  def occupied(channel: UInt): Bool=channel<12.U && (timerRunning(channel) || timerEnables(channel))
  val nextChannel=request.req_wdata(3,0)
  for(p<-0 until 13) {
    val selected=q(s"timer_select${p}_channel")
    val captureConflict=if(p<9) false.B else q(s"capture_select${p-9}_channel")=/=15.U && nextChannel=/=15.U
    invalidRoute(p):=request.req_addr===offset(s"timer_select$p") &&
      (nextChannel>=12.U && nextChannel=/=15.U || occupied(selected) || occupied(nextChannel) || captureConflict)
  }
  for(p<-0 until 4) {
    val selected=q(s"capture_select${p}_channel")
    val duplicate=(0 until 4).filter(_!=p).map(i=>q(s"capture_select${i}_channel")===nextChannel).reduce(_||_)
    invalidRoute(13+p):=request.req_addr===offset(s"capture_select$p") &&
      (nextChannel>=12.U && nextChannel=/=15.U || occupied(selected) || occupied(nextChannel) ||
        nextChannel=/=15.U && (duplicate || q(s"timer_select${p+9}_channel")=/=15.U))
  }
  val deny=request.req_write && request.req_wstrb(0) && invalidRoute.asUInt.orR
  regs.bus.req_addr:=Mux(deny,255.U,request.req_addr)
  val inputSync=Module(new CdcSync(4));inputSync.clk:=clk;inputSync.reset_n:=reset_n;inputSync.in:=timerInputs
  val timerPins=Wire(Vec(13,Bool()));val timerDrives=Wire(Vec(13,Bool()))
  val captureValues=Wire(Vec(12,Bool()));val captureArmed=Wire(Vec(12,Bool()))
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val moving=Wire(Vec(17,Bool()))
    for(p<-0 until 13) {
      val requested=q(s"timer_select${p}_channel")
      val chosen=RegNext(requested,15.U(4.W));val changing=requested=/=chosen
      regs.hw(s"timer_active${p}_channel_d"):=chosen
      moving(p):=changing || RegNext(changing,false.B)
      val drive= !changing && requested<12.U && timerEnables(requested)
      withReset((!(reset_n && watchdogReset_n.getOrElse(true.B))).asAsyncReset) {
        timerDrives(p):=RegNext(drive,false.B)
        timerPins(p):=RegNext(drive && timerValues(requested),false.B)
      }
    }
    val selected=(0 until 4).map(p=>q(s"capture_select${p}_channel"))
    val settled=(0 until 4).map {p=>
      val chosen=RegNext(selected(p),15.U(4.W));val changing=selected(p)=/=chosen
      regs.hw(s"capture_active${p}_channel_d"):=chosen
      val stable=RegNext(!changing,false.B)
      moving(13+p):=changing || !stable
      stable && !changing
    }
    for(c<-0 until 12) {
      captureValues(c):=(0 until 4).map(p=>selected(p)===c.U && inputSync.out(p)).reduce(_||_)
      captureArmed(c):=(0 until 4).map(p=>selected(p)===c.U && settled(p)).reduce(_||_)
    }
    routeBusy:=moving.asUInt.orR
    regs.hw("route_events_rejected_set"):=RegNext(request.req_valid && regs.bus.req_ready && deny,false.B).asUInt
  }
  timerOut:=timerPins.asUInt;timerEnable:=timerDrives.asUInt
  captures:=captureValues.asUInt;captureValid:=captureArmed.asUInt
  val pads=(0 until 3).map {i=>
    val p=Module(new PinmuxPad(watchdog));p.clk:=clk;p.reset_n:=reset_n;p.select:=regs.hw(s"select${i}_source_q")
    p.watchdogReset_n.foreach(_:=watchdogReset_n.get)
    p.values:=VecInit(values.map(_(i))).asUInt;p.enables:=VecInit(enables.map(_(i))).asUInt
    regs.hw(s"active${i}_source_d"):=p.active;p
  }
  pinsOut:=VecInit(pads.map(_.value)).asUInt;pinsEnable:=VecInit(pads.map(_.enable)).asUInt
  regs.hw("settling_pads_d"):=VecInit(pads.map(_.settling)).asUInt
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val changing=(0 until 3).map(i=>regs.hw(s"select${i}_source_q")=/=pads(i).active).reduce(_||_)
    clockHold:=RegNext(bus.req || adapter.registers.req_valid || changing || pads.map(_.settling).reduce(_||_) || routeBusy,false.B)
  }
}
object EmitPinmux extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new Pinmux(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
