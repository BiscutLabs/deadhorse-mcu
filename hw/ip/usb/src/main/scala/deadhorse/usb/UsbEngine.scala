package deadhorse.usb

import chisel3._
import chisel3.util._
import deadhorse.lib.ResetRelease
import java.nio.file.Paths

/** Only the locked SIE/PHY enters production as vendor RTL. */
class UsbSie(bulkPacketBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends BlackBox(Map("IN_CTRL_MAXPACKETSIZE" -> 8,
  "IN_BULK_MAXPACKETSIZE" -> bulkPacketBytes, "BIT_SAMPLES" -> 4)) with HasBlackBoxPath {
  UsbPacketGeometry(bulkPacketBytes)
  override def desiredName = "sie"
  val io = IO(new Bundle {
    val clk_i = Input(Clock()); val rstn_i = Input(Bool()); val clk_gate_i = Input(Bool())
    val frame_o = Output(UInt(11.W)); val bus_reset_o = Output(Bool()); val endp_o = Output(UInt(4.W))
    val stall_i = Input(Bool()); val out_data_o = Output(UInt(8.W)); val out_valid_o = Output(Bool())
    val out_err_o = Output(Bool()); val setup_o = Output(Bool()); val out_ready_o = Output(Bool())
    val out_nak_i = Input(Bool()); val in_req_o = Output(Bool()); val in_ready_o = Output(Bool())
    val in_data_ack_o = Output(Bool()); val in_valid_i = Input(Bool()); val in_data_i = Input(UInt(8.W))
    val in_zlp_i = Input(Bool()); val in_nak_i = Input(Bool()); val usb_en_i = Input(Bool())
    val usb_detach_i = Input(Bool()); val addr_i = Input(UInt(7.W))
    val in_bulk_endps_i = Input(UInt(16.W)); val out_bulk_endps_i = Input(UInt(16.W))
    val in_int_endps_i = Input(UInt(16.W)); val out_int_endps_i = Input(UInt(16.W))
    val in_iso_endps_i = Input(UInt(16.W)); val out_iso_endps_i = Input(UInt(16.W))
    val in_toggle_reset_i = Input(UInt(16.W)); val out_toggle_reset_i = Input(UInt(16.W))
    val dp_pu_o = Output(Bool()); val tx_en_o = Output(Bool())
    val dp_tx_o = Output(Bool()); val dn_tx_o = Output(Bool())
    val dp_rx_i = Input(Bool()); val dn_rx_i = Input(Bool())
  })
  for (file <- Seq("sie.v","phy_rx.v","phy_tx.v"))
    addPath(Paths.get("build/vendor/usb/rtl",file).toAbsolutePath.toString)
}

class UsbEngine(vid: Int = 0, pid: Int = 0, bulkPacketBytes: Int = UsbPacketSizing.bulkMaxPacketBytes) extends RawModule {
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool())); val vbus = IO(Input(Bool()))
  val dpRx = IO(Input(Bool())); val dnRx = IO(Input(Bool()))
  val dpTx = IO(Output(Bool())); val dnTx = IO(Output(Bool())); val txEnable = IO(Output(Bool()))
  val pullup = IO(Output(Bool()))
  val txData = IO(Input(UInt(8.W))); val txValid = IO(Input(Bool())); val txReady = IO(Output(Bool()))
  val rxData = IO(Output(UInt(8.W))); val rxValid = IO(Output(Bool())); val rxReady = IO(Input(Bool()))
  val configured = IO(Output(Bool())); val frame = IO(Output(UInt(11.W)))
  val sessionReset = IO(Output(Bool())); val attached = IO(Output(Bool()))
  val txReset = IO(Output(Bool())); val rxReset = IO(Output(Bool()))
  val txEmpty = IO(Output(Bool())); val rxEmpty = IO(Output(Bool()))

  val release = Module(new ResetRelease)
  release.clk := clk; release.reset_n := reset_n && vbus
  val engineReset = release.released
  val sie = Module(new UsbSie(bulkPacketBytes))
  val control = Module(new UsbControl(vid,pid,bulkPacketBytes))
  val in = Module(new UsbInBuffer(packetBytes=bulkPacketBytes)); val out = Module(new UsbOutBuffer(packetBytes=bulkPacketBytes))
  control.clk := clk; control.reset_n := engineReset
  in.clk := clk; out.clk := clk
  sie.io.clk_i := clk; sie.io.rstn_i := engineReset
  val cadence=Module(new UsbBitEnable);cadence.clk:=clk;cadence.reset_n:=engineReset
  control.bitEnable:=cadence.enable;in.bitEnable:=cadence.enable;out.bitEnable:=cadence.enable
  sie.io.clk_gate_i:=cadence.enable
  // Cut the vendor combinational packet decode from endpoint admission. These
  // sample-clock stages settle before the following protocol-enable edge.
  def packetFlag(value: Bool): Bool=withClockAndReset(clk,(!engineReset).asAsyncReset){RegNext(value,false.B)}
  val packetData=withClockAndReset(clk,(!engineReset).asAsyncReset){RegNext(sie.io.out_data_o,0.U)}
  control.busReset := sie.io.bus_reset_o
  control.inRequest := packetFlag(sie.io.in_req_o && sie.io.endp_o === 0.U)
  control.inReady := packetFlag(sie.io.in_ready_o && sie.io.endp_o === 0.U)
  control.inAck := packetFlag(sie.io.in_data_ack_o)
  control.setup := packetFlag(sie.io.setup_o)
  control.outReady := packetFlag(sie.io.out_ready_o && sie.io.endp_o === 0.U)
  control.outData := packetData; control.outValid := packetFlag(sie.io.out_valid_o); control.outError := packetFlag(sie.io.out_err_o)
  sie.io.usb_en_i := control.usbEnable; sie.io.usb_detach_i := false.B; sie.io.addr_i := control.address
  sie.io.in_bulk_endps_i := Mux(control.configured,2.U,0.U)
  sie.io.out_bulk_endps_i := Mux(control.configured,2.U,0.U)
  sie.io.in_int_endps_i := Mux(control.configured,4.U,0.U); sie.io.out_int_endps_i := 0.U
  sie.io.in_iso_endps_i := 0.U; sie.io.out_iso_endps_i := 0.U
  sie.io.in_toggle_reset_i := control.inToggleReset; sie.io.out_toggle_reset_i := control.outToggleReset
  sie.io.stall_i := sie.io.endp_o === 0.U && control.stall
  sie.io.in_data_i := Mux(sie.io.endp_o === 0.U,control.inData,in.data)
  sie.io.in_valid_i := Mux(sie.io.endp_o === 0.U,control.inValid,sie.io.endp_o === 1.U && in.valid)
  sie.io.in_zlp_i := sie.io.endp_o === 0.U && control.inZlp
  sie.io.in_nak_i := sie.io.endp_o === 2.U
  sie.io.out_nak_i := sie.io.endp_o === 1.U && out.nak
  in.request := packetFlag(sie.io.in_req_o && sie.io.endp_o === 1.U)
  in.consume := packetFlag(sie.io.in_ready_o && sie.io.endp_o === 1.U); in.acknowledge := packetFlag(sie.io.in_data_ack_o)
  out.received := packetData; out.receiveValid := packetFlag(sie.io.out_valid_o)
  out.receiveReady := packetFlag(sie.io.out_ready_o && sie.io.endp_o === 1.U); out.receiveError := packetFlag(sie.io.out_err_o)
  val inRelease = Module(new ResetRelease); val outRelease = Module(new ResetRelease)
  val transportReset = engineReset && control.configured && !sie.io.bus_reset_o && !control.sessionFlush
  inRelease.clk := clk; outRelease.clk := clk
  inRelease.reset_n := transportReset && !control.inToggleReset(1)
  outRelease.reset_n := transportReset && !control.outToggleReset(1)
  in.reset_n := inRelease.released; out.reset_n := outRelease.released
  in.appData := txData; in.appValid := txValid; txReady := in.appReady
  out.appReady := rxReady; rxData := out.appData; rxValid := out.appValid
  txEmpty := in.empty; rxEmpty := out.empty
  configured := control.configured; frame := sie.io.frame_o
  withClockAndReset(clk,(!engineReset).asAsyncReset) {
    sessionReset := RegNext(!transportReset,true.B)
    txReset := RegNext(!transportReset || control.inToggleReset(1),true.B)
    rxReset := RegNext(!transportReset || control.outToggleReset(1),true.B)
    attached := RegNext(sie.io.dp_pu_o,false.B)
  }
  sie.io.dp_rx_i := dpRx; sie.io.dn_rx_i := dnRx
  // Approved PHY-only combinational safety gate; disable works with stopped clocks.
  dpTx := sie.io.dp_tx_o; dnTx := sie.io.dn_tx_o
  val safety=Module(new UsbPadSafety)
  safety.reset_n:=reset_n;safety.vbus:=vbus
  safety.requestedDrive:=sie.io.tx_en_o;safety.requestedPullup:=sie.io.dp_pu_o
  txEnable:=safety.drive;pullup:=safety.pullupEnable
}
