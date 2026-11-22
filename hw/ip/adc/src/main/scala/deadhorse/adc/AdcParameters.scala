// SPDX-License-Identifier: Apache-2.0
package deadhorse.adc
import chisel3._

final case class AdcParameters(halfPeriodCycles: Int = 5, intervalCycles: Int = 100000,
    numerator: Int = 25300, denominator: Int = 4095, offset: Int = 0,
    calibrated: Boolean = false) {
  require(halfPeriodCycles >= 2 && intervalCycles > 40 * halfPeriodCycles)
  require(numerator > 0 && numerator < 1000000 && denominator > 0)
}

class Acquisition extends Bundle {
  val value = UInt(32.W)
  val valid = Bool()
  val calibrated = Bool()
}
