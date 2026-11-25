package deadhorse.bus_bridge

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Source-clock endpoint; all requests cross a registered payload boundary. */
class BridgeSource(limit: Int) extends RawModule {
  protected def readResult(value: UInt): UInt = value
  require(limit >= 32)
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val source = IO(new LocalBus)
  val offer = IO(Input(Bool())); val permit = IO(Input(Bool())); val linkUp = IO(Input(Bool()))
  val requestReady = IO(Input(Bool())); val requestPush = IO(Output(Bool())); val requestData = IO(Output(UInt(72.W)))
  val responseValid = IO(Input(Bool())); val responseData = IO(Input(UInt(33.W))); val responsePop = IO(Output(Bool()))
  val abortAcknowledged = IO(Input(Bool())); val targetNeedsClock = IO(Input(Bool()))
  val abort = IO(Output(Bool())); val permitRequest = IO(Output(Bool())); val admit = IO(Output(Bool())); val clockRequest = IO(Output(Bool()))
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val idle :: waiting :: aborting :: releasing :: Nil = Enum(4)
    val phase = RegInit(releasing)
    val demand = RegInit(false.B); val ask = RegInit(false.B)
    val canAccept = RegInit(false.B); val admitted = RegInit(false.B)
    val valid = RegInit(false.B); val result = RegInit(0.U(32.W)); val error = RegInit(false.B)
    val age = RegInit(0.U(log2Ceil(limit + 1).W)); val write = RegInit(false.B)
    val abortState = RegInit(false.B)
    abort := abortState
    val requestValid = RegInit(false.B)
    val packet = Reg(new BusPayload)
    when(requestValid && requestReady) { requestValid := false.B }
    requestPush := requestValid; requestData := packet.asUInt
    permitRequest := ask; admit := admitted; clockRequest := demand
    source.gnt := canAccept; source.rvalid := valid; source.rdata := result; source.err := error
    responsePop := true.B // responses have no backpressure; unowned replies are discarded
    valid := false.B
    canAccept := phase === idle && ask && permit && requestReady && linkUp
    admitted := phase === idle && ask && permit && requestReady && linkUp
    // Reopening waits for both clocks to acknowledge the flush. Dropping this
    // demand at abort acknowledgement could stop the target before it reopens.
    demand := offer || ask || phase === waiting || phase === aborting ||
      (phase === releasing && !linkUp) || abortState || targetNeedsClock
    when(phase === releasing && !permit && linkUp && !abortAcknowledged) { phase := idle }
    when(phase === idle) {
      when(offer) { ask := true.B }
      when(ask && !offer && !source.req) {
        canAccept := false.B; admitted := false.B
        // A pending request cannot withdraw before observing its grant: a
        // delayed grant could otherwise be mistaken for the next request.
        when(permit) { ask := false.B; phase := releasing }
      }
      when(source.req && canAccept) {
        phase := waiting; age := 1.U; write := source.bits.we
        requestValid := true.B; packet := source.bits
        canAccept := false.B; admitted := false.B
      }
    }
    when(phase === waiting) {
      age := age + 1.U
      when(linkUp && responseValid) {
        abortState := false.B
        valid := true.B; error := responseData(32)
        result := Mux(write || responseData(32), 0.U, readResult(responseData(31,0)))
        ask := false.B; phase := releasing
      }.elsewhen(!linkUp || age === (limit-1).U) {
        requestValid := false.B
        abortState := true.B; valid := true.B; result := 0.U; error := true.B
        phase := aborting
      }
    }
    when(phase === aborting && abortAcknowledged) {
      abortState := false.B; ask := false.B; phase := releasing
    }
  }

}

/** Target-clock endpoint retains issued work outside the transport flush. */
class BridgeTarget extends RawModule {
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool())); val linkUp = IO(Input(Bool()))
  val target = IO(Flipped(new LocalBus)); val quiescent = IO(Input(Bool())); val isolated = IO(Output(Bool()))
  val requestValid = IO(Input(Bool())); val requestData = IO(Input(UInt(72.W))); val requestPop = IO(Output(Bool()))
  val responseReady = IO(Input(Bool())); val responsePush = IO(Output(Bool())); val responseData = IO(Output(UInt(33.W)))
  val abortAck = IO(Output(Bool())); val needClock = IO(Output(Bool()))
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val idle :: sending :: waiting :: responding :: Nil = Enum(4)
    val phase = RegInit(idle)
    val req = RegInit(false.B); val packet = Reg(new BusPayload)
    val reply = RegInit(0.U(33.W)); val poison = RegInit(true.B)
    val issued = RegInit(false.B)
    val demand = RegInit(true.B); val ack = RegInit(false.B)
    val acceptRequest = RegInit(false.B); val replyPending = RegInit(false.B)
    needClock := demand; abortAck := ack
    demand := !linkUp || issued || poison || phase =/= idle || (requestValid && acceptRequest && linkUp)
    acceptRequest := phase === idle && linkUp
    isolated := poison
    target.req := req; target.bits := packet
    requestPop := acceptRequest
    responsePush := replyPending
    responseData := reply
    when(issued && target.rvalid) { issued := false.B }
    when(poison && (quiescent || (issued && target.rvalid))) { poison := false.B; issued := false.B }
    when(linkUp) {
      ack := false.B
      when(phase === idle && requestValid && acceptRequest) {
        acceptRequest := false.B
        packet := requestData.asTypeOf(new BusPayload)
        when(poison || issued) { replyPending := true.B; reply := (BigInt(1)<<32).U; phase := responding }
          .otherwise { req := true.B; phase := sending }
      }
      when(phase === sending && target.gnt) {
        req := false.B; issued := true.B; phase := waiting
      }
      when(phase === waiting && target.rvalid) {
        replyPending := true.B
        reply := Cat(target.err, Mux(target.err || packet.we, 0.U(32.W), target.rdata))
        phase := responding
      }
      when(phase === responding && responseReady) { replyPending := false.B; phase := idle }
    }.otherwise {
      // Common flush prevents any queued request from a cancelled epoch issuing.
      // Only transport is cleared: granted endpoint work remains accounted for.
      when((issued && !target.rvalid) || (req && target.gnt)) { poison := true.B }
      when(req && target.gnt) { issued := true.B }
      req := false.B; phase := idle; ack := true.B; acceptRequest := false.B; replyPending := false.B
    }
  }
}
