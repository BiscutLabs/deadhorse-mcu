package deadhorse.perf_core

import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

object EmitLeaves {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "Usage: EmitLeaves build/<output>")
    val output = Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    val options = Array("--disable-all-randomization", "-strip-debug-info", "--preserve-values=named")
    ChiselStage.emitSystemVerilogFile(new IbexCsr,
      Array("--target-dir", output.resolve("csr").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexCounter,
      Array("--target-dir", output.resolve("counter").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexCounter(64, false),
      Array("--target-dir", output.resolve("mcycle").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexCounter(64, true),
      Array("--target-dir", output.resolve("minstret").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexCsr(8, true, 0xa5),
      Array("--target-dir", output.resolve("shadow").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexAlu,
      Array("--target-dir", output.resolve("alu").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexRegisterFile,
      Array("--target-dir", output.resolve("register_file").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexCompressedDecoder,
      Array("--target-dir", output.resolve("compressed_decoder").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexFetchFifo,
      Array("--target-dir", output.resolve("fetch_fifo").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexPrefetchBuffer,
      Array("--target-dir", output.resolve("prefetch_buffer").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexMultdivFast,
      Array("--target-dir", output.resolve("multdiv_fast").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexMultdivFast(iterativeMultiply = true),
      Array("--target-dir", output.resolve("multdiv_iterative").toString), options)
    ChiselStage.emitSystemVerilogFile(new IterativeMultiply,
      Array("--target-dir", output.resolve("iterative_multiply").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexExBlock,
      Array("--target-dir", output.resolve("ex_block").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexExBlock(localDivisionArithmetic = true),
      Array("--target-dir", output.resolve("ex_repaired").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexExBlock(iterativeMultiply = true, localDivisionArithmetic = true),
      Array("--target-dir", output.resolve("ex_iterative").toString), options)
    ChiselStage.emitSystemVerilogFile(new ClockedExecute,
      Array("--target-dir", output.resolve("clocked_execute").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexDecoder,
      Array("--target-dir", output.resolve("decoder").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexLoadStoreUnit,
      Array("--target-dir", output.resolve("load_store_unit").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexIfStage,
      Array("--target-dir", output.resolve("if_stage").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexController,
      Array("--target-dir", output.resolve("controller").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexWbStage,
      Array("--target-dir", output.resolve("wb_stage").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexCsRegisters,
      Array("--target-dir", output.resolve("cs_registers").toString), options)
    ChiselStage.emitSystemVerilogFile(new IbexIdStage,
      Array("--target-dir", output.resolve("id_stage").toString), options)
  }
}
