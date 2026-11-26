package deadhorse.top

import chisel3._
import deadhorse.lib.ClockGateTarget

/** Physical scan-out landing pins. Insertion replaces each I tie with its
  * chain tail. A PDK BlackBox prevents functional synthesis deleting the pad
  * mux before insertion. Logical simulation defaults unused scan lanes low.
  */
class SocScanHooks(target: ClockGateTarget) extends RawModule {
  val out=IO(Output(UInt(7.W)))
  val lanes=Wire(Vec(7,Bool()))
  for(i<-0 until 7) {
    target match {
      case ClockGateTarget.Asic=>
        val cell=Module(new Gf180ScanOutputCell)
        cell.suggestName(s"lane_$i")
        cell.io.I:=false.B;lanes(i):=cell.io.Z
        dontTouch(cell.io.I);dontTouch(cell.io.Z)
      case _=>lanes(i):=false.B
    }
  }
  out:=lanes.asUInt
}

class Gf180ScanOutputCell extends BlackBox {
  override def desiredName="gf180mcu_fd_sc_mcu7t5v0__buf_1"
  val io=IO(new Bundle {val I=Input(Bool());val Z=Output(Bool())})
}
