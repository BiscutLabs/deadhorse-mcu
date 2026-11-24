package deadhorse.top

import java.nio.file.{Files,Path,Paths}
import java.nio.charset.StandardCharsets.UTF_8

/** Reuse T32's reviewed two-hart constant-selector diagnostic exception only
  * for the exact emitted copy of the pinned vendor file at the reviewed line.
  * Every other warning remains fatal. This audits tool inputs, not behavior. */
object SocDebugLint {
  // firtool adds its pinned version header and the BlackBox source location.
  private val expected="ec518e6a19ba8d3b6c75aa8f005baae89f510eb60c035d76a0c7bf11ee04f0a8"
  def digest(bytes: Array[Byte]): String=java.security.MessageDigest.getInstance("SHA-256")
    .digest(bytes).map(b=>f"${b & 255}%02x").mkString
  def verify(bytes: Array[Byte]): Unit=require(digest(bytes)==expected,"DEBUG_LINT_SOURCE_DRIFT")
  def settings(directory: => Path,fault: String="none"): svsim.CommonSettingsModifications = s=> {
    require(Set("none","message","file","rule").contains(fault))
    val dir=directory.toAbsolutePath.normalize
    require(dir.startsWith(Paths.get("build").toAbsolutePath.normalize))
    val source=dir.resolve("primary-sources/dm_csrs.sv")
    // No vendor DM in a minimal fixture means no diagnostic exception needed.
    if(!Files.exists(source)) s else {
      verify(Files.readAllBytes(source))
      // This reviewed wrapper instantiates NrHarts=2. Fail closed if its
      // elaboration parameters change even when the vendor file is unchanged.
      require(digest(Files.readAllBytes(Paths.get("hw/ip/debug/src/main/scala/deadhorse/debug/DebugVendor.scala")))==
        "52583c538902eabc4efd154c43e3390edccfbd344a37b2eddbaceed6db02b9e4","DEBUG_LINT_WRAPPER_DRIFT")
      val lock=ujson.read(Files.readString(Paths.get("hw/vendor/riscv_dbg/riscv_dbg.lock.json")))
      require(lock("parameters")("NrHarts").num==2)
      val control=dir.resolve("primary-sources/debug-selector.vlt")
      val rule=if(fault=="rule") "WIDTH" else "CMPCONST"
      val file=if(fault=="file") dir.resolve("unrelated.sv") else
        dir.resolve("workdir-verilator/../primary-sources/dm_csrs.sv")
      val message=if(fault=="message") "Unrelated diagnostic*" else "Comparison is constant due to limited range*"
      Files.writeString(control,"`verilator_config\n"+
        s"lint_off -rule $rule -file \"$file\" -match \"$message\"\n",UTF_8)
      s.copy(fileFilter={case f if f.getName=="debug-selector.vlt"=>true
        case f=>s.fileFilter.applyOrElse(f,(_: java.io.File)=>true)})
    }
  }
}

trait SocDebugLintConfiguration {
  implicit def socDebugLint(implicit directory: chisel3.testing.HasTestingDirectory): svsim.CommonSettingsModifications=
    SocDebugLint.settings(directory.getDirectory)
}
