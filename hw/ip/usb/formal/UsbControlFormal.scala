package deadhorse.usb

import chisel3._

class UsbPrematureStatus extends UsbControl {
  override protected def statusAcknowledged(ack: Bool,sent: Bool): Bool=ack || sent
}
/** Unbounded side-effect qualification, not a full USB control-transfer proof.
  * Public packet inputs are unconstrained; the production cadence is real.
  */
class UsbControlFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val busReset=IO(Input(Bool()))
  val request=IO(Input(Bool()));val inReady=IO(Input(Bool()));val ack=IO(Input(Bool()))
  val setup=IO(Input(Bool()));val outReady=IO(Input(Bool()));val valid=IO(Input(Bool()))
  val error=IO(Input(Bool()));val data=IO(Input(UInt(8.W)))
  val cadence=Module(new UsbBitEnable);cadence.clk:=clock;cadence.reset_n:=reset_n
  val d=Module(if(variant=="corrupt") new UsbPrematureStatus else new UsbControl)
  d.clk:=clock;d.reset_n:=reset_n;d.bitEnable:=cadence.enable;d.busReset:=busReset
  d.inRequest:=request;d.inReady:=inReady;d.inAck:=ack
  d.setup:=setup;d.outReady:=outReady;d.outValid:=valid;d.outError:=error;d.outData:=data
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val history=RegNext(true.B,false.B)
    val oldAddress=RegNext(d.address,0.U);val oldConfig=RegNext(d.configured,false.B)
    val allowed=RegNext(busReset || (cadence.enable && inReady && ack && !request &&
      !(outReady && (setup || error))),false.B)
    if(variant=="cover") {
      cover(d.address=/=0.U)
      cover(d.configured)
      cover(history && d.address===oldAddress && setup && outReady && ack && cadence.enable)
    } else {
      when(history && d.address=/=oldAddress){assert(allowed)}
      when(history && d.configured=/=oldConfig){assert(allowed)}
    }
  }
}
