package deadhorse.lib

import chisel3._

/** D106/D107 cancellation fence, shared by request and reply channels.
  * Only the release/event state is asynchronously affected by cancel_n.
  * Payload and pointer banks use domain resets and synchronous initialization.
  * No endpoint reopens until both endpoints have clocked through cancellation.
  */
class CdcEpoch(rawCapture: Boolean=false) extends RawModule {
  protected def admitted(local: Bool,peer: Bool): Bool=local && peer
  val aClock=IO(Input(Clock()));val bClock=IO(Input(Clock()))
  val aReset_n=IO(Input(Bool()));val bReset_n=IO(Input(Bool()))
  val cancel_n=IO(Input(Bool()))
  val aOpen=IO(Output(Bool()));val bOpen=IO(Output(Bool()))
  val aLocal=IO(Output(Bool()));val bLocal=IO(Output(Bool()))
  // The shared pin fence also feeds AON bootstrap's event capture. Waiting for
  // the main cold release there would deadlock the clock startup it enables.
  // In rawCapture mode cancel_n MUST include raw cold plus pin; domain resets
  // remain cold-qualified and continue to quarantine admission independently.
  val common=if(rawCapture) cancel_n else aReset_n && bReset_n && cancel_n
  val ar=Module(new ResetRelease);val br=Module(new ResetRelease)
  ar.clk:=aClock;br.clk:=bClock;ar.reset_n:=common;br.reset_n:=common
  val ab=Module(new CdcSync(1,withClear=true));val ba=Module(new CdcSync(1,withClear=true))
  ab.clk:=bClock;ab.reset_n:=bReset_n;ab.in:=ar.released.asUInt;ab.clear.get:= !br.released
  ba.clk:=aClock;ba.reset_n:=aReset_n;ba.in:=br.released.asUInt;ba.clear.get:= !ar.released
  // Async assertion blocks admission immediately; release uses local FFs only.
  aOpen:=admitted(ar.released && (if(rawCapture) aReset_n else true.B),ba.out.asBool)
  bOpen:=admitted(br.released && (if(rawCapture) bReset_n else true.B),ab.out.asBool)
  aLocal:=ar.released;bLocal:=br.released
}
