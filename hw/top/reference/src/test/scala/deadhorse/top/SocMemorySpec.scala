package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim, Randomization, Settings}
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import java.nio.file.{Files, Paths}
import org.scalatest.funsuite.AnyFunSuite

object SocTestFiles {
  val config = "build/t20/map/soc.json"
  def description = new SocDescription(config)
  def romWord(index: Int): BigInt = (BigInt(index) * 0x10203 + 0x13579bdfL) & BigInt("ffffffff", 16)
  def memoryRom: String = {
    val p = Paths.get("build/t20/images/memory.hex").toAbsolutePath
    Files.createDirectories(p.getParent)
    val words = (0 until (description.region("boot_rom").size / 4).toInt).map(i => f"${romWord(i)}%08x")
    Files.writeString(p, words.mkString("\n") + "\n"); p.toString
  }
}

class SocMemorySpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  // ChiselSim otherwise randomizes memories after $readmemh, overwriting ROM.
  // RAM comparisons only follow explicit writes; formal RAM remains arbitrary.
  private val settings = Settings.defaultRaw[SocLocalMemory].copy(
    randomization = Randomization.random.copy(memories = false))
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t20/memory-simulation").toAbsolutePath
  }
  private def high(x: Bool): Boolean = x.peek().litToBoolean
  private def drive(p: LocalBus, address: BigInt, write: Boolean = false,
                    value: BigInt = 0, mask: Int = 15, origin: Int = 1): Unit = {
    p.req.poke(true.B); p.bits.addr.poke(address.U); p.bits.we.poke(write.B)
    p.bits.wdata.poke(value.U); p.bits.be.poke(mask.U); p.bits.origin.poke(origin.U)
  }
  private def reset(d: SocLocalMemory): Unit = {
    drive(d.instruction, 0); drive(d.data, 0)
    d.instruction.req.poke(false.B); d.data.req.poke(false.B)
    d.peripheral.gnt.poke(false.B); d.peripheral.rvalid.poke(false.B)
    d.peripheral.err.poke(false.B); d.peripheral.rdata.poke(0.U)
    d.serviceReset_n.poke(false.B); d.clientReset_n.poke(false.B); d.clk.step(2)
    d.serviceReset_n.poke(true.B); d.clientReset_n.poke(true.B); d.clk.step(4)
    assert(high(d.epochReady))
  }
  private def transact(d: SocLocalMemory, address: BigInt, write: Boolean = false,
                       value: BigInt = 0, mask: Int = 15, origin: Int = 1,
                       latency: Int = 1): (BigInt, Boolean) = {
    drive(d.data, address, write, value, mask, origin)
    var wait = 0
    while(!high(d.data.gnt)) { d.clk.step(); wait += 1; assert(wait < 12, "MEMORY_GRANT_TIMEOUT") }
    d.clk.step(); d.data.req.poke(false.B)
    for(_ <- 1 until latency) { assert(!high(d.data.rvalid), "EARLY_MEMORY_RESPONSE"); d.clk.step() }
    assert(high(d.data.rvalid), "MEMORY_RESPONSE_LATENCY")
    val result = (d.data.rdata.peek().litValue, high(d.data.err))
    d.clk.step(); assert(!high(d.data.rvalid), "DUPLICATE_MEMORY_RESPONSE")
    result
  }
  private def fetchCheck(d: SocLocalMemory): Unit = {
    reset(d)
    for(index <- 0 until 40) {
      drive(d.instruction, index * 4)
      assert(high(d.instruction.gnt), "FETCH_BUBBLE")
      d.clk.step()
      assert(high(d.instruction.rvalid) && !high(d.instruction.err))
      assert(d.instruction.rdata.peek().litValue == SocTestFiles.romWord(index), "ROM_DATA_MODEL")
    }
    d.instruction.req.poke(false.B); d.clk.step()
    assert(!high(d.instruction.rvalid))
  }
  test("one-edge ROM replies sustain consecutive native fetches") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom), settings = settings)(fetchCheck)
  }
  test("corrupted memory response is rejected by the same independent ROM oracle") {
    val caught = intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom) {
        override protected def returned(value: UInt): UInt = value ^ 1.U
      }, settings = settings)(fetchCheck)
    }
    assert(caught.getMessage.contains("ROM_DATA_MODEL"))
  }
  for((banks, latency) <- Seq((1,1), (4,1), (4,3))) {
    test(s"byte masks, banks, errors and retained RAM; banks=$banks latency=$latency") {
      simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom, banks, latency), settings = settings) { d =>
        reset(d)
        val base = SocTestFiles.description.region("performance_sram").base
        val offsets = Seq(0,4,8,12,16,0x3ffc)
        val expected = scala.collection.mutable.Map.empty[Int, BigInt]
        for(offset <- offsets) {
          val word = BigInt("a1b2c3d4",16) ^ offset
          assert(transact(d, base+offset, true, word, latency=latency) == (BigInt(0), false))
          expected(offset) = word
        }
        for(mask <- 0 until 16; offset <- offsets) {
          val word = BigInt("10203040",16) + mask
          assert(transact(d, base+offset, true, word, mask, latency=latency) == (BigInt(0), false))
          for(lane <- 0 until 4 if (mask & (1 << lane)) != 0) {
            val bits = BigInt(255) << (lane*8)
            expected(offset) = (expected(offset) & ~bits) | (word & bits)
          }
          assert(transact(d, base+offset, latency=latency) == (expected(offset), false), "BYTE_MEMORY_ORACLE")
        }
        for((addr, origin) <- Seq((base+1,1), (base,0), (BigInt(0),1))) {
          assert(transact(d, addr, true, 0, origin=origin, latency=latency) == (BigInt(0), true))
        }
        d.clientReset_n.poke(false.B); d.clk.step(2); d.clientReset_n.poke(true.B); d.clk.step(4)
        for(offset <- offsets) assert(transact(d, base+offset, latency=latency) == (expected(offset), false))
        d.serviceReset_n.poke(false.B); d.clk.step(2); d.serviceReset_n.poke(true.B); d.clk.step(4)
        for(offset <- offsets) assert(transact(d, base+offset, latency=latency) == (expected(offset), false))
      }
    }
  }
  test("current-request arbitration serves contention and excludes the MMIO response edge") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom), settings=settings) { d =>
      reset(d)
      drive(d.instruction, 0); drive(d.data, 4)
      // Reset gives instruction first choice; a completed fetch gives data next choice.
      assert(high(d.instruction.gnt) && !high(d.data.gnt))
      d.clk.step()
      assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue == SocTestFiles.romWord(0))
      assert(!high(d.instruction.gnt) && high(d.data.gnt))
      d.clk.step(); d.data.req.poke(false.B)
      assert(high(d.data.rvalid) && d.data.rdata.peek().litValue == SocTestFiles.romWord(1))
      assert(high(d.instruction.gnt) && !high(d.data.gnt))
      d.clk.step(); d.instruction.req.poke(false.B)
      drive(d.data, SocTestFiles.description.region("uart0").base)
      assert(high(d.data.gnt) && !high(d.instruction.gnt))
      d.clk.step(); d.data.req.poke(false.B)
      d.peripheral.gnt.poke(true.B); d.clk.step(); d.peripheral.gnt.poke(false.B)
      // Hold the next request from before completion through the public reply.
      drive(d.data, 8)
      assert(!high(d.data.gnt))
      d.peripheral.rvalid.poke(true.B); d.peripheral.rdata.poke(0x1234.U)
      d.clk.step(); d.peripheral.rvalid.poke(false.B)
      assert(high(d.data.rvalid) && d.data.rdata.peek().litValue == 0x1234)
      assert(!high(d.data.gnt), "NEW_ACCEPT_OVERLAPS_MMIO_RESPONSE")
      d.clk.step()
      assert(!high(d.data.rvalid) && high(d.data.gnt))
      d.clk.step(); d.data.req.poke(false.B)
      assert(high(d.data.rvalid) && d.data.rdata.peek().litValue == SocTestFiles.romWord(2))
      d.clientReset_n.poke(false.B)
      d.epochReady.expect(false.B); d.instruction.gnt.expect(false.B); d.data.gnt.expect(false.B)
    }
  }
  test("stalled MMIO retains payload, allows fetch, and drains across a short core reset") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom), settings = settings) { d =>
      reset(d)
      val address = SocTestFiles.description.region("uart0").base
      drive(d.data, address, true, 0x51)
      while(!high(d.data.gnt)) d.clk.step()
      d.clk.step(); d.data.req.poke(false.B)
      assert(high(d.peripheral.req))
      for(index <- 0 until 8) {
        assert(d.peripheral.bits.addr.peek().litValue == address && d.peripheral.bits.wdata.peek().litValue == 0x51)
        drive(d.instruction, index * 4); assert(high(d.instruction.gnt)); d.clk.step()
        assert(high(d.instruction.rvalid) && d.instruction.rdata.peek().litValue == SocTestFiles.romWord(index))
      }
      d.instruction.req.poke(false.B)
      d.clientReset_n.poke(false.B)
      assert(!high(d.epochReady) && !high(d.data.rvalid))
      d.clientReset_n.poke(true.B) // No service edge during assertion.
      d.clk.step(4)
      assert(!high(d.epochReady) && high(d.peripheral.req))
      d.peripheral.gnt.poke(true.B); d.clk.step(); d.peripheral.gnt.poke(false.B)
      assert(!high(d.peripheral.req))
      d.peripheral.rvalid.poke(true.B); d.peripheral.rdata.poke(123.U); d.clk.step()
      assert(!high(d.data.rvalid), "ORPHAN_RESPONSE_ESCAPED")
      d.peripheral.rvalid.poke(false.B); d.clk.step(4)
      assert(high(d.epochReady) && !high(d.peripheral.req) && !high(d.data.rvalid))
      assert(transact(d, 0) == (SocTestFiles.romWord(0), false))
    }
  }
  for(latency <- Seq(1, 3)) {
    test(s"concurrent instruction/data arbitration preserves ordered replies; latency=$latency") {
      simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom,
        readLatency=latency), settings=settings) { d =>
        reset(d)
        val base = SocTestFiles.description.region("performance_sram").base
        val stored = BigInt("01234567",16)
        assert(transact(d, base, true, stored, latency=latency) == (BigInt(0), false))
        val expectedI = scala.collection.mutable.Queue.empty[(Int,BigInt)]
        val expectedD = scala.collection.mutable.Queue.empty[(Int,BigInt)]
        var iCount=0; var dCount=0; var iWait=0; var dWait=0; var dPending=false
        for(cycle <- 0 until 160) {
          val ramFetch = iCount % 2 == 0
          drive(d.instruction, if(ramFetch) base else BigInt((iCount % 40)*4))
          drive(d.data, (dCount % 40)*4)
          d.data.req.poke((!dPending).B)
          val iFire=high(d.instruction.gnt)
          val dFire= !dPending && high(d.data.gnt)
          assert(!(iFire && dFire), "DOUBLE_GRANT")
          if(iFire) { expectedI.enqueue((cycle+latency, if(ramFetch) stored else SocTestFiles.romWord(iCount%40))); iCount+=1; iWait=0 }
          else { iWait+=1; assert(iWait <= 2, "INSTRUCTION_STARVATION") }
          if(dFire) { expectedD.enqueue((cycle+latency,SocTestFiles.romWord(dCount%40))); dPending=true; dCount+=1; dWait=0 }
          else if(!dPending) { dWait+=1; assert(dWait <= 4, "DATA_STARVATION") }
          d.clk.step()
          def check(bus: LocalBus, queue: scala.collection.mutable.Queue[(Int,BigInt)]): Boolean = {
            val due=queue.headOption.exists(_._1 == cycle+1)
            assert(high(bus.rvalid)==due, "RESPONSE_SCHEDULE")
            if(due) { assert(!high(bus.err) && bus.rdata.peek().litValue==queue.dequeue()._2, "ARBITRATION_DATA_MODEL") }
            due
          }
          check(d.instruction,expectedI)
          if(check(d.data,expectedD)) dPending=false
        }
        assert(iCount > 40 && dCount > 15)
      }
    }
  }
  test("client reset cancels a pipelined local reply and drains before the new epoch") {
    simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom,
      readLatency=3), settings=settings) { d =>
      reset(d)
      drive(d.instruction, 4); assert(high(d.instruction.gnt))
      d.clk.step(); d.instruction.req.poke(false.B)
      assert(!high(d.instruction.rvalid)) // Accepted, still in the three-edge pipeline.
      d.clientReset_n.poke(false.B)
      // Force simulator evaluation of assertion before deasserting the pulse.
      d.epochReady.expect(false.B); d.instruction.rvalid.expect(false.B)
      d.clientReset_n.poke(true.B)
      for(_ <- 0 until 6) { d.clk.step(); assert(!high(d.instruction.rvalid), "INSTRUCTION_ORPHAN") }
      assert(high(d.epochReady))
      drive(d.data, 0)
      while(!high(d.data.gnt)) d.clk.step()
      d.clk.step(); d.data.req.poke(false.B); d.instruction.req.poke(false.B)
      d.clientReset_n.poke(false.B)
      assert(!high(d.epochReady) && !high(d.data.rvalid) && !high(d.instruction.rvalid))
      d.clientReset_n.poke(true.B)
      for(_ <- 0 until 6) { d.clk.step(); assert(!high(d.data.rvalid) && !high(d.instruction.rvalid), "LOCAL_ORPHAN") }
      assert(high(d.epochReady))
      assert(transact(d,8,latency=3)==(SocTestFiles.romWord(2),false))
    }
  }
  for(resetAt <- Seq(-1, 0, 1)) {
    test(s"issued MMIO response across client reset boundary $resetAt") {
      simulateRaw(new SocLocalMemory(SocTestFiles.description, SocTestFiles.memoryRom), settings=settings) { d =>
        reset(d); drive(d.data,SocTestFiles.description.region("uart0").base)
        while(!high(d.data.gnt)) d.clk.step()
        d.clk.step(); d.data.req.poke(false.B)
        d.peripheral.gnt.poke(true.B); d.clk.step(); d.peripheral.gnt.poke(false.B)
        assert(!high(d.peripheral.req))
        if(resetAt == 0) {
          d.clientReset_n.poke(false.B); d.clk.step(); d.clientReset_n.poke(true.B)
          d.clk.step(2); assert(!high(d.epochReady))
        }
        d.peripheral.rvalid.poke(true.B); d.peripheral.rdata.poke(0x12345678.U)
        if(resetAt == 1) d.clientReset_n.poke(false.B)
        d.clk.step()
        if(resetAt < 0) { assert(high(d.data.rvalid) && d.data.rdata.peek().litValue==0x12345678 && !high(d.data.err)) }
        else assert(!high(d.data.rvalid), "REMOTE_ORPHAN")
        d.peripheral.rvalid.poke(false.B); d.clientReset_n.poke(true.B)
        for(_ <- 0 until 5) { d.clk.step(); assert(!high(d.data.rvalid)) }
        assert(high(d.epochReady))
        assert(transact(d,12)==(SocTestFiles.romWord(3),false))
      }
    }
  }
}
