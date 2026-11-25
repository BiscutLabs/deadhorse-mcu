package deadhorse.qspi
import chisel3._
import _root_.circt.stage.ChiselStage

class QspiFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val start=IO(Input(Bool()))
  val command=IO(Input(new QspiCommand));val dq=IO(Input(UInt(4.W)))
  val e=Module[QspiEngine](if(variant=="select") new QspiEngine {
    override protected def chipSelect(value: UInt): UInt=0.U
  } else new QspiEngine)
  e.clk:=clock;e.reset_n:=reset_n;e.start:=start;e.dq:=dq;e.command:=command
  // All legal wrapper commands remain represented, without an assume on DUT outputs.
  e.command.addressBytes:=Mux(command.addressBytes>4.U,4.U,command.addressBytes)
  e.command.dataBytes:=Mux(command.dataBytes>4.U,4.U,command.dataBytes)
  e.command.halfPeriod:=Mux(command.halfPeriod<4.U,4.U,command.halfPeriod)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val oldResult=RegNext(e.result,0.U)
    val oldClock=RegNext(e.sclk,false.B);val oldData=RegNext(e.dqOut,0.U)
    val oldEnable=RegNext(e.dqEnable,0.U);val oldCs=RegNext(e.cs_n,3.U)
    if(variant=="cover") {
      cover(e.cs_n===1.U);cover(e.cs_n===2.U)
      cover(e.done && e.result=/=0.U)
      cover(e.cs_n=/=3.U && e.dqEnable===15.U)
      cover(e.cs_n=/=3.U && e.sclk && e.dqEnable===0.U)
    } else {
      assert(e.cs_n===1.U || e.cs_n===2.U || e.cs_n===3.U)
      assert(e.cs_n=/=3.U || !e.sclk)
      assert(e.cs_n===3.U || (e.busy && e.pinsEnable))
      assert(e.busy || (e.cs_n===3.U && !e.sclk && e.dqEnable===0.U))
      assert(!e.done || (!e.busy && e.cs_n===3.U))
      when(past) {
        assert(e.result===oldResult || e.done)
        when(oldClock && e.sclk) {assert(e.dqOut===oldData && e.dqEnable===oldEnable)}
        when(oldCs=/=3.U && e.cs_n=/=3.U) {assert(e.cs_n===oldCs)}
      }
    }
  }
}
class QspiOwnerFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val req=IO(Input(Bool()));val addr=IO(Input(UInt(32.W)));val data=IO(Input(UInt(32.W)))
  val write=IO(Input(Bool()));val be=IO(Input(UInt(4.W)));val origin=IO(Input(UInt(3.W)))
  val d=Module[Qspi](if(variant=="owner") new Qspi("build/t29/qspi/qspi_regs.json") {
    override protected def permitted(o: UInt,current: UInt): Bool=true.B
  } else new Qspi("build/t29/qspi/qspi_regs.json"))
  d.clk:=clock;d.reset_n:=reset_n;d.dqIn:=0.U
  d.bus.req:=req;d.bus.bits.addr:=addr;d.bus.bits.wdata:=data;d.bus.bits.we:=write;d.bus.bits.be:=be
  d.bus.bits.origin:=Mux(origin===1.U,0.U,origin)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    if(variant=="cover") {cover(d.bus.rvalid && d.bus.err)} else {
      assert(!d.sclkEnable && d.csEnable===0.U)
      assert(!d.bus.rvalid || d.bus.err)
    }
  }
}
object EmitQspiFormal extends App {
  require(args.length==2)
  val variants=if(args(0)=="engine") Seq("correct","select","cover") else Seq("correct","owner","cover")
  for(v<-variants) ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(
    if(args(0)=="engine") new QspiFormal(v) else new QspiOwnerFormal(v)),Array("--target-dir",s"${args(1)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
