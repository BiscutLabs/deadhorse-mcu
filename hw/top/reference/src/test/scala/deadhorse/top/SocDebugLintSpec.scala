package deadhorse.top

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.{Files,Paths}
import org.scalatest.funsuite.AnyFunSuite
import deadhorse.debug.DebugModuleBench

class UnrelatedWarningBench extends DebugModuleBench {
  val limited=IO(Input(UInt(1.W)));val result=IO(Output(Bool()))
  result:=limited<=1.U
}
class SocDebugLintSpec extends AnyFunSuite with ChiselSim {
  for(fault<-Seq("file","message","rule")) test(s"diagnostic exemption does not extend to another $fault") {
    implicit val directory: HasTestingDirectory=new HasTestingDirectory {
      def getDirectory=Paths.get("build/plan04/lint-negative",fault).toAbsolutePath
    }
    implicit val settings: svsim.CommonSettingsModifications=SocDebugLint.settings(directory.getDirectory,fault)
    val failure=intercept[Exception] {simulate(new DebugModuleBench) {_=>fail("Unexpected compile success")}}
    assert(failure.toString.contains("CMPCONST"),failure.toString)
  }
  test("unrelated warning remains fatal with the correct vendor exception") {
    implicit val directory: HasTestingDirectory=new HasTestingDirectory {
      def getDirectory=Paths.get("build/plan04/lint-negative/unrelated").toAbsolutePath
    }
    implicit val settings: svsim.CommonSettingsModifications=SocDebugLint.settings(directory.getDirectory)
    val failure=intercept[Exception] {
      simulate(new UnrelatedWarningBench,firtoolOpts=Array("--disable-opt")) {_=>fail("Unexpected compile success")}
    }
    assert(failure.toString.contains("CMPCONST") && failure.toString.contains("UnrelatedWarningBench.sv"),failure.toString)
  }
  test("emitted source drift rejects the diagnostic exception") {
    implicit val directory: HasTestingDirectory=new HasTestingDirectory {
      def getDirectory=Paths.get("build/plan04/lint-negative/source").toAbsolutePath
    }
    implicit val settings: svsim.CommonSettingsModifications=SocDebugLint.settings(directory.getDirectory)
    simulate(new DebugModuleBench) {_=>()}
    val source=Files.readAllBytes(directory.getDirectory.resolve("primary-sources/dm_csrs.sv"))
    SocDebugLint.verify(source)
    val failure=intercept[IllegalArgumentException] {SocDebugLint.verify(source++Array[Byte](0))}
    assert(failure.getMessage.contains("DEBUG_LINT_SOURCE_DRIFT"))
  }
}
