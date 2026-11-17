package deadhorse.uart

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

/** Real production fault hooks, never part of a production instance. */
class UartBadTx(json: String) extends Uart(json, 2) {
  override protected def txValue(value: Bool): Bool = !value
}
class UartBadWake extends UartWake {
  override protected def wakeValue(value: Bool): Bool = !value
}
class UartBadOwner(json: String) extends Uart(json,2) {
  override protected def accessAllowed(origin: UInt, selected: UInt): Bool = true.B
}

class UartPhaseFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val left=IO(Input(UInt(16.W))); val right=IO(Input(UInt(16.W)))
  val sum=UartPhase.add(left,right)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    if(variant=="cover") { cover(left === 65535.U && right === 1.U && sum === 65536.U) }
    else { assert((if(variant=="corrupt") sum ^ 1.U else sum) === (left +& right)) }
  }
}

/** All non-owner origin tags, arbitrary addresses/data/strobes and request
  * timing. The owner is zero; mapped input tags cover every tag 1 through 7.
  */
class UartDeniedFormal(json: String, variant: String) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val bus=IO(new deadhorse.lib.LocalBus)
  val d=Module(if(variant=="corrupt") new UartBadOwner(json) else new Uart(json,2))
  d.clk:=clock;d.reset_n:=reset_n;d.owner:=0.U;d.rx:=true.B
  d.sleepRequest:=false.B;d.sleepMode:=0.U;d.bus<>bus
  d.bus.bits.origin:=Mux(bus.bits.origin===0.U,1.U,bus.bits.origin)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val granted=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") {
      cover(bus.rvalid && bus.err)
      cover(bus.rvalid && bus.err && bus.req)
    } else {
      assert(bus.rvalid===granted)
      when(bus.rvalid) { assert(bus.err); assert(bus.rdata===0.U) }
      assert(!d.txEnable); assert(d.tx); assert(!d.irq)
      assert(!d.dmaTxRequest); assert(!d.dmaRxRequest)
    }
  }
}

/** A public-pin frame contract for a specified configuration. The bus master
  * writes a legal 8-edge bit period, enables TX, and sends one arbitrary byte.
  * This is bounded configured frame evidence, not arbitrary-software coverage.
  */
class UartFrameFormal(json: String, variant: String) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val byte = IO(Input(UInt(8.W)))
  val d = Module(if(variant == "corrupt") new UartBadTx(json) else new Uart(json,2))
  d.clk := clock; d.reset_n := reset_n; d.rx := true.B
  d.owner := 0.U; d.sleepRequest := false.B; d.sleepMode := 0.U
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val state = RegInit(0.U(4.W)); val waiting = RegInit(false.B)
    val payload = RegInit(0.U(8.W)); val settle = RegInit(0.U(3.W))
    when(settle =/= 7.U) { settle := settle + 1.U }
    val go = settle === 7.U && state < 4.U
    d.bus.req := go && !waiting
    d.bus.bits.addr := MuxLookup(state,0.U)(Seq(0.U->4.U,1.U->0.U,2.U->8.U,3.U->12.U))
    d.bus.bits.we := true.B; d.bus.bits.be := 15.U; d.bus.bits.origin := 0.U
    d.bus.bits.wdata := MuxLookup(state,0.U)(Seq(0.U->8192.U,1.U->1.U,2.U->1.U,3.U->byte.pad(32)))
    when(d.bus.req && d.bus.gnt) {
      waiting := true.B
      when(state === 3.U) { payload := byte }
    }
    when(d.bus.rvalid) { waiting := false.B; state := state + 1.U }
    val outstanding = RegInit(false.B)
    when(d.bus.req && d.bus.gnt) { outstanding := true.B }
    when(d.bus.rvalid) { outstanding := false.B }
    val started = RegInit(false.B); val completed = RegInit(false.B)
    val elapsed = RegInit(0.U(7.W))
    when(!started && d.txEnable && !d.tx) { started := true.B; elapsed := 1.U }
    when(started && !completed) {
      when(elapsed === 80.U) { completed := true.B }
        .otherwise { elapsed := elapsed + 1.U }
    }
    val index = elapsed >> 3
    val expected = Mux(index === 0.U,false.B,Mux(index <= 8.U,payload((index-1.U)(2,0)),true.B))
    if(variant == "cover") {
      cover(completed && payload === "hA5".U && d.tx)
      cover(started && elapsed === 40.U && !d.quiescent)
    } else {
      when(d.bus.rvalid) { assert(outstanding); assert(!d.bus.err) }
      when(started && !completed) { assert(d.tx === expected); assert(d.txEnable) }
      when(started && elapsed > 1.U && elapsed < 80.U) { assert(d.clockHold) }
      when(completed) { assert(d.tx) }
    }
  }
}

/** Single AON domain, arbitrary input levels/config/reset. Capture obligation
  * is conditioned only on the documented four-edge settled active input.
  */
class UartWakeFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val rx=IO(Input(Bool())); val armed=IO(Input(Bool()))
  val invert=IO(Input(Bool())); val clear=IO(Input(Bool()))
  val d=Module(if(variant=="corrupt") new UartBadWake else new UartWake)
  d.clk:=clock; d.reset_n:=reset_n; d.rx:=rx; d.armed:=armed; d.invert:=invert; d.clear:=clear
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val active= !(rx ^ invert)
    val activeHistory=RegInit(0.U(4.W)); val armHistory=RegInit(0.U(4.W))
    val up=RegInit(0.U(5.W))
    up:=Cat(up(3,0),true.B)
    activeHistory:=Cat(activeHistory(2,0),active)
    armHistory:=Cat(armHistory(2,0),armed)
    val oldWake=RegNext(d.wake,false.B); val oldClear=RegNext(clear,false.B)
    if(variant=="cover") {
      cover(up.andR && d.wake && !armed)
      cover(up.andR && activeHistory.andR && armHistory.andR && clear && d.wake)
    } else {
      when(up.andR && oldWake && !oldClear) { assert(d.wake) }
      when(up.andR && activeHistory.andR && armHistory.andR) { assert(d.wake) }
      assert(d.clockRequest === d.wake)
    }
  }
}

object EmitUartFormal {
  def main(args: Array[String]): Unit = {
    require(args.length==3,"EmitUartFormal <json> <frame|wake|denied|phase> build/<output>")
    val root=Paths.get(args(2)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for(variant<-Seq("correct","corrupt","cover")) {
      val dir=root.resolve(variant);Files.createDirectories(dir)
      def design: RawModule=args(1) match {
        case "frame" => new UartFrameFormal(args(0),variant)
        case "wake" => new UartWakeFormal(variant)
        case "denied" => new UartDeniedFormal(args(0),variant)
        case "phase" => new UartPhaseFormal(variant)
      }
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(design),
        Array("--target-dir",dir.toString),Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
    }
  }
}
