package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class ResetBootstrapSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/reset-simulation").toAbsolutePath
  }
  for(external<-Seq(false,true);bypass<-Seq(false,true)) {
    test(s"reset-held source=$external bypass=$bypass, frozen straps, asynchronous reset") {
      simulateRaw(new ResetBootstrap) {d=>
        d.selectExternal.poke(external.B);d.bypassPor.poke(bypass.B)
        d.externalReset_n.poke(false.B);d.supplyReset_n.poke(false.B)
        def tick(n: Int): Unit=for(_<-0 until n) {
          if(external) d.externalAonClock.step() else d.rcClock.step()
        }
        tick(5);d.aonReset_n.expect(false.B);d.coldReset_n.expect(false.B)
        // Fallback RC is deliberately never clocked; bypass POR stays stuck low.
        d.externalReset_n.poke(true.B)
        if(!bypass) {
          tick(20);d.aonReset_n.expect(false.B)
          d.supplyReset_n.poke(true.B)
        }
        tick(16);d.aonReset_n.expect(true.B);d.strapsFrozen.expect(true.B)
        // D84 bypass is fixed while powered; only AON selection is latched.
        d.selectExternal.poke((!external).B)
        tick(6);d.selectedExternal.expect(external.B);d.selectedBypass.expect(bypass.B)
        d.aonReset_n.expect(true.B)
        if(bypass) {
          d.supplyReset_n.poke(true.B);tick(3);d.supplyReset_n.poke(false.B)
          d.aonReset_n.expect(true.B)
        } else {
          // Restore static board straps before a new reset epoch.
          d.selectExternal.poke(external.B);d.bypassPor.poke(bypass.B)
          d.supplyReset_n.poke(false.B);d.aonReset_n.expect(false.B)
        }
        // D83: pin reset is cold only in bypass mode. Restore straps for
        // this new reset epoch and leave the supply supervisor released.
        d.selectExternal.poke(external.B);d.bypassPor.poke(bypass.B)
        d.supplyReset_n.poke(true.B);tick(16)
        d.externalReset_n.poke(false.B);d.aonReset_n.expect(false.B)
        d.coldReset_n.expect((!bypass).B)
      }
    }
  }
  test("normal POR-only boot releases after RC edges without an external-pin pulse") {
    simulateRaw(new ResetBootstrap) {d=>
      d.selectExternal.poke(false.B);d.bypassPor.poke(false.B)
      d.externalReset_n.poke(true.B);d.supplyReset_n.poke(false.B)
      d.rcClock.step(4);d.aonReset_n.expect(false.B)
      d.supplyReset_n.poke(true.B);d.rcClock.step(16);d.aonReset_n.expect(true.B)
    }
  }
}
