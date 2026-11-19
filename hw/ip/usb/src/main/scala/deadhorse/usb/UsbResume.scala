package deadhorse.usb

import chisel3._
import chisel3.util._
import deadhorse.lib.CdcSync

/** Host-resume detector, not device-initiated remote wake. Clock must run while
  * attached. Pending survives loss of application clock until explicit clear.
  */
class UsbResume(idleSamples: Int = 144000) extends RawModule {
  require(idleSamples >= 4 && idleSamples < (1 << 20))
  protected def retain(value: Bool): Bool = value
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val dp=IO(Input(Bool()));val dn=IO(Input(Bool()));val attached=IO(Input(Bool()))
  val driving=IO(Input(Bool()));val clear=IO(Input(Bool()))
  val pending=IO(Output(Bool()));val suspended=IO(Output(Bool()))
  val pins=Module(new CdcSync(2));pins.clk:=clk;pins.reset_n:=reset_n;pins.in:=Cat(dn,dp)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val count=RegInit(0.U(20.W));val sleeping=RegInit(false.B);val event=RegInit(false.B)
    val invalid=RegInit(0.U(2.W))
    val j=pins.out===1.U;val k=pins.out===2.U
    // Predict carries one running sample ahead. Clearing the timer also clears
    // every carry, so interrupted idle periods cannot borrow time from a prior one.
    val running=attached && !driving && j
    val terminal=RegNext(running && count === (idleSamples-2).U,false.B)
    val carries=(1 until 5).map {lane=>
      RegNext(running && count(lane*4-1,0) === ((BigInt(1) << (lane*4))-2).U,false.B)
    }
    val next=Cat((0 until 5).reverse.map { lane=>
      val nibble=count(lane*4+3,lane*4)
      val carry=if(lane==0) true.B else carries(lane-1)
      nibble+carry.asUInt
    })
    when(j || k || !attached || driving) { invalid:=0.U }
      .elsewhen(invalid =/= 3.U) { invalid:=invalid+1.U }
    when(!attached || driving) { count:=0.U;sleeping:=false.B }
      .elsewhen(j) {
        // Elapsed time is irrelevant after qualification. Let the counter run
        // rather than placing the suspend latch on every counter feedback path.
        count:=next
        when(terminal) { sleeping:=true.B }
      }.otherwise {
        count:=0.U
        // The independently synchronized pins may briefly show SE0/SE1 on
        // J-to-K. Preserve qualification across that skew; sustained illegal
        // line state (including bus reset) cancels it after four samples.
        when(k || invalid === 3.U) { sleeping:=false.B }
      }
    event:=retain((event && !clear) || (attached && !driving && sleeping && k))
    pending:=event;suspended:=sleeping
  }
}
