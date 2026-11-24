package deadhorse.sram

import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils

/** Pins of the actual hard-macro binding, with arbitrary addresses/data/masks.
  * Macro internals are outside this wiring proof; no memory-data assumption. */
class SramPinsFormal(fault: Boolean=false) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val address=IO(Input(UInt(10.W)));val data=IO(Input(UInt(32.W)))
  val mask=IO(Input(UInt(4.W)));val enable=IO(Input(Bool()));val write=IO(Input(Bool()))
  val d=Module(new SramWordBank(target=SramTarget.Asic) {
    override protected def lane(i: Int): Int=if(fault) (i+1)%4 else i
  })
  d.clk:=clock;d.port.address:=address;d.port.data:=data;d.port.mask:=mask
  d.port.enable:=enable;d.port.write:=write
  for((cell,i)<-d.physical.zipWithIndex) {
    val cen=BoringUtils.bore(cell.io.CEN);val gwen=BoringUtils.bore(cell.io.GWEN)
    val wen=BoringUtils.bore(cell.io.WEN);val a=BoringUtils.bore(cell.io.A);val value=BoringUtils.bore(cell.io.D)
    withClockAndReset(clock,(!reset_n).asAsyncReset) {
      assert(cen=== !enable);assert(gwen=== !write);assert(wen===Fill(8,!mask(i)))
      assert(a===address);assert(value===data(8*i+7,8*i))
    }
  }
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    cover(enable && write && mask===5.U && address===1023.U)
    cover(enable && !write && address===768.U)
  }
}

/** Full production depth; an arbitrary constant witness does not constrain any
  * DUT input. Only explicitly written lanes may be compared to an oracle. */
class SramDataFormal extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val address=IO(Input(UInt(10.W)));val data=IO(Input(UInt(32.W)))
  val mask=IO(Input(UInt(4.W)));val enable=IO(Input(Bool()));val write=IO(Input(Bool()))
  val witness=IO(Input(UInt(10.W)))
  val d=Module(new SramWordBank)
  d.clk:=clock;d.port.address:=address;d.port.data:=data;d.port.mask:=mask
  d.port.enable:=enable;d.port.write:=write
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B);val previous=RegNext(witness)
    when(past) {assume(witness===previous)}
    val known=RegInit(0.U(4.W));val value=Reg(Vec(4,UInt(8.W)))
    when(enable && write && address===witness) {
      known:=known|mask
      for(i<-0 until 4) when(mask(i)) {value(i):=data(8*i+7,8*i)}
    }
    val check=RegNext(enable && !write && address===witness,false.B)
    val expected=RegNext(value.asUInt);val defined=RegNext(known,0.U)
    for(i<-0 until 4) when(check && defined(i)) {assert(d.port.result(8*i+7,8*i)===expected(8*i+7,8*i))}
    cover(check && defined===15.U)
    cover(check && defined===5.U)
  }
}

class SramMarchFormal(fault: Boolean=false) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val run=IO(Input(Bool()));val permitted=IO(Input(Bool()));val data=IO(Input(UInt(32.W)))
  val d=Module(new SramMarch(8) {
    override protected def completed(last: Bool): Bool=if(fault) true.B else last
  })
  d.clk:=clock;d.reset_n:=reset_n;d.run:=run;d.permitted:=permitted;d.memory.result:=data
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val operations=RegInit(0.U(8.W))
    when(!run) {operations:=0.U}.elsewhen(d.memory.enable) {operations:=operations+1.U}
    assert(!d.done || operations===80.U)
    assert(operations<=80.U)
    assert(!d.memory.enable || d.busy && permitted && run)
    cover(d.done && !d.result.failed)
    cover(d.done && d.result.failed)
  }
}

object EmitSramFormal extends App {
  for((name,make)<-Seq[(String,()=>RawModule)](
    "pins"->(()=>new SramPinsFormal),"wrong-lane"->(()=>new SramPinsFormal(true)),
    "data"->(()=>new SramDataFormal),"march"->(()=>new SramMarchFormal),
    "early"->(()=>new SramMarchFormal(true)))) {
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(make()),
      Array("--target-dir",s"${args(0)}/$name"),Array("--disable-all-randomization","--disable-opt",
        "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
