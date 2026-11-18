package deadhorse.fpu

import chisel3._
import chisel3.util._
import hardfloat._

object FpuOp {
  val names = Seq("ADD", "SUB", "MUL", "MADD", "MSUB", "NMSUB", "NMADD",
    "DIV", "SQRT", "MIN", "MAX", "EQ", "LT", "LE", "SGNJ", "SGNJN", "SGNJX",
    "CLASS", "MV_X_W", "MV_W_X", "TO_I", "TO_U", "FROM_I", "FROM_U")
  def apply(name: String): UInt = names.indexOf(name).U(5.W)
}
class FpuRequest extends Bundle {
  val op = UInt(5.W)
  val a = UInt(32.W); val b = UInt(32.W); val c = UInt(32.W)
  val rm = UInt(3.W)
}
class FpuResponse extends Bundle {
  val result = UInt(32.W); val flags = UInt(5.W)
}

/** A registered owner selects unsigned 12-bit partials for the shared integer MAC. */
class MantissaMacPort extends Bundle {
  val owner = Output(Bool())
  val a = Output(UInt(12.W))
  val b = Output(UInt(12.W))
  val addend = Output(UInt(24.W))
  val result = Input(UInt(25.W))
}

/** One outstanding operation, with registered transaction boundaries. */
class Fpu(val shareIntegerMac: Boolean = false) extends Module with RequireAsyncReset {
  val sharedMac = if (shareIntegerMac) Some(IO(new MantissaMacPort)) else None

  val io = IO(new Bundle {
    val req = Flipped(Decoupled(new FpuRequest))
    val rsp = Decoupled(new FpuResponse)
    val cancel = Input(Bool())
    val busy = Output(Bool())
  })
  val Seq(idle, decode, prepare, multiply, sum, post, divide, waitDivide,
    intRaw, round, pack, simple, publish, hold) = Enum(14)
  val state = RegInit(idle)
  val ready = RegInit(true.B); val valid = RegInit(false.B); val busy = RegInit(false.B)
  val response = RegInit(0.U.asTypeOf(new FpuResponse))
  val request = Reg(new FpuRequest)
  val selectedB = Reg(UInt(32.W)); val selectedC = Reg(UInt(32.W))
  val a = Reg(UInt(33.W)); val b = Reg(UInt(33.W)); val c = Reg(UInt(33.W))
  val fmaOp = Reg(UInt(2.W))
  val sqrtOp = Reg(Bool())
  val raw = Reg(new RawFloat(8, 26))
  val invalid = Reg(Bool()); val infinite = Reg(Bool())
  val rounded = Reg(UInt(33.W)); val flags = Reg(UInt(5.W))
  val pending = Reg(new FpuResponse)
  val multiplicand = Reg(UInt(24.W)); val product = Reg(UInt(48.W))
  val addend = Reg(UInt(48.W)); val sumResult = Reg(UInt(49.W))
  val sumA = Reg(UInt(49.W))
  // The MAC partials already accumulate in sumA. Once they finish, the saved
  // addend can shift in place during the same three addition cycles.
  val sumB = if (shareIntegerMac) addend else Reg(UInt(49.W))
  val carry = Reg(Bool())
  val count = RegInit(0.U(5.W))
  val metadata = Reg(new MulAddRecFN_interIo(8, 24))

  io.req.ready := ready; io.rsp.valid := valid; io.rsp.bits := response; io.busy := busy

