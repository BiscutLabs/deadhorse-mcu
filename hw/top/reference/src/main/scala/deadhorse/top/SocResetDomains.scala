package deadhorse.top

import chisel3._
import deadhorse.lib.{ResetRelease,CdcSync,CdcEpoch}

/** Cold-owned acknowledgement of synchronous warm-entry initialization.
  * Rearm on the exact release edge, and discard the old synchronized low
  * sample then. A new warm pulse cannot release before its clear is consumed.
  */
class SocWarmEntry extends RawModule {
  val clk=IO(Input(Clock()));val cold_n=IO(Input(Bool()))
  val warmReleased=IO(Input(Bool()));val releasePending=IO(Input(Bool()))
  val initialize=IO(Output(Bool()));val ready=IO(Output(Bool()))
  val low=Module(new CdcSync(1,withClear=true))
  low.clk:=clk;low.reset_n:=cold_n;low.in:=(!warmReleased).asUInt
  low.clear.get:=releasePending
  withClockAndReset(clk,(!cold_n).asAsyncReset) {
    val serviced=RegInit(false.B);val pulse=RegInit(false.B)
    pulse:=low.out.asBool && !serviced && !pulse
    when(pulse) {serviced:=true.B}
    when(releasePending) {serviced:=false.B;pulse:=false.B}
    initialize:=pulse;ready:=serviced || warmReleased
  }
}

/** Shared domain releases. Qualification is sampled data, not another reset
  * source. Its owner holds it true after release until the next warm entry.
  * USB transport and D106/D107 cancellation remain separately inventoried.
  */
class SocResetReleases extends Bundle {
  val coldMain=Bool();val coldAon=Bool();val coldSource=Bool();val coldScan=Bool()
  val warmMain=Bool();val warmAon=Bool()
  val warmAonPending=Bool()
  val warmInitialize=Bool()
  val pinMain=Bool();val pinAon=Bool();val pinMainOpen=Bool();val pinAonOpen=Bool()
}

class SocResetDomains extends RawModule {
  protected def initializeValue(warm: Bool,pin: Bool): Bool=warm || pin
  val mainClock=IO(Input(Clock()));val aonClock=IO(Input(Clock()))
  val sourceClock=IO(Input(Clock()));val scanClock=IO(Input(Clock()))
  val cold_n=IO(Input(Bool()));val warm_n=IO(Input(Bool()))
  val pin_n=IO(Input(Bool()))
  val aonQualified=IO(Input(Bool()));val mainQualified=IO(Input(Bool()))
  val released=IO(Output(new SocResetReleases))
  def cold(clock: Clock): Bool={
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=cold_n;r.released
  }
  def warm(clock: Clock,qualified: Bool): ResetRelease={
    val r=Module(new ResetRelease(withPermit=true));r.clk:=clock
    r.reset_n:=cold_n && warm_n;r.permit.get:=qualified;r
  }
  released.coldMain:=cold(mainClock);released.coldAon:=cold(aonClock)
  released.coldSource:=cold(sourceClock);released.coldScan:=cold(scanClock)
  val pin=Module(new CdcEpoch(rawCapture=true))
  pin.aClock:=mainClock;pin.bClock:=aonClock
  pin.aReset_n:=released.coldMain;pin.bReset_n:=released.coldAon
  pin.cancel_n:=cold_n && pin_n
  released.pinMain:=pin.aLocal;released.pinAon:=pin.bLocal
  released.pinMainOpen:=pin.aOpen;released.pinAonOpen:=pin.bOpen
  val entry=Module(new SocWarmEntry)
  entry.clk:=aonClock;entry.cold_n:=released.coldAon
  entry.warmReleased:=released.warmAon;entry.releasePending:=released.warmAonPending
  // Pin can arrive while ndmreset already holds warm low. Preserve that event
  // independently: bootstrap restarts the divider, so policy must requalify too.
  val pinEntry=Module(new CdcSync(1))
  pinEntry.clk:=aonClock;pinEntry.reset_n:=released.coldAon
  pinEntry.in:=(!pin.bLocal).asUInt
  released.warmInitialize:=initializeValue(entry.initialize,pinEntry.out.asBool)
  val aon=warm(aonClock,released.coldAon && aonQualified && entry.ready)
  released.warmAon:=aon.released;released.warmAonPending:=aon.releasePending.get
  // The AON release remembers even a complete warm pulse while AON is stopped.
  // Main cannot reuse a stale qualification before AON processes that entry.
  released.warmMain:=warm(mainClock,released.warmAon && mainQualified).released
}
