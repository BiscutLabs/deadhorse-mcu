package deadhorse.watchdog
import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage

class WatchdogFormal(variant: String) extends RawModule {
  val clk=IO(Input(Clock()));val por_n=IO(Input(Bool()));val reset_n=IO(Input(Bool()))
  val period=IO(Input(UInt(32.W)));val window=IO(Input(UInt(32.W)));val warning=IO(Input(UInt(32.W)))
  val start=IO(Input(Bool()));val feed=IO(Input(Bool()))
  val d=Module[WatchdogChannel](variant match {
    case "early"=>new WatchdogChannel {override protected def earlyViolation(v: Bool): Bool=false.B}
    case "hold"=>new WatchdogChannel {override protected def holdLength: UInt=2.U}
    case "retention"=>new WatchdogChannel {override protected def retainedReset: Bool=this.por_n && this.reset_n}
    case _=>new WatchdogChannel
  })
  d.clk:=clk;d.por_n:=por_n;d.reset_n:=reset_n;d.period:=period;d.window:=window;d.warning:=warning
  d.start:=start;d.feed:=feed
  withClockAndReset(clk,(!por_n).asAsyncReset) {
    val valid=RegNext(true.B,false.B)
    val oldEpoch=RegNext(reset_n,false.B)
    val armed=RegNext(d.active,false.B);val left=RegNext(d.remaining,0.U)
    val wasHeld=RegNext(d.resetHold,false.B);val wasCause=RegNext(d.cause,false.B)
    val count=RegNext(d.crashes,0.U);val oldStart=RegNext(start,false.B);val oldFeed=RegNext(feed,false.B)
    val oldPeriod=RegNext(period);val oldWindow=RegNext(window);val oldWarning=RegNext(warning)
    val capturedPeriod=RegInit(0.U(32.W));val capturedWindow=RegInit(0.U(32.W));val capturedWarning=RegInit(0.U(32.W))
    val accept=reset_n && !d.active && !d.resetHold && start && !feed && period=/=0.U && window<period && warning<period
    when(accept) {capturedPeriod:=period;capturedWindow:=window;capturedWarning:=warning}
    val early=armed && oldFeed && !oldStart && left-1.U>capturedPeriod-capturedWindow
    val expired=oldEpoch && armed && !wasHeld && (left===1.U || early)
    val holdExpected=RegInit(0.U(3.W))
    // Track the required duration from the public reset-hold rising edge.
    when(d.resetHold && !wasHeld) {holdExpected:=3.U}
      .elsewhen(holdExpected=/=0.U) {holdExpected:=holdExpected-1.U}
    if(variant=="cover") {
      cover(d.active && d.warn);cover(early && d.resetHold);cover(expired && !reset_n && d.cause)
      cover(d.cause && !d.resetHold && d.active);cover(d.crashes===2.U)
    } else when(valid) {
      assert(!wasCause || d.cause)
      assert(d.crashes===Mux(expired && !count.andR,count+1.U,count))
      when(expired) {assert(d.resetHold && d.cause)}
      when(wasHeld) {assert(d.resetHold===(holdExpected=/=0.U))}
      when(reset_n && oldEpoch) {
        assert(d.active===(d.remaining=/=0.U))
        assert(!d.active || d.remaining<=capturedPeriod)
        assert(d.warn===(d.active && capturedWarning=/=0.U && d.remaining<=capturedWarning))
        when(armed && !wasHeld) {
          when(expired) {assert(!d.active)}
            .elsewhen(oldFeed && !oldStart) {assert(d.remaining===capturedPeriod)}
            .otherwise {assert(d.remaining===left-1.U)}
          assert(d.error===oldStart)
        }
        when(!armed && !wasHeld && oldStart && !oldFeed && oldPeriod=/=0.U && oldWindow<oldPeriod && oldWarning<oldPeriod) {
          assert(d.active && d.remaining===oldPeriod)
        }
      }
    }
  }
}
object EmitWatchdogFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","early","hold","retention","cover")) {
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new WatchdogFormal(v)),
      Array("--target-dir",s"${args(0)}/$v"),Array("--disable-all-randomization","--disable-opt",
      "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
