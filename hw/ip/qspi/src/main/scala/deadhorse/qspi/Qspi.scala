package deadhorse.qspi
import chisel3._
import chisel3.util._
import deadhorse.lib._
import deadhorse.qspi_xip.QspiScheduler

class Qspi(json: String,base: BigInt=0,withXip: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val dqIn=IO(Input(UInt(4.W)));val dqOut=IO(Output(UInt(4.W)));val dqEnable=IO(Output(UInt(4.W)))
  val sclk=IO(Output(Bool()));val sclkEnable=IO(Output(Bool()))
  val cs_n=IO(Output(UInt(2.W)));val csEnable=IO(Output(UInt(2.W)));val clockHold=IO(Output(Bool()))
  val xip=if(withXip) Some(IO(new LocalBus)) else None
  protected def permitted(origin: UInt,owner: UInt): Bool=origin===owner
  protected def engine(): QspiEngine=new QspiEngine
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(12,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  val owner=withClockAndReset(clk,(!reset_n).asAsyncReset) {RegInit(0.U(3.W))}
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(permitted(bus.bits.origin,owner),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  val sync=Module(new CdcSync(4));sync.clk:=clk;sync.reset_n:=reset_n;sync.in:=dqIn
  val e=Module(engine());e.clk:=clk;e.reset_n:=reset_n;e.dq:=sync.out
  def q(name: String)=regs.hw(name+"_q")
  val raw=Wire(new QspiCommand)
  raw.select:=q("configuration_chip_select").asBool
  raw.addressBytes:=q("configuration_address_bytes");raw.dataBytes:=q("configuration_data_bytes")
  raw.read:=q("configuration_read_data").asBool
  raw.quadAddress:=q("configuration_quad_address").asBool;raw.quadData:=q("configuration_quad_data").asBool
  raw.halfPeriod:=q("timing_half_period");raw.dummy:=q("timing_dummy_clocks")
  raw.opcode:=q("opcode_value");raw.address:=q("address_value");raw.data:=q("tx_data_value")
  e.command:=raw
  val launch=regs.hw("launch_key_we").asBool;val handoff=regs.hw("handoff_key_we").asBool
  val valid=raw.addressBytes<=4.U && raw.dataBytes<=4.U && raw.halfPeriod>=4.U
  val canStart=WireDefault(!e.busy);val canTransfer=WireDefault(!e.busy)
  val occupied=WireDefault(e.busy);val cmdResult=WireDefault(e.result);val cmdDone=WireDefault(e.done)
  val applyError=WireDefault(false.B)
  val start=launch && !handoff && canStart && valid && regs.hw("launch_key_wdata")==="h51535049".U
  val handoffValue=regs.hw("handoff_key_wdata")
  val transfer=handoff && !launch && canTransfer && (handoffValue==="h4f574e00".U || handoffValue==="h4f574e01".U)
  if(withXip) {
    val scheduler=Module(new QspiScheduler);scheduler.clk:=clk;scheduler.reset_n:=reset_n;scheduler.xip<>xip.get
    scheduler.command:=raw;scheduler.commandValid:=start
    scheduler.engineBusy:=e.busy;scheduler.engineDone:=e.done;scheduler.engineResult:=e.result
    e.command:=scheduler.engineCommand
    val apply=regs.hw("xip_apply_key_we").asBool
    withClockAndReset(clk,(!reset_n).asAsyncReset) {
      val enabled=RegInit(false.B);val config=RegInit(0.U.asTypeOf(new QspiCommand))
      val applyValid=regs.hw("xip_apply_key_wdata")==="h58495021".U &&
        (q("xip_configuration_address_bytes")===3.U || q("xip_configuration_address_bytes")===4.U) &&
        q("xip_timing_half_period")>=4.U
      val permitted=scheduler.idle && !xip.get.req && !launch && !handoff && applyValid
      when(apply && permitted) {
        enabled:=q("xip_configuration_enable").asBool
        config.select:=false.B;config.addressBytes:=q("xip_configuration_address_bytes")
        config.dataBytes:=4.U;config.read:=true.B;config.quadAddress:=q("xip_configuration_quad_address").asBool
        config.quadData:=q("xip_configuration_quad_data").asBool;config.halfPeriod:=q("xip_timing_half_period")
        config.dummy:=q("xip_timing_dummy_clocks");config.opcode:=q("xip_configuration_opcode");config.address:=0.U;config.data:=0.U
      }
      scheduler.enabled:=enabled;scheduler.readConfig:=config
      canStart:=scheduler.commandReady && !apply && (!enabled || raw.select)
      canTransfer:=scheduler.idle && !xip.get.req && !apply
      regs.hw("xip_status_enabled_d"):=enabled.asUInt
      regs.hw("xip_status_busy_d"):=scheduler.busy.asUInt
      applyError:=apply && !permitted
    }
    occupied:=scheduler.busy;cmdResult:=scheduler.commandResult;cmdDone:=scheduler.commandDone
    e.start:=scheduler.engineStart
  } else {e.start:=start}
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    when(transfer) {owner:=handoffValue(2,0)}
    clockHold:=RegNext(occupied || launch || handoff,false.B)
  }
  dqOut:=e.dqOut;dqEnable:=e.dqEnable;sclk:=e.sclk;sclkEnable:=e.pinsEnable
  cs_n:=e.cs_n;csEnable:=Fill(2,e.pinsEnable)
  regs.hw("rx_data_value_d"):=cmdResult;regs.hw("status_busy_d"):=occupied.asUInt
  regs.hw("status_owner_d"):=owner;regs.hw("events_done_set"):=cmdDone.asUInt
  regs.hw("events_command_error_set"):=((launch && !start) || (handoff && !transfer) || applyError).asUInt
}
object EmitQspi extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new Qspi(args(0)),Array("--target-dir",args(1)),
    Array("--disable-all-randomization","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
