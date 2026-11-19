package deadhorse.usb

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class UsbResumeSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t19/resume-simulation").toAbsolutePath
  }
  test("idle threshold, interrupted idle, retained host resume and explicit clear") {
    for(threshold<-Seq(17,256,513,144000)) simulateRaw(new UsbResume(threshold),subdirectory=Some(s"threshold-$threshold")) { d=>
      def high(b: Bool)=b.peek().litValue==1
      def line(j: Boolean): Unit={d.dp.poke(j.B);d.dn.poke((!j).B)}
      d.reset_n.poke(false.B);d.attached.poke(false.B);d.driving.poke(false.B);d.clear.poke(false.B);line(true)
      d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(4);d.attached.poke(true.B)
      d.clk.step(threshold-1);assert(!high(d.suspended));d.clk.step();assert(high(d.suspended))
      line(false);d.clk.step(3);assert(high(d.pending));assert(!high(d.suspended))
      d.attached.poke(false.B);d.clk.step(19);assert(high(d.pending),"wake lost on detach")
      d.clear.poke(true.B);d.clk.step();assert(!high(d.pending));d.clear.poke(false.B)
      line(true);d.clk.step(4);d.attached.poke(true.B);d.clk.step(threshold-2)
      d.driving.poke(true.B);d.clk.step();d.driving.poke(false.B)
      d.clk.step(threshold-1);assert(!high(d.suspended),"interrupted idle borrowed prior elapsed time")
      d.clk.step();assert(high(d.suspended))
      line(false);d.clear.poke(true.B);d.clk.step(3);assert(high(d.pending),"capture must win simultaneous clear")
      d.reset_n.poke(false.B);d.clk.step();assert(!high(d.pending) && !high(d.suspended))
    }
  }
  test("independently sampled J-to-K pin skew preserves the resume event") {
    for(se1<-Seq(false,true)) simulateRaw(new UsbResume(17),subdirectory=Some(s"skew-$se1")) { d=>
      d.reset_n.poke(false.B);d.attached.poke(true.B);d.driving.poke(false.B);d.clear.poke(false.B)
      d.dp.poke(true.B);d.dn.poke(false.B);d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(24)
      assert(d.suspended.peek().litValue==1)
      d.dp.poke(se1.B);d.dn.poke(se1.B);d.clk.step()
      d.dp.poke(false.B);d.dn.poke(true.B);d.clk.step(5)
      assert(d.pending.peek().litValue==1,"skewed J-to-K lost host resume")
    }
  }
  test("sustained SE0 or SE1 cancels suspend qualification before a later K") {
    for(se1<-Seq(false,true)) simulateRaw(new UsbResume(17),subdirectory=Some(s"sustained-$se1")) { d=>
      d.reset_n.poke(false.B);d.attached.poke(true.B);d.driving.poke(false.B);d.clear.poke(false.B)
      d.dp.poke(true.B);d.dn.poke(false.B);d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(24)
      assert(d.suspended.peek().litValue==1)
      d.dp.poke(se1.B);d.dn.poke(se1.B);d.clk.step(6)
      assert(d.suspended.peek().litValue==0,"four synchronized illegal samples did not clear suspend")
      d.dp.poke(false.B);d.dn.poke(true.B);d.clk.step(6)
      assert(d.pending.peek().litValue==0,"invalid line interval reused an old suspend qualification")
      d.dp.poke(true.B);d.dn.poke(false.B);d.clk.step(24)
      assert(d.suspended.peek().litValue==1,"fresh idle period did not requalify suspend")
    }
  }
}
