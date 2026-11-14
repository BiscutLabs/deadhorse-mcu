package deadhorse.template

import chisel3._

/** Empty clocked block template; elaboration is introduced by T07. */
class Template extends Module {
  val io = IO(new Bundle {})
}