  val pre = Module(new MulAddRecFNToRaw_preMul(8, 24))
  pre.io.a := a; pre.io.b := b; pre.io.c := c; pre.io.op := fmaOp
  val after = Module(new MulAddRecFNToRaw_postMul(8, 24))
  after.io.fromPreMul := metadata; after.io.mulAddResult := sumResult
  after.io.roundingMode := request.rm
  val div = Module(new DivSqrtRawFN_small(8, 24, 0))
  div.io.cancel := io.cancel
  div.io.inValid := state === divide && !io.cancel
  div.io.sqrtOp := sqrtOp
  div.io.a := rawFloatFromRecFN(8, 24, a)
  div.io.b := rawFloatFromRecFN(8, 24, b)
  div.io.roundingMode := request.rm
  val rounding = Module(new RoundRawFNToRecFN(8, 24, 0))
  rounding.io.in := raw; rounding.io.invalidExc := invalid; rounding.io.infiniteExc := infinite
  rounding.io.roundingMode := request.rm; rounding.io.detectTininess := 1.U
  val toInt = Module(new RecFNToIN(8, 24, 32))
  val fromInt = resizeRawFloat(8, 26,
    rawFloatFromIN(request.op === FpuOp("FROM_I"), request.a))
  toInt.io.in := a; toInt.io.roundingMode := request.rm
  toInt.io.signedOut := request.op === FpuOp("TO_I")
  val compare = Module(new CompareRecFN(8, 24))
  compare.io.a := a; compare.io.b := b
  compare.io.signaling := request.op === FpuOp("LT") || request.op === FpuOp("LE")
  val cmpLt = RegNext(compare.io.lt); val cmpEq = RegNext(compare.io.eq)
  val cmpFlags = RegNext(compare.io.exceptionFlags)
  val ar = rawFloatFromRecFN(8, 24, a); val br = rawFloatFromRecFN(8, 24, b)
  val nanA = ar.isNaN; val nanB = br.isNaN
  val snan = isSigNaNRawFloat(ar) || isSigNaNRawFloat(br)
  val bothZero = ar.isZero && br.isZero
  val minA = Mux(bothZero, request.a(31), cmpLt)
  val maxA = Mux(bothZero, !request.a(31), !cmpLt)
  val selectA = Mux(nanA, false.B, Mux(nanB, true.B,
    Mux(request.op === FpuOp("MIN"), minA, maxA)))

