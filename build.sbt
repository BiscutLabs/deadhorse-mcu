// Versions come from tools/env/lock.json through tools/sbt.py.
val repo = file(sys.props.getOrElse("deadhorse.root", sys.error("Use python3 tools/sbt.py")))
def pin(name: String) = sys.props("deadhorse." + name)
def owners(parent: String): Seq[File] =
  Option((repo / parent).listFiles).toSeq.flatten
    .filter(f => f.isDirectory && !f.getName.startsWith("_") && !f.getName.startsWith(".") &&
      !Set("template", "templates", "vendor").contains(f.getName)).toSeq
def sources(kind: String): Seq[File] =
  (Seq(repo / "hw/lib") ++ owners("hw/ip") ++ owners("hw/top"))
    .map(_ / "src" / kind / "scala").filter(_.isDirectory)

ThisBuild / scalaVersion := pin("scala")
ThisBuild / organization := "io.github.biscutlabs.deadhorse"
ThisBuild / version := "0.1.0-SNAPSHOT"

lazy val hw = project.in(file(".")).settings(
  name := "deadhorse-hw",
  target := repo / "build/sbt/hw",
  Compile / unmanagedSourceDirectories := sources("main") ++ Seq(repo / "hw/lib/formal", repo / "hw/ip/bus/formal",
    repo / "hw/ip/bus_bridge/formal", repo / "hw/ip/mailbox/formal", repo / "hw/ip/uart/formal",
    repo / "hw/ip/spi_host/formal", repo / "hw/ip/i2c_host/formal",
    repo / "hw/ip/i2c_recovery_loader/formal", repo / "build/vendor/hardfloat"),
  Test / unmanagedSourceDirectories := sources("test"),
  Compile / unmanagedResourceDirectories := Seq.empty,
  Test / unmanagedResourceDirectories := Seq.empty,
  libraryDependencies ++= Seq(
    "org.chipsalliance" %% "chisel" % pin("chisel"),
    "org.scalatest" %% "scalatest" % pin("scalatest") % Test
  ),
  addCompilerPlugin("org.chipsalliance" % "chisel-plugin" % pin("chisel_plugin") cross CrossVersion.full),
  scalacOptions ++= Seq("-deprecation", "-feature", "-unchecked", "-language:reflectiveCalls"),
  Test / parallelExecution := false,
  Test / fork := true,
  Test / baseDirectory := repo,
  Test / javaOptions ++= Seq("-Xmx2G", "-XX:ActiveProcessorCount=4",
    "-Duser.home=" + (repo / "build/env/home"), "-Djava.io.tmpdir=" + (repo / "build/env/tmp")),
  Compile / run / fork := true,
  Compile / run / baseDirectory := repo,
  Compile / run / javaOptions ++= Seq("-Xmx2G", "-XX:ActiveProcessorCount=4",
    "-Duser.home=" + (repo / "build/env/home"), "-Djava.io.tmpdir=" + (repo / "build/env/tmp")),
  publish / skip := true
)
