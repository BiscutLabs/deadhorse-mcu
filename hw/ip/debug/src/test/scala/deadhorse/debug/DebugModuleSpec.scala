package deadhorse.debug
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Full adopted two-hart DM at its DMI and instruction/data ports. */
class DebugModuleBench(lostReset: Boolean=false) extends Module {
  val hartReset=IO(Input(UInt(2.W)))
  val request=IO(Input(UInt(41.W)));val requestValid=IO(Input(Bool()));val requestReady=IO(Output(Bool()))
  val response=IO(Output(UInt(34.W)));val responseValid=IO(Output(Bool()));val responseReady=IO(Input(Bool()))
  val memRequest=IO(Input(Bool()));val memWrite=IO(Input(Bool()));val address=IO(Input(UInt(32.W)))
  val value=IO(Input(UInt(32.W)));val readData=IO(Output(UInt(32.W)))
  val owner=IO(Output(UInt(20.W)));val busy=IO(Output(Bool()))
  val d=Module(new DebugModule)
  d.io.clk_i:=clock;d.io.rst_ni:= !reset.asBool;d.io.dmi_rst_ni:= !reset.asBool;d.io.testmode_i:=false.B
  d.io.next_dm_addr_i:=0.U;d.io.hartinfo_i:=((BigInt(2)<<52)|(BigInt(2)<<20)).U
  d.io.hart_reset_i:=(if(lostReset) 0.U else hartReset);d.io.unavailable_i:=hartReset
  d.io.ndmreset_ack_i:=false.B
  d.io.dmi_req_i:=request;d.io.dmi_req_valid_i:=requestValid;requestReady:=d.io.dmi_req_ready_o
  response:=d.io.dmi_resp_o;responseValid:=d.io.dmi_resp_valid_o;d.io.dmi_resp_ready_i:=responseReady
  d.io.slave_req_i:=memRequest;d.io.slave_we_i:=memWrite;d.io.slave_addr_i:=address
  d.io.slave_wdata_i:=value;d.io.slave_be_i:=15.U;readData:=d.io.slave_rdata_o
  d.io.master_gnt_i:=false.B;d.io.master_r_valid_i:=false.B;d.io.master_r_err_i:=false.B
  d.io.master_r_other_err_i:=false.B;d.io.master_r_rdata_i:=0.U
  owner:=d.io.command_hart_o;busy:=d.io.command_busy_o
}
class DebugModuleSpec extends AnyFunSuite with ChiselSim {
  // Reviewed adopted-code diagnostic: with two harts, the one-bit selector is
  // necessarily <= 1 (dm_csrs selected_hart_valid). Keep every other warning
  // fatal, all runtime assertions enabled, and production parameters unchanged.
  implicit val backendSettings:svsim.BackendSettingsModifications = {
    case s:svsim.verilator.Backend.CompilationSettings => s.withDisabledWarnings(s.disabledWarnings :+ "CMPCONST")
    case s => s
  }
  def exercise(fault:Boolean):Unit={
   implicit val outputDirectory:HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t32/dm-unit04",if(fault) "lost-reset" else "correct").toAbsolutePath
   }
   simulate(new DebugModuleBench(fault)) { d=>
    d.hartReset.poke(0.U);d.request.poke(0.U);d.requestValid.poke(false.B);d.responseReady.poke(true.B)
    d.memRequest.poke(false.B);d.memWrite.poke(false.B);d.address.poke(0.U);d.value.poke(0.U)
    d.reset.poke(true.B);d.clock.step(3);d.reset.poke(false.B);d.clock.step(3)
    def dmi(address:Int,value:BigInt=0,write:Boolean=false,onAccept:()=>Unit=()=>()):BigInt={
      // dm::dmi_req_t is {address, operation, data}; the TAP scan register's
      // {address, data, operation} layout is converted before this interface.
      d.request.poke(((BigInt(address)<<34)|(BigInt(if(write) 2 else 1)<<32)|value).U)
      d.requestValid.poke(true.B)
      var n=0;while(!d.requestReady.peek().litToBoolean && n<32){d.clock.step();n+=1}
      assert(n<32,"DMI grant");onAccept();d.clock.step();d.requestValid.poke(false.B)
      n=0;while(!d.responseValid.peek().litToBoolean && n<32){d.clock.step();n+=1}
      assert(n<32,"DMI response");val result=d.response.peek().litValue
      assert((result&3)==0,"DMI response error");d.clock.step();result>>2
    }
    def select(hart:Int):Unit={dmi(0x10,1|(hart<<16),true)}
    def store(address:Int,value:Int):Unit={
      d.address.poke(address.U);d.value.poke(value.U);d.memWrite.poke(true.B);d.memRequest.poke(true.B)
      d.clock.step();d.memRequest.poke(false.B);d.memWrite.poke(false.B)
    }
    def status(hart:Int):BigInt={select(hart);dmi(0x11)}
    select(0);store(0x10100,0);store(0x10100,1)
    assert((status(0)&0x300)==0x300 && (status(1)&0x300)==0x300,"both halted")
    d.hartReset.poke(2.U);store(0x10100,1);d.clock.step();d.hartReset.poke(0.U)
    val resetStatus=status(1)
    assert((resetStatus&0xc0000)==0xc0000 && (resetStatus&0x300)==0,"DM_RESET_STATUS: reset must win over HALTED")
    store(0x10100,1)
    // Clear initial havereset, then issue a real access-register command for lite.
    for(h<-0 to 1) dmi(0x10,0x10000001L|(h<<16),true)
    select(0);dmi(0x17,0x00221001,true);d.busy.expect(true.B);d.owner.expect(0.U)
    // Reset the unselected performance hart while reporting it HALTED.
    d.hartReset.poke(2.U);store(0x10100,1);d.clock.step();d.hartReset.poke(0.U)
    d.busy.expect(true.B);d.owner.expect(0.U)
    // The adopted DM freezes hartsel while abstractcs.busy. Attempting to
    // select another hart must leave the command and its public selection alone.
    select(1)
    assert((dmi(0x10)&0x10000)==0,"busy command changed selected hart")
    d.busy.expect(true.B);d.owner.expect(0.U)
    // Execute owner GOING, then collide owner HALTED completion with owner reset.
    store(0x10108,0);d.hartReset.poke(1.U);store(0x10100,0);d.clock.step();d.hartReset.poke(0.U)
    d.busy.expect(false.B)
    val abstractcs=dmi(0x16)
    assert(((abstractcs>>8)&7)==4,"owner reset did not report halt/resume error")
    // A reset on the acceptance edge must beat ackhavereset for that same hart.
    select(0)
    dmi(0x10,0x10000001L,true,()=>d.hartReset.poke(1.U))
    d.hartReset.poke(0.U)
    assert((dmi(0x11)&0xc0000)==0xc0000,"ackhavereset overtook reset")
    dmi(0x10,0x10000001L,true)
    assert((dmi(0x11)&0xc0000)==0,"ackhavereset did not recover")
    assert((status(1)&0xc0000)==0xc0000,"other-hart reset history was cleared")
   }
  }
  test("full DM preserves command ownership and gives per-hart reset priority over status and acknowledgement") {exercise(false)}
  test("lost per-hart reset connection is rejected by the DMI status oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException](exercise(true))
    assert(e.getMessage.contains("DM_RESET_STATUS"))
  }
}
