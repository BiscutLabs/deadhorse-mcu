package deadhorse.qspi_xip
import chisel3._
import chisel3.util._
import deadhorse.lib.LocalBus
import deadhorse.qspi.QspiCommand

/** One slot per producer; commands and native reads share complete frames. */
class QspiScheduler extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val xip=IO(new LocalBus);val enabled=IO(Input(Bool()));val readConfig=IO(Input(new QspiCommand))
  val command=IO(Input(new QspiCommand));val commandValid=IO(Input(Bool()))
  val commandReady=IO(Output(Bool()));val commandDone=IO(Output(Bool()));val commandResult=IO(Output(UInt(32.W)))
  val engineBusy=IO(Input(Bool()));val engineDone=IO(Input(Bool()));val engineResult=IO(Input(UInt(32.W)))
  val engineStart=IO(Output(Bool()));val engineCommand=IO(Output(new QspiCommand))
  val busy=IO(Output(Bool()));val idle=IO(Output(Bool()))
  protected def nativeWord(value: UInt): UInt=Cat(value(7,0),value(15,8),value(23,16),value(31,24))
  protected def nextPreference(wasRead: Bool): Bool= !wasRead
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val waiting :: launching :: running :: retire :: Nil=Enum(4)
    val state=RegInit(waiting);val preferRead=RegInit(true.B);val currentRead=RegInit(false.B)
    val cmdPending=RegInit(false.B);val readPending=RegInit(false.B)
    val cmdFree=RegInit(true.B);val readOccupied=RegInit(false.B)
    val capturedCommand=Reg(new QspiCommand);val capturedRead=Reg(new QspiCommand)
    val activeCommand=Reg(new QspiCommand);val startPulse=RegInit(false.B)
    val cmdDone=RegInit(false.B);val cmdResult=RegInit(0.U(32.W))
    val grant=RegInit(false.B);val response=RegInit(false.B);val result=RegInit(0.U(32.W));val error=RegInit(false.B)
    val work=RegInit(false.B);val quiet=RegInit(false.B)
    engineStart:=startPulse;engineCommand:=activeCommand
    commandReady:=cmdFree;commandDone:=cmdDone;commandResult:=cmdResult;busy:=work;idle:=quiet
    xip.gnt:=grant;xip.rvalid:=response;xip.rdata:=result;xip.err:=error
    startPulse:=false.B;cmdDone:=false.B;response:=false.B
    val acceptRead=xip.req && grant
    val acceptCommand=commandValid && cmdFree
    grant:= !readOccupied && !response
    quiet:=state===waiting && !cmdPending && !readPending && !engineBusy && !response && !cmdDone &&
      !acceptRead && !acceptCommand
    when(state===waiting && !cmdPending && !readPending && !acceptRead && !acceptCommand) {work:=false.B}
    when(acceptCommand) {capturedCommand:=command;cmdPending:=true.B;cmdFree:=false.B;work:=true.B}
    when(acceptRead) {
      grant:=false.B
      val inRange=xip.bits.addr>="h10000000".U && xip.bits.addr<"h20000000".U
      val representable=readConfig.addressBytes===4.U || xip.bits.addr(27,24)===0.U
      val legal=enabled && inRange && !xip.bits.addr(1,0).orR && !xip.bits.we && xip.bits.origin===1.U && representable
      when(legal) {
        capturedRead:=readConfig;capturedRead.select:=false.B;capturedRead.read:=true.B
        capturedRead.dataBytes:=4.U;capturedRead.address:=Cat(0.U(4.W),xip.bits.addr(27,0))
        readPending:=true.B;readOccupied:=true.B;work:=true.B
      }.otherwise {response:=true.B;result:=0.U;error:=true.B}
    }
    when(state===waiting && (cmdPending || readPending)) {
      val useRead=readPending && (!cmdPending || preferRead)
      activeCommand:=Mux(useRead,capturedRead,capturedCommand);currentRead:=useRead
      when(useRead) {readPending:=false.B}.otherwise {cmdPending:=false.B}
      startPulse:=true.B;state:=launching
    }
    when(state===launching) {state:=running}
    when(state===running && engineDone) {
      preferRead:=nextPreference(currentRead)
      when(currentRead) {result:=nativeWord(engineResult);error:=false.B;response:=true.B;readOccupied:=false.B}
        .otherwise {cmdResult:=engineResult;cmdDone:=true.B;cmdFree:=true.B}
      state:=retire
    }
    when(state===retire) {state:=waiting}
  }
}
