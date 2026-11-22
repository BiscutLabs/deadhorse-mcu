package deadhorse.lite_core
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class LiteMachineSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t25/machine-simulation").toAbsolutePath
  }
  import Assembly._
  def csr(address: Int,rd: Int,op: Int,source: Int): Long=
    (address.toLong<<20)|(source.toLong<<15)|(op.toLong<<12)|(rd.toLong<<7)|0x73L
  val base=0x30000000L;val handler=base+0x400
  val setup=Seq(0x300000b7L,i(0x13,1,0,1,0x400),csr(0x305,0,1,1))
  val handlerProgram=Seq(csr(0x341,14,2,0),i(0x13,14,0,14,4),csr(0x341,0,1,14),0x30200073L)
  def high(b: Bool)=b.peek().litToBoolean
  class Driver(d: LiteHart,words: Seq[Long],handlerWords: Seq[Long]=handlerProgram) {
    val memory=(words.zipWithIndex.map {case(w,i)=>(base+4*i)->w}++
      handlerWords.zipWithIndex.map {case(w,i)=>(handler+4*i)->w}).toMap
    val oracle=new MachineOracle(memory,base);val random=new scala.util.Random(2501)
    var cycles=0;var retiring=0;var interrupts=0;var irq=false
    var waitGrant= -1;var waitReply= -1;var captured=0L;var responding=false
    d.reset_n.poke(false.B);d.start.poke(false.B);d.entry.poke(base.U);d.irq.poke(false.B)
    d.bus.gnt.poke(false.B);d.bus.rvalid.poke(false.B);d.bus.err.poke(false.B);d.bus.rdata.poke(0.U)
    d.clk.step(3);d.reset_n.poke(true.B)
    def tick(): Unit={
      d.irq.poke(irq.B)
      if(high(d.bus.req) && waitGrant<0) waitGrant=random.nextInt(4)
      val grant=high(d.bus.req) && waitGrant==0
      d.bus.gnt.poke(grant.B)
      if(grant) {
        assert(!high(d.bus.bits.we) && d.bus.bits.origin.peek().litValue==0,"MACHINE_BUS_ORACLE")
        captured=d.bus.bits.addr.peek().litValue.toLong;waitReply=1+random.nextInt(4)
      }
      responding=waitReply==0
      d.bus.rvalid.poke(responding.B);d.bus.rdata.poke(memory.getOrElse(captured,0L).U)
      d.bus.err.poke((responding && !memory.contains(captured)).B)
      val oldPc=oracle.pc;val oldOrder=oracle.order
      d.clk.step();cycles+=1;assert(cycles<16000,"MACHINE_DEADLINE")
      val event=high(d.rvfi.valid);val intr=high(d.interruptTaken)
      val expected=oracle.edge(event,intr,irq)
      if(intr) interrupts+=1
      expected.foreach {e=>
        val v=d.rvfi;retiring+=1
        assert(v.order.peek().litValue==oldOrder && v.pc_rdata.peek().litValue==oldPc &&
          v.insn.peek().litValue==e.insn && v.rd_addr.peek().litValue==e.rd &&
          v.rd_wdata.peek().litValue==e.data && high(v.trap)==e.trap &&
          v.pc_wdata.peek().litValue==e.next && high(v.intr)==e.intr,"MACHINE_ARCH_ORACLE")
        assert(high(d.trace.valid) && d.trace.cause.peek().litValue==e.cause,"MACHINE_CAUSE_ORACLE")
      }
      if(grant) waitGrant= -1 else if(waitGrant>0) waitGrant-=1
      if(responding) waitReply= -1 else if(waitReply>0) waitReply-=1
    }
    d.start.poke(true.B);tick();d.start.poke(false.B)
    def untilSleep(): Unit={while(!high(d.sleeping)) tick();tick();assert(!high(d.bus.req))}
  }
  val operations=setup++Seq(
    i(0x13,2,0,0,0),csr(0x340,3,5,31),csr(0x340,4,6,16),csr(0x340,5,7,1),
    csr(0x340,6,2,0),csr(0x340,7,3,2),csr(0x340,8,1,0),
    csr(0xf11,9,2,0),csr(0xf11,9,2,2),csr(0xf14,0,1,0),
    csr(0x777,1,2,0),csr(0x340,16,2,0),csr(0x340,1,2,16),
    csr(0x300,1,5,8),csr(0x300,1,2,0),csr(0x300,0,7,8),
    csr(0x301,2,1,0),csr(0x301,2,2,0),csr(0x310,3,5,31),csr(0x310,3,2,0),
    csr(0x320,0,5,5),i(0x13,2,0,0,-1),csr(0xb02,0,1,2),csr(0xb82,0,1,0),
    csr(0xb00,0,1,2),csr(0xb80,0,1,0),csr(0xb00,3,2,0),csr(0xb02,4,2,0),
    csr(0x320,0,5,0),csr(0xb80,3,2,0),csr(0xb82,4,2,0),
    0x73L,0x100073L,0x10500073L)
  test("CSR operations, traps, MRET, 64-bit counter carry/inhibit/write priority match independent model") {
    simulateRaw(new LiteHart) {d=>val h=new Driver(d,operations);h.untilSleep();assert(h.retiring>operations.size)}
  }
  test("WFI wake ignores global MIE; IRQ entry waits until whole instruction boundary") {
    val words=setup++Seq(i(0x13,2,0,0,-2048),csr(0x304,0,1,2),0x10500073L,
      i(0x13,3,0,0,7),csr(0x300,0,6,8),0x10500073L,i(0x13,4,0,0,9),0x10500073L)
    // Interrupt handler returns to the saved next PC without adding four.
    simulateRaw(new LiteHart) {d=>
      val h=new Driver(d,words,Seq(csr(0x342,5,2,0),0x30200073L))
      h.untilSleep();assert(h.interrupts==0);h.irq=true
      while(h.interrupts==0) h.tick()
      assert(h.oracle.regs(3)==7,"MACHINE_WFI_MASKED_WAKE")
      h.irq=false;h.untilSleep();assert(h.interrupts==1)
      h.irq=true;while(h.interrupts==1) h.tick();h.irq=false
      h.untilSleep();assert(h.oracle.regs(4)==9 && h.interrupts==2)
    }
  }
  test("actual register-write corruption fails the machine architectural oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new LiteHart(corrupt=true)) {d=>val h=new Driver(d,operations);h.untilSleep()}
    };assert(e.getMessage.contains("MACHINE_ARCH_ORACLE"))
  }
}
