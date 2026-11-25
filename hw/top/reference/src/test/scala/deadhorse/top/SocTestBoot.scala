package deadhorse.top

import chisel3._
import chisel3.simulator.PeekPokeAPI

/** Performance boots directly after its reset; lite remains held until firmware
  * loads and releases it. Keep the external performance reset during setup. */
object SocTestBoot extends PeekPokeAPI {
  def release(d: SocCoreAssembly, tick: () => Unit): Unit = {
    val p=d.i1.get
    d.mainCoreReset_n.poke(false.B)
    p.aonExtraIn.poke(0.U)
    p.clockControl.reset_n.poke(true.B);p.clockControl.coreIdle.poke(false.B)
    p.clockControl.closed.poke(false.B);p.clockControl.stable.poke(false.B);p.clockControl.jtagWake.poke(false.B)
    for(_<-0 until 520) tick()
    p.clockControl.stable.poke(true.B)
    for(_<-0 until 8) tick()
    assert(!d.coreReady.peek().litToBoolean,"PRODUCTION_BOOT_EXTERNAL_HOLD")
    d.mainCoreReset_n.poke(true.B)
  }
}
