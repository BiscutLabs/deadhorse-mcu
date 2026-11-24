package deadhorse.sram

import chisel3._
import chisel3.util._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Real CSR adapter/controller; only the memory fault source is a test fixture. */
class SramStatusBench extends RawModule {
  val clk=IO(Input(Clock()));val aonClock=IO(Input(Clock()));val epoch_n=IO(Input(Bool()))
  val transport_n=IO(Input(Bool()));val ndm=IO(Input(Bool()))
  val request=IO(Flipped(Decoupled(UInt(41.W))));val response=IO(Decoupled(UInt(34.W)))
  val main=IO(new SramPort(12));val aon=IO(new SramPort(12));val held=IO(Output(Bool()))
  val regs=Module(new SramDmi("build/t20/i1/sram/sram_regs.json"))
  val owner=Module(new SramBist)
  regs.clk:=clk;regs.reset_n:=transport_n;regs.epoch_n:=epoch_n
  regs.request<>request;regs.response<>response
  owner.clk:=clk;owner.aonClock:=aonClock;owner.epoch_n:=epoch_n
  owner.start:=regs.start;owner.keyed:=regs.keyed;owner.authorized:=ndm
  owner.mainReset_n:= !(ndm || owner.resetHold);owner.aonReset_n:= !(ndm || owner.resetHold)
  regs.busy:=owner.busy;regs.done:=owner.done;regs.failed:=owner.failed;regs.rejected:=owner.rejected
  regs.resetAck:=owner.resetAck;regs.failAddress:=owner.failAddress;regs.result:=owner.result
  main<>owner.main;aon<>owner.aon;held:=owner.resetHold
}

class SramStatusSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t35/status").toAbsolutePath
  }
  test("full-size test records read-path faults for every performance bank and retained RAM over DMI") {
    simulateRaw(new SramStatusBench) {d=>
      def high(b: Bool)=b.peek().litToBoolean
      val m=Array.fill[BigInt](4096)(0);val a=Array.fill[BigInt](768)(0)
      var fault=0
      def memory(port: SramPort,array: Array[BigInt],remote: Boolean): Option[BigInt]={
        if(!high(port.enable)) None else {
          d.held.expect(true.B)
          val address=port.address.peek().litValue.toInt
          if(high(port.write)) {array(address)=port.data.peek().litValue;None}
          else Some(array(address) ^ (if((remote && fault==4 && address==767) ||
              (!remote && fault<4 && address==4092+fault)) BigInt(1)<<24 else BigInt(0)))
        }
      }
      def step(n: Int=1): Unit=for(_<-0 until n) {
        val r=memory(d.main,m,false);d.clk.step();r.foreach(v=>d.main.result.poke(v.U))
        val s=memory(d.aon,a,true);d.aonClock.step();s.foreach(v=>d.aon.result.poke(v.U))
      }
      d.epoch_n.poke(false.B);d.transport_n.poke(false.B);d.ndm.poke(false.B)
      d.request.valid.poke(false.B);d.request.bits.poke(0.U);d.response.ready.poke(true.B)
      d.main.result.poke(0.U);d.aon.result.poke(0.U)
      step(4);d.epoch_n.poke(true.B);d.transport_n.poke(true.B);d.ndm.poke(true.B);step(12)
      def access(address: Int,data: BigInt=0,write: Boolean=false): BigInt={
        val packet=(BigInt(address)<<34)|(BigInt(if(write) 2 else 1)<<32)|data
        d.request.bits.poke(packet.U);d.request.valid.poke(true.B)
        var wait=0;while(!high(d.request.ready) && wait<32) {step();wait+=1}
        assert(wait<32,"DMI_GRANT");step();d.request.valid.poke(false.B);wait=0
        while(!high(d.response.valid) && wait<32) {step();wait+=1}
        assert(wait<32,"DMI_REPLY")
        val value=d.response.bits.peek().litValue;assert((value&3)==0,"DMI_ERROR");step();value>>2
      }
      for(index<-0 until 5) {
        fault=index
        access(0x70,BigInt("42535431",16),true)
        // Preserve an active test through a transport epoch reset.
        d.transport_n.poke(false.B);step(3);d.transport_n.poke(true.B)
        var status=access(0x71);var ticks=0
        while((status&1)!=0 && ticks<70000) {step(64);ticks+=64;status=access(0x71)}
        assert((status&7)==6,"BIST_FAULT_STATUS")
        val expected=if(index==4) BigInt("30000bfc",16) else BigInt("20003ff0",16)+4*index
        assert(access(0x72)==expected,"BIST_FAULT_ADDRESS")
        assert(access(0x73)==0 && access(0x74)==(BigInt(1)<<24),"BIST_FAULT_DATA")
        assert(access(0x75)==1,"BIST_FAULT_PHASE")
      }
    }
  }
}
