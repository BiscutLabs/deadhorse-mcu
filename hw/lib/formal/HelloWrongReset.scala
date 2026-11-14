package deadhorse.lib

import chisel3._

/** Deliberate reset fault, never selected by EmitHello. */
class HelloWrongReset extends Hello {
  override protected def resetValue: Int = 1
}
