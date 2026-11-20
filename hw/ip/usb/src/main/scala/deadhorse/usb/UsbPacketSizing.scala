package deadhorse.usb

import chisel3.util.log2Ceil

object UsbPacketSizing {
  val bulkMaxPacketBytes: Int = 16
}

/** One reserved ring slot; the banked RAM retains its three-stage read path. */
final case class UsbPacketGeometry(maxPacketBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) {
  require(Set(8,16,32,64).contains(maxPacketBytes))
  val slots: Int = maxPacketBytes + 1
  val pointerBits: Int = log2Ceil(slots)
  val bankWords: Int = 8
  val wordBits: Int = log2Ceil(bankWords)
  val banks: Int = (slots + bankWords - 1) / bankWords
  val physicalWords: Int = banks * bankWords
}
