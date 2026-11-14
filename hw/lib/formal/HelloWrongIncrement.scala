package deadhorse.lib

import chisel3._

/** Deliberate fault, used only by the simulation/formal negative controls. */
class HelloWrongIncrement extends Hello {
  override protected def successor(value: UInt): UInt = value + 2.U
}
