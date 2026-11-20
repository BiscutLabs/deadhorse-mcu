package deadhorse.stubs

/** Same public interface, no USB engine or pad drive. */
class UsbStub(json: String, base: BigInt = 0x40040800L)
  extends deadhorse.usb.Usb(json,base,included=false)
