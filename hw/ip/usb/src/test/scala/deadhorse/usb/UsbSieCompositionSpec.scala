package deadhorse.usb

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class UsbSieCompositionBench(fault: Int = 0)
    extends UsbWireBench(engineFactory = () => new UsbSiePacketContract(fault)) {
  val violationsSeen = IO(Output(UInt(4.W)))
  val trafficSeen = IO(Output(UInt(4.W)))
  violationsSeen := engine.asInstanceOf[UsbSiePacketContract].violationsSeen
  trafficSeen := engine.asInstanceOf[UsbSiePacketContract].trafficSeen
}

/** Real wire witnesses and DUT faults for the unbounded SIE contract proof.
  * The host independently encodes/decodes USB packets; no internal state is
  * forced. Fault runs test the very same four predicates as the formal run.
  */
class UsbSieCompositionSpec extends AnyFunSuite with ChiselSim {
  private var scenario = "positive"
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t19/sie-composition-simulation",scenario).toAbsolutePath
  }
  test("real SIE traffic exercises packet contracts through independent transport resets") {
    scenario = "positive"
    simulate(new UsbSieCompositionBench) { d =>
      val h = new UsbWireHost(d); h.initialize(); h.write(0,5,5); h.write(5,9,1)
      def read(): (Int,Seq[Int]) = { h.token(h.IN,5,1); h.receive() }
      def ack(): Unit = { h.idle(2); h.packet(h.ACK); h.idle(30) }
      val bytes = (0 until 16).map(i => i * 11)
      h.enqueue(bytes); assert(read() == (h.DATA0,bytes)); ack()
      assert(read() == (h.DATA1,Seq.empty))
      h.enqueue(Seq(0x62)); assert(read() == (h.DATA1,Seq.empty)); ack()
      assert(read() == (h.DATA0,Seq(0x62))); ack()
      h.token(h.OUT,5,1); h.idle(2); h.data(h.DATA0,Seq(0x31,0xa2)); assert(h.receive()._1 == h.ACK)
      h.idle(30)
      h.setup(5,h.setupBytes(2,1,0,0x81,0)); h.statusWrite(5)
      assert(read()._1 == h.NAK)
      h.enqueue(Seq(0xc3)); assert(read() == (h.DATA0,Seq(0xc3))); ack()
      h.write(5,9,1); h.idle(30)
      assert(d.trafficSeen.peek().litValue == 15, "missing real request/read/ACK/OUT witness")
      assert(d.violationsSeen.peek().litValue == 0)
    }
  }
  for ((fault,mask) <- Seq((1,1),(2,6),(3,8))) {
    test(s"real wire setup exposes SIE packet DUT fault $fault") {
      scenario = "fault-" + fault
      simulate(new UsbSieCompositionBench(fault)) { d =>
        val h = new UsbWireHost(d); h.initialize(); h.write(0,5,5); h.write(5,9,1); h.idle(30)
        assert((d.violationsSeen.peek().litValue & mask) == mask, s"DUT fault $fault escaped the contract")
      }
    }
  }
}
