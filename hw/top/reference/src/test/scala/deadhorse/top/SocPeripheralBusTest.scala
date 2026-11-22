package deadhorse.top

import chisel3._
import chisel3.simulator.PeekPokeAPI

/** A named test boundary substitutes the lite bus stimulus, not its block set.
  * Real-core/loader tests use the unmodified production connection separately.
  */
class SocPeripheralBusTest(d: SocDescription,c: SocI1Config)
  extends SocI1Peripherals(d,c) {
  override protected def testBusInjection: Boolean=true
}

object SocTestPorts extends PeekPokeAPI {
  def idle(d: SocI1Peripherals): Unit = {
    d.performanceReady.foreach(_.poke(true.B))
    d.nativeXip.foreach {p=>p.req.poke(false.B);p.bits.poke(0.U.asTypeOf(p.bits))}
    d.dmaMemory.foreach {p=>
      p.gnt.poke(false.B);p.rvalid.poke(false.B);p.rdata.poke(0.U);p.err.poke(false.B)
    }
  }
  def tieIdle(d: SocI1Peripherals): Unit = {
    d.performanceReady.foreach(_:=true.B)
    d.nativeXip.foreach {p=>p.req:=false.B;p.bits:=0.U.asTypeOf(p.bits)}
    d.dmaMemory.foreach {p=>p.gnt:=false.B;p.rvalid:=false.B;p.rdata:=0.U;p.err:=false.B}
  }
}
