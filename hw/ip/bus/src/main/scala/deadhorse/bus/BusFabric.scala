package deadhorse.bus

import chisel3._
import chisel3.util._
import deadhorse.lib._

case class BusRegion(base: BigInt, size: BigInt, limit: Int = 128) {
  require(size > 0 && (size & (size - 1)) == 0 && base % size == 0)
  require(base >= 0 && base + size <= (BigInt(1) << 32) && limit >= 8)
}

class BusFabric(masters: Int, regions: Seq[BusRegion]) extends RawModule {
  require(masters >= 1 && masters <= 8 && regions.nonEmpty && regions.size <= 8)
  for (a <- regions.indices; b <- 0 until a)
    require(regions(a).base + regions(a).size <= regions(b).base || regions(b).base + regions(b).size <= regions(a).base)
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val master = IO(Vec(masters, new LocalBus))
  val target = IO(Vec(regions.size, Flipped(new LocalBus)))
  val admit = IO(Input(Vec(regions.size, Bool())))
  val allow = IO(Input(Vec(masters, Bool())))
  val quiescent = IO(Input(Vec(regions.size, Bool())))
  val waiting = IO(Output(Vec(regions.size, Bool())))
  val completed = IO(Output(Vec(regions.size, Bool())))
  val isolated = IO(Output(Vec(regions.size, Bool())))
  protected def response(value: UInt): UInt = value
  val mw = math.max(1, log2Ceil(masters)); val tw = math.max(1, log2Ceil(regions.size))
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val idle :: grant :: send :: awaitResponse :: reply :: Nil = Enum(5)
    val state = RegInit(idle)
    val priority = RegInit(0.U(mw.W))
    val owner = RegInit(0.U(mw.W)); val destination = RegInit(0.U(tw.W))
    val payload = Reg(new BusPayload)
    val mapped = RegInit(false.B)
    val grants = RegInit(VecInit(Seq.fill(masters)(false.B)))
    val responses = RegInit(VecInit(Seq.fill(masters)(false.B)))
    val result = RegInit(0.U(32.W)); val error = RegInit(false.B)
    val requests = RegInit(VecInit(Seq.fill(regions.size)(false.B)))
    val poisons = RegInit(VecInit(Seq.fill(regions.size)(false.B)))
    val demands = RegInit(VecInit(Seq.fill(regions.size)(false.B)))
    val done = RegInit(VecInit(Seq.fill(regions.size)(false.B)))
    val elapsed = RegInit(0.U(log2Ceil(regions.map(_.limit).max + 1).W))
    val limit = Reg(UInt(elapsed.getWidth.W))
    val hits = VecInit(master.map(m => VecInit(regions.map(r =>
      (m.bits.addr & (BigInt("ffffffff",16) ^ (r.size - 1)).U(32.W)) === r.base.U))))
    val eligible = VecInit((0 until masters).map(i => master(i).req &&
      (!hits(i).asUInt.orR || (0 until regions.size).map(t => hits(i)(t) && (admit(t) || poisons(t))).reduce(_ || _))))
    val chosen = WireDefault(0.U(mw.W)); val found = WireDefault(false.B)
    for (offset <- (0 until masters).reverse) {
      val sum = priority +& offset.U
      val index = Mux(sum >= masters.U, sum - masters.U, sum)(mw-1,0)
      when(eligible(index)) { chosen := index; found := true.B }
    }
    grants.foreach(_ := false.B); responses.foreach(_ := false.B); done.foreach(_ := false.B)
    for (i <- 0 until masters) {
      master(i).gnt := grants(i); master(i).rvalid := responses(i)
      master(i).rdata := result; master(i).err := error
    }
    for (t <- regions.indices) {
      target(t).req := requests(t); target(t).bits := payload
      isolated(t) := poisons(t); waiting(t) := demands(t); completed(t) := done(t)
      demands(t) := (0 until masters).map(i => master(i).req && hits(i)(t)).reduce(_ || _) ||
        (state =/= idle && mapped && destination === t.U)
      when(poisons(t) && (target(t).rvalid || quiescent(t))) { poisons(t) := false.B }
    }
    def finish(data: UInt, failed: Bool): Unit = {
      result := Mux(failed || payload.we, 0.U, response(data))
      error := failed; responses(owner) := true.B
      requests.foreach(_ := false.B)
      when(mapped) { done(destination) := true.B }
      state := reply
    }
    when(state === idle && found) {
      owner := chosen; payload := master(chosen).bits
      mapped := hits(chosen).asUInt.orR
      destination := PriorityEncoder(hits(chosen).asUInt)
      grants(chosen) := true.B
      priority := Mux(chosen === (masters-1).U, 0.U, chosen + 1.U)
      state := grant
    }
    when(state === grant) {
      elapsed := 1.U
      limit := VecInit(regions.map(_.limit.U(elapsed.getWidth.W)))(destination)
      when(!mapped || payload.addr(1,0).orR || !allow(owner) || poisons(destination)) {
        finish(0.U, true.B)
      }.otherwise {
        requests(destination) := true.B; state := send
      }
    }
    when(state === send || state === awaitResponse) {
      elapsed := elapsed + 1.U
      when(state === awaitResponse && target(destination).rvalid) {
        finish(target(destination).rdata, target(destination).err)
      }.elsewhen(elapsed === limit - 1.U) {
        poisons(destination) := true.B; finish(0.U, true.B)
      }.elsewhen(state === send && target(destination).gnt) {
        requests(destination) := false.B; state := awaitResponse
      }
    }
    when(state === reply) { state := idle }
  }
}
