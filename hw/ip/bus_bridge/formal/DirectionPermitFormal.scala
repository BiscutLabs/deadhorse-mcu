package deadhorse.bus_bridge

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

class DirectionEarlyReuse extends DirectionArbiter {
  override protected def mayAllocate(revoking: Bool): Bool = true.B
}
class DirectionStarvesMain extends DirectionArbiter {
  override protected def favorMain(nextMain: Bool): Bool = false.B
}
class DirectionBadPermit extends DirectionPermit {
  override protected def arbiter(): DirectionArbiter = new DirectionEarlyReuse
}

/** Actual independent clocks and legal four-phase requesters; no fairness assumes. */
class DirectionPermitFormal(variant: String) extends RawModule {
  val ac = IO(Input(Clock())); val mc = IO(Input(Clock())); val observe = IO(Input(Clock()))
  val an = IO(Input(Bool())); val mn = IO(Input(Bool()))
  val demandA = IO(Input(Bool())); val demandM = IO(Input(Bool()))
  val finishA = IO(Input(Bool())); val finishM = IO(Input(Bool()))
  val d = Module(if (variant == "fault") new DirectionBadPermit else new DirectionPermit)
  d.aonClock := ac; d.mainClock := mc; d.aonReset_n := an; d.mainReset_n := mn
  val reset = (!(an && mn)).asAsyncReset
  def requester(clock: Clock, demand: Bool, finish: Bool, permit: Bool): Bool = {
    withClockAndReset(clock, reset) {
      val idle :: asking :: releasing :: Nil = Enum(3)
      val state = RegInit(idle); val request = RegInit(false.B)
      when(state === idle && demand) { request := true.B; state := asking }
      // Withdrawal is legal only after observing a grant, including no-work grants.
      when(state === asking && permit && (finish || !demand)) { request := false.B; state := releasing }
      when(state === releasing && !permit) { state := idle }
      request
    }
  }
  d.requestAon := requester(ac, demandA, finishA, d.permitAon)
  d.requestMain := requester(mc, demandM, finishM, d.permitMain)
  withClockAndReset(ac, reset) {
    val sawA = RegInit(false.B); val sawM = RegInit(false.B)
    when(d.permitAon) { sawA := true.B }; when(d.permitMain) { sawM := true.B }
    if (variant == "cover") {
      cover(sawA && d.permitMain)
      cover(sawM && d.permitAon)
      cover(d.requestMain && !mc.asBool && d.permitAon)
    } else assert(!(d.permitAon && d.permitMain))
  }
  withClockAndReset(mc, reset) {
    if (variant != "cover") assert(!(d.permitAon && d.permitMain))
  }
  withClockAndReset(observe, false.B) {
    if (variant != "cover") assert((an && mn) || (!d.permitAon && !d.permitMain))
  }
}

/** AON arbitration guarantees, for arbitrary public request/acknowledgment inputs.
  * Progress counts eligible AON edges, not wall time or an invented clock ratio.
  */
class DirectionArbiterFormal(variant: String) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val a = IO(Input(Bool())); val m = IO(Input(Bool())); val returned = IO(Input(Bool()))
  val d = Module(if (variant == "fault") new DirectionStarvesMain else new DirectionArbiter)
  d.clk := clock; d.reset_n := reset_n
  d.requestAon := a; d.requestMain := m; d.returnedMain := returned
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val oldA = RegNext(d.permitAon, false.B); val oldM = RegNext(d.grantMain, false.B)
    val oldReqA = RegNext(a, false.B); val oldReqM = RegNext(m, false.B)
    val oweA = RegInit(false.B); val oweM = RegInit(false.B)
    when(!a || d.permitAon) { oweA := false.B }.elsewhen(d.grantMain) { oweA := true.B }
    when(!m || d.grantMain) { oweM := false.B }.elsewhen(d.permitAon) { oweM := true.B }
    val idleAge = RegInit(0.U(3.W))
    when(!d.permitAon && !d.grantMain && !returned && (a || m)) { idleAge := idleAge + 1.U }
      .otherwise { idleAge := 0.U }
    if (variant == "cover") {
      cover(oweA && d.permitAon)
      cover(oweM && d.grantMain)
    } else {
      assert(!(d.permitAon && d.grantMain))
      assert(!(d.permitAon && !oldA && oweM))
      assert(!(d.grantMain && !oldM && oweA))
      assert(idleAge < 4.U)
      assert(!(oldA && oldReqA) || d.permitAon)
      assert(!(oldM && oldReqM) || d.grantMain)
    }
  }
}

object EmitDirectionPermitFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 1)
    val root = Paths.get(args(0)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for (kind <- Seq("permit", "arbiter"); variant <- Seq("cover", "fault", "correct")) {
      val dir = root.resolve(kind + "_" + variant); Files.createDirectories(dir)
      def circuit = if (kind == "permit") new DirectionPermitFormal(variant) else new DirectionArbiterFormal(variant)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(circuit), Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
  }
}
