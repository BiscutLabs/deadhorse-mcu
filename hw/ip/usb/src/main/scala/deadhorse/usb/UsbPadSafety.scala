package deadhorse.usb

import chisel3._

/** Approved PHY safety boundary: raw reset/VBUS must disable pads without clocks. */
class UsbPadSafety extends RawModule {
  val reset_n=IO(Input(Bool()));val vbus=IO(Input(Bool()))
  val requestedDrive=IO(Input(Bool()));val requestedPullup=IO(Input(Bool()))
  val drive=IO(Output(Bool()));val pullupEnable=IO(Output(Bool()))
  protected def permitted(reset: Bool,power: Bool): Bool=reset && power
  drive:=requestedDrive && permitted(reset_n,vbus)
  pullupEnable:=requestedPullup && permitted(reset_n,vbus)
}
