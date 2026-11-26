package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib.ResetRelease

/** Unscanned manufacturing entry; see docs/spec/t37-test-access.md.
  * Pins are tester-synchronous to TCK. No functional clock is needed to enter.
  */
class SocTestAccess extends RawModule {
  val tck=IO(Input(Clock()));val externalReset_n=IO(Input(Bool()))
  val tms=IO(Input(Bool()));val tdi=IO(Input(Bool()))
  val porBypass=IO(Input(Bool()));val aonClockSelect=IO(Input(Bool()))
  val scanReset_n=IO(Input(Bool()))
  val testMode=IO(Output(Bool()))

  protected def key: BigInt=BigInt("D37A6C95",16)
  protected def lastBit: UInt=31.U(5.W)
  val release=Module(new ResetRelease)
  release.clk:=tck;release.reset_n:=externalReset_n
  val fallingClock=(!tck.asBool).asClock
  val fallingRelease=Module(new ResetRelease)
  fallingRelease.clk:=fallingClock;fallingRelease.reset_n:=externalReset_n
  val armed=withClockAndReset(tck,(!release.released).asAsyncReset) {
    val position=RegInit(0.U(5.W))
    val closed=RegInit(false.B)
    val accepted=RegInit(false.B)
    val expected=key.U(32.W)(31.U-position)
    when(!closed) {
      when(!tms || tdi=/=expected || !porBypass || !aonClockSelect || scanReset_n) {
        closed:=true.B
      }.elsewhen(position===lastBit) {
        accepted:=true.B;closed:=true.B
      }.otherwise {
        position:=position+1.U
      }
    }
    dontTouch(position);dontTouch(closed);dontTouch(accepted)
    accepted
  }
  withClockAndReset(fallingClock,(!fallingRelease.released).asAsyncReset) {
    val active=RegInit(false.B)
    when(armed) {active:=true.B}
    dontTouch(active)
    testMode:=active
  }
}
