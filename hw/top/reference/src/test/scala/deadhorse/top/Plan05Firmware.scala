package deadhorse.top
import java.nio.file.{Files,Paths}

/** Authenticate diagnostic firmware and its generation inputs before elaboration. */
object Plan05Firmware {
  def checked(image: String): String={
    val path=Paths.get(image);val directory=path.getParent
    val receipt=ujson.read(Files.readString(directory.resolve("result.json")))
    require(receipt("status").str=="built_not_simulated","PLAN05_FIRMWARE_BUILD_STATUS")
    def hash(p: java.nio.file.Path)=SocDebugLint.digest(Files.readAllBytes(p))
    val sources=receipt.obj.getOrElse("source_sha256",receipt.obj.getOrElse("sources",ujson.Obj()))
    require(sources.obj.nonEmpty,"PLAN05_FIRMWARE_EMPTY_SOURCES")
    for((name,digest)<-sources.obj) require(hash(Paths.get(name))==digest.str,s"PLAN05_FIRMWARE_SOURCE_DRIFT $name")
    for((name,digest)<-receipt("artifacts").obj) require(hash(directory.resolve(name))==digest.str,s"PLAN05_FIRMWARE_ARTIFACT_DRIFT $name")
    require(receipt("artifacts").obj.contains(path.getFileName.toString),"PLAN05_FIRMWARE_UNBOUND_ROM")
    path.toAbsolutePath.toString
  }
}