  when (state === idle && io.req.valid) {
    request := io.req.bits; ready := false.B; busy := true.B; state := decode
    val add = io.req.bits.op === FpuOp("ADD") || io.req.bits.op === FpuOp("SUB")
    selectedB := Mux(add, "h3f800000".U, io.req.bits.b)
    selectedC := Mux(add, io.req.bits.b, Mux(io.req.bits.op === FpuOp("MUL"),
      Cat(io.req.bits.a(31) ^ io.req.bits.b(31), 0.U(31.W)), io.req.bits.c))
  }
  when (state === decode) {
    count := 0.U
    sqrtOp := request.op === FpuOp("SQRT")
    a := recFNFromFN(8, 24, request.a)
    b := recFNFromFN(8, 24, selectedB)
    c := recFNFromFN(8, 24, selectedC)
    fmaOp := MuxLookup(request.op, 0.U)(Seq(FpuOp("SUB") -> 1.U,
      FpuOp("MSUB") -> 1.U, FpuOp("NMSUB") -> 2.U, FpuOp("NMADD") -> 3.U))
    state := Mux(request.op <= FpuOp("NMADD"), prepare,
      Mux(request.op <= FpuOp("SQRT"), divide,
        Mux(request.op === FpuOp("FROM_I") || request.op === FpuOp("FROM_U"), intRaw, simple)))
    when (request.op >= FpuOp.names.size.U || request.rm > 4.U) {
      pending.result := "h7fc00000".U; pending.flags := 16.U; state := publish
    }
  }
  when (state === prepare) {
    count := count + 1.U
    when (count === 2.U) {
    if (shareIntegerMac) {
      sumA := 0.U
    } else {
      multiplicand := pre.io.mulAddA; product := pre.io.mulAddB
    }
    addend := pre.io.mulAddC; metadata := pre.io.toPostMul
    count := 0.U; state := multiply
    }
  }
  if (shareIntegerMac) {
    val mac = sharedMac.get
    // The recoded operands are held from decode until the next request.
    val aSig = pre.io.mulAddA
    val bSig = pre.io.mulAddB
    mac.owner := busy
    mac.a := Mux(count(0), aSig(23, 12), aSig(11, 0))
    mac.b := Mux(count(1), bSig(23, 12), bSig(11, 0))
    mac.addend := sumA(47, 24)
    // Bits 47:24 carry into the next MAC. Bits 23:0 hold finalized limbs.
    // For base R=4096 the four sums are ll, hl+ll/R, lh+prev, hh+prev/R.
    when (state === multiply && !io.cancel) {
      count := count + 1.U
      switch(count(1, 0)) {
        is(0.U) { sumA := Cat(mac.result(23, 12), 0.U(12.W), mac.result(11, 0)) }
        is(1.U) { sumA := Cat(mac.result(23, 0), sumA(23, 0)) }
        is(2.U) { sumA := Cat(mac.result(24, 12), mac.result(11, 0), sumA(11, 0)) }
        is(3.U) {
          sumA := Cat(mac.result(23, 0), sumA(23, 0))
          sumResult := 0.U; carry := false.B
          count := 0.U; state := sum
        }
      }
    }
  } else {
    // Shift/add: only a 24-bit addition per iteration; no full-width multiplier.
    val mulSum = FpuAdd(product(47, 24), Mux(product(0), multiplicand, 0.U), 25)
    val nextProduct = Cat(mulSum, product(23, 1))
    when (state === multiply) {
      product := nextProduct
      count := count + 1.U
      when (count === 23.U) {
        sumA := nextProduct; sumB := addend; sumResult := 0.U; carry := false.B
        count := 0.U; state := sum
      }
    }
  }
  // A 49-bit fused addition in three 17-bit chunks; carry is never discarded.
  val chunkSum = sumA(16, 0) +& sumB(16, 0) + carry
  when (state === sum) {
    sumResult := Cat(chunkSum(16, 0), sumResult(48, 17))
    sumA := sumA >> 17; sumB := sumB >> 17; carry := chunkSum(17)
    count := count + 1.U
    when (count === 2.U) {
      // Three chunks have 51 bits, of which only 49 belong to the result.
      sumResult := Cat(chunkSum(14, 0), sumResult(48, 15))
      count := 0.U; state := post
    }
  }
  when (state === post) {
    count := count + 1.U
    when (count === 2.U) {
    raw := after.io.rawOut; invalid := after.io.invalidExc; infinite := false.B
    count := 0.U; state := round
    }
  }
  when (state === divide) { when(div.io.inReady) { state := waitDivide } }
  when (state === waitDivide && (div.io.rawOutValid_div || div.io.rawOutValid_sqrt)) {
    raw := div.io.rawOut; invalid := div.io.invalidExc; infinite := div.io.infiniteExc
    count := 0.U; state := round
  }
  when (state === intRaw) {
    count := count + 1.U
    when (count === 2.U) {
    raw := fromInt
    invalid := false.B; infinite := false.B; count := 0.U; state := round
    }
  }
  when (state === round) {
    count := count + 1.U
    when (count === 2.U) {
    rounded := rounding.io.out; flags := rounding.io.exceptionFlags; state := pack
    }
  }
  when (state === pack) {
    response.result := fNFromRecFN(8, 24, rounded); response.flags := flags
    valid := true.B; state := hold
  }
  when (state === simple) {
    pending.result := request.a; pending.flags := 0.U
    switch(request.op) {
      is(FpuOp("MIN"), FpuOp("MAX")) {
        pending.result := Mux(nanA && nanB, "h7fc00000".U, Mux(selectA, request.a, request.b))
        pending.flags := Cat(snan, 0.U(4.W))
      }
      is(FpuOp("EQ"), FpuOp("LT"), FpuOp("LE")) {
        pending.result := Mux(request.op === FpuOp("EQ"), cmpEq,
          Mux(request.op === FpuOp("LT"), cmpLt, cmpLt || cmpEq))
        pending.flags := cmpFlags
      }
      is(FpuOp("SGNJ"), FpuOp("SGNJN"), FpuOp("SGNJX")) {
        val sign = Mux(request.op === FpuOp("SGNJ"), request.b(31),
          Mux(request.op === FpuOp("SGNJN"), !request.b(31), request.a(31) ^ request.b(31)))
        pending.result := Cat(sign, request.a(30, 0))
      }
      is(FpuOp("CLASS")) { pending.result := classifyRecFN(8, 24, a) }
      is(FpuOp("TO_I"), FpuOp("TO_U")) {
        pending.result := toInt.io.out
        pending.flags := Cat(toInt.io.intExceptionFlags(2, 1).orR, 0.U(3.W), toInt.io.intExceptionFlags(0))
      }
    }
    count := count + 1.U
    val comparison = request.op >= FpuOp("MIN") && request.op <= FpuOp("LE")
    when (Mux(comparison, count === 1.U,
      request.op < FpuOp("TO_I") || count === 3.U)) { state := publish }
  }
  when (state === publish) { response := pending; valid := true.B; state := hold }
  when (state === hold && io.rsp.ready) {
    valid := false.B; busy := false.B; ready := true.B; state := idle
  }
  when (io.cancel) {
    state := idle; ready := true.B; valid := false.B; busy := false.B; count := 0.U
    response := 0.U.asTypeOf(new FpuResponse)
  }
}
