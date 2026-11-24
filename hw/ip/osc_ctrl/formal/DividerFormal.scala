package deadhorse.osc_ctrl

import chisel3._

/** Initialize the monitor only. The DUT phase/state and functional reset remain
  * arbitrary. After an observed transition, every high pulse has three source
  * periods; reset may extend a low pulse but cannot shorten it. */
class DividerFormal(fault: Boolean=false) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val monitorReset=IO(Input(Bool()))
  val d=Module[OscDivider](if(fault) new OscDivider {
    override protected def terminal(value: Bool): Bool= !value
  } else new OscDivider)
  d.clk:=clock;d.reset_n:=reset_n
  withClockAndReset(clock,monitorReset.asAsyncReset) {
    val old=RegNext(d.divided.asBool,false.B)
    val oldReset=RegNext(reset_n,false.B)
    val started=RegInit(false.B)
    val seenEdge=RegInit(false.B)
    val age=RegInit(0.U(3.W))
    val uninterrupted=RegInit(false.B)
    val releasedEdges=RegInit(0.U(3.W))
    when(!oldReset) {releasedEdges:=0.U}
      .elsewhen(releasedEdges<6.U) {releasedEdges:=releasedEdges+1.U}
    started:=true.B
    // Width checks alone would permit a stuck divider. Require transitions on
    // time once running, including progress out of a reset-extended low phase.
    when(started && seenEdge && age===3.U && (old || uninterrupted && oldReset)) {
      assert(d.divided.asBool=/=old)
    }
    when(releasedEdges===6.U) {
      assert(seenEdge)
      assert(age<=3.U)
    }
    when(started) {
      when(d.divided.asBool=/=old) {
        when(seenEdge) {
          when(old) {assert(age===3.U)}
            .otherwise {
              assert(age>=3.U)
              when(uninterrupted && oldReset) {assert(age===3.U)}
            }
        }
        seenEdge:=true.B;age:=1.U;uninterrupted:=oldReset
      }.otherwise {
        when(age<7.U) {age:=age+1.U}
        when(!oldReset) {uninterrupted:=false.B}
      }
    }
    cover(seenEdge && old && age===3.U && !reset_n)
    cover(seenEdge && !old && age===6.U)
  }
}

object EmitDividerFormal extends App {
  require(args.length==1)
  for(fault<-Seq(false,true)) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new DividerFormal(fault)),
    Array("--target-dir",s"${args(0)}/${if(fault) "fault" else "correct"}"),
    Array("--disable-all-randomization","--disable-opt","--strip-debug-info",
      "--verification-flavor=immediate","--lower-to-core"))
}
