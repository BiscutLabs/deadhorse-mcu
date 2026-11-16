package deadhorse.fpu

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage

/** Properties augment the production class; no arithmetic abstraction. */
class FpuFormal(fault: Int = 0, coversOnly: Boolean = false,
    protocolCovers: Boolean = false, divideCovers: Boolean = false) extends Fpu {
  val pendingCheck = RegInit(false.B)
  val age = RegInit(0.U(7.W))
  val history = RegInit(false.B); history := true.B
  val accepted = RegNext(io.req.fire && !io.cancel, false.B)
  val offered = RegNext(io.req.bits.asUInt)
  val offeredB = RegNext(Mux(io.req.bits.op < 2.U, "h3f800000".U, io.req.bits.b))
  val offeredC = RegNext(Mux(io.req.bits.op < 2.U, io.req.bits.b,
    Mux(io.req.bits.op === 2.U, Cat(io.req.bits.a(31) ^ io.req.bits.b(31), 0.U(31.W)), io.req.bits.c)))
  val canceled = RegNext(io.cancel, false.B)
  val held = RegNext(io.rsp.valid && !io.rsp.ready && !io.cancel, false.B)
  val priorResponse = RegNext(io.rsp.bits.asUInt)
  val priorRequest = RegNext(request.asUInt)
  val priorState = RegNext(state)
  val priorCount = RegNext(count)
  val priorPostInputs = RegNext(Cat(metadata.asUInt, sumResult, request.rm))
  val priorRoundInputs = RegNext(Cat(raw.asUInt, invalid, infinite, request.rm))
  val deadline = Mux(request.op <= 6.U, 38.U,
    Mux(request.op === 7.U, 58.U, Mux(request.op === 8.U, 56.U,
      Mux(request.op === 20.U || request.op === 21.U, 6.U,
        Mux(request.op >= 22.U, 8.U, Mux(request.op >= 9.U && request.op <= 13.U, 4.U, 3.U))))))
  when (io.req.fire) { pendingCheck := true.B; age := 0.U }
    .elsewhen (io.rsp.fire) { pendingCheck := false.B }
  when (pendingCheck && !io.rsp.valid) { age := age + 1.U }
  when (io.cancel) { pendingCheck := false.B; age := 0.U }

  if (fault == 1) { when (io.cancel) { valid := true.B } }
  if (fault == 2) { when (state === hold && !io.rsp.ready) { response.result := response.result ^ 1.U } }
  if (fault == 3) { when (state === multiply) { count := 0.U } }

  if (coversOnly) {
    if (divideCovers) {
      for(op<-Seq(7,8)) cover(io.rsp.valid && request.op === op.U &&
        request.a === "h3f800000".U && request.b === "h40000000".U && request.rm === 0.U)
    } else if (protocolCovers) {
      cover(canceled && io.req.fire && !io.cancel)
      cover(io.cancel && (div.io.rawOutValid_div || div.io.rawOutValid_sqrt))
      cover(io.cancel && io.req.fire && state === idle)
      cover(held && io.rsp.fire && !io.cancel)
    } else {
      for (op <- 0 until 24) cover(io.rsp.valid && request.op === op.U && request.rm <= 4.U)
      cover(held && io.rsp.valid)
    }
  } else {
    assert(io.req.ready === !io.busy)
    assert(io.busy === pendingCheck)
    assert(io.rsp.valid === (state === hold))
    assert(!(io.req.ready && io.rsp.valid))
    when (pendingCheck && !io.rsp.valid) { assert(age < deadline) }
    when (history) {
      when (canceled) {
        assert(io.req.ready && !io.busy && !io.rsp.valid)
        assert(io.rsp.bits.asUInt === 0.U)
        assert(div.io.inReady && !div.io.rawOutValid_div && !div.io.rawOutValid_sqrt)
      }
      when (accepted) {
        assert(request.asUInt === offered)
        assert(selectedB === offeredB && selectedC === offeredC)
      }
      when (!accepted && !canceled && io.busy) { assert(request.asUInt === priorRequest) }
      when (held) { assert(io.rsp.valid && io.rsp.bits.asUInt === priorResponse) }
      when (state === post && priorState === post) {
        assert(Cat(metadata.asUInt, sumResult, request.rm) === priorPostInputs)
      }
      when (priorState === post && state === round) { assert(priorCount === 2.U) }
      when (state === round && priorState === round) {
        assert(Cat(raw.asUInt, invalid, infinite, request.rm) === priorRoundInputs)
      }
      when (priorState === round && state === pack) { assert(priorCount === 2.U) }
    }
  }
}

object EmitFpuFormal extends App {
  require(args.length == 1)
  for ((name,fault,covers,protocol,divide) <- Seq(("normal",0,false,false,false),
      ("cover_operations",0,true,false,false),("cover_protocol",0,true,true,false),
      ("cover_division",0,true,false,true),
      ("cancel_fault",1,false,false,false),("hold_fault",2,false,false,false),
      ("progress_fault",3,false,false,false))) {
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new FpuFormal(fault,covers,protocol,divide)),
      Array("--target-dir",s"${args(0)}/$name"),
      Array("--disable-all-randomization","--verification-flavor=immediate",
            "--lower-to-core","--strip-debug-info","--preserve-values=named"))
  }
}
