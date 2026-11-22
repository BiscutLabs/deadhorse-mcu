package deadhorse.qspi
import chisel3._
import chisel3.util._

class QspiCommand extends Bundle {
  val select=Bool();val addressBytes=UInt(3.W);val dataBytes=UInt(3.W)
  val read=Bool();val quadAddress=Bool();val quadData=Bool()
  val halfPeriod=UInt(8.W);val dummy=UInt(5.W)
  val opcode=UInt(8.W);val address=UInt(32.W);val data=UInt(32.W)
}

/** SCLK is registered output data, never an RTL clock. dq is already sampled
  * through the shared synchronizer in the wrapper. */
class QspiEngine extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val command=IO(Input(new QspiCommand));val dq=IO(Input(UInt(4.W)))
  val busy=IO(Output(Bool()));val done=IO(Output(Bool()));val result=IO(Output(UInt(32.W)))
  val dqOut=IO(Output(UInt(4.W)));val dqEnable=IO(Output(UInt(4.W)))
  val sclk=IO(Output(Bool()));val cs_n=IO(Output(UInt(2.W)));val pinsEnable=IO(Output(Bool()))
  protected def transmit(value: UInt): UInt=value
  protected def chipSelect(value: UInt): UInt=value
  protected def gapReload(half: UInt): UInt=half-1.U
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: opcode :: address :: dummy :: payload :: hold :: gap :: Nil=Enum(7)
    val phase=RegInit(idle);val active=RegInit(false.B);val completed=RegInit(false.B)
    val settings=Reg(new QspiCommand)
    val timer=RegInit(0.U(8.W));val remaining=RegInit(0.U(6.W))
    val quad=RegInit(false.B);val receiving=RegInit(false.B)
    val tx=RegInit(0.U(32.W));val rx=RegInit(0.U(32.W));val published=RegInit(0.U(32.W))
    val clockPin=RegInit(false.B);val selectPin=RegInit(3.U(2.W));val enabled=RegInit(false.B)
    val dataPin=RegInit(0.U(4.W));val dataEnable=RegInit(0.U(4.W))
    busy:=active;done:=completed;result:=published
    sclk:=clockPin;cs_n:=selectPin;pinsEnable:=enabled;dqOut:=dataPin;dqEnable:=dataEnable
    completed:=false.B
    def aligned(value: UInt,bytes: UInt): UInt=MuxLookup(bytes,value)(Seq(
      1.U->Cat(value(7,0),0.U(24.W)),2.U->Cat(value(15,0),0.U(16.W)),3.U->Cat(value(23,0),0.U(8.W))))
    def symbol(value: UInt,q: Bool): UInt=transmit(Mux(q,value(31,28),Cat(3.U(2.W),0.U(1.W),value(31))))
    def enter(p: UInt,value: UInt,count: UInt,q: Bool,rd: Bool,isDummy: Bool=false.B): Unit={
      phase:=p;remaining:=count;quad:=q;receiving:=rd;tx:=value
      dataPin:=Mux(isDummy,0.U,Mux(rd,12.U,symbol(value.pad(32),q)))
      dataEnable:=Mux(isDummy,0.U,Mux(q,Mux(rd,0.U,15.U),Mux(rd,12.U,13.U)))
    }
    def enterData(): Unit={
      when(settings.dataBytes=/=0.U) {
        enter(payload,aligned(settings.data,settings.dataBytes),
          Mux(settings.quadData,settings.dataBytes<<1,settings.dataBytes<<3),settings.quadData,settings.read)
      }.otherwise {phase:=hold;dataEnable:=0.U}
    }
    def afterAddress(): Unit={
      when(settings.dummy=/=0.U) {enter(dummy,0.U,settings.dummy,false.B,false.B,true.B)}
        .otherwise {enterData()}
    }
    when(start && !active) {
      settings:=command;active:=true.B;enabled:=true.B;rx:=0.U
      selectPin:=chipSelect(Mux(command.select,1.U,2.U));clockPin:=false.B
      timer:=command.halfPeriod-1.U
      enter(opcode,Cat(command.opcode,0.U(24.W)),8.U,false.B,false.B)
    }
    when(active) {
      when(timer=/=0.U) {timer:=timer-1.U}.otherwise {
        timer:=settings.halfPeriod-1.U
        when(phase===hold) {selectPin:=3.U;dataEnable:=0.U;dataPin:=0.U;phase:=gap;timer:=gapReload(settings.halfPeriod)}
          .elsewhen(phase===gap) {
            active:=false.B;phase:=idle;completed:=true.B
            published:=Mux(settings.read && settings.dataBytes=/=0.U,rx,0.U)
          }.otherwise {
            clockPin:= !clockPin
            when(!clockPin) {
              when(phase===payload && receiving) {
                rx:=Mux(quad,Cat(rx(27,0),dq),Cat(rx(30,0),dq(1)))
              }
            }.otherwise {
              when(remaining===1.U) {
                when(phase===opcode) {
                  when(settings.addressBytes=/=0.U) {
                    enter(address,aligned(settings.address,settings.addressBytes),
                      Mux(settings.quadAddress,settings.addressBytes<<1,settings.addressBytes<<3),settings.quadAddress,false.B)
                  }.otherwise {afterAddress()}
                }.elsewhen(phase===address) {afterAddress()}
                  .elsewhen(phase===dummy) {enterData()}
                  .otherwise {phase:=hold;dataEnable:=0.U}
              }.otherwise {
                remaining:=remaining-1.U
                val shifted=Mux(quad,Cat(tx(27,0),0.U(4.W)),Cat(tx(30,0),0.U(1.W)))
                tx:=shifted
                when(phase=/=dummy && !receiving) {dataPin:=symbol(shifted,quad)}
              }
            }
          }
      }
    }
  }
}
