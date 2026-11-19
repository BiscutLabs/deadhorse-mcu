// SPDX-License-Identifier: MIT
// Adapted from ulixxe/usb_cdc ctrl_endp.v, commit 6798bf42d43be81368d4e5e2c26b262b41e9fb6a.
// See hw/vendor/usb/LICENSE. Single-channel contract, registered decode, ACK commit/replay.
package deadhorse.usb

import chisel3._
import chisel3.util._

object UsbDescriptors {
  def device(vid: Int, pid: Int): Seq[Int] = Seq(18,1,0,2,2,0,0,8,
    vid & 255,vid >> 8,pid & 255,pid >> 8,0x10,1,0,0,0,1)
  val configuration: Seq[Int] = Seq(9,2,67,0,2,1,0,0x80,0x32,
    9,4,0,0,1,2,2,1,0,5,0x24,0,0x10,1,5,0x24,1,0,1,
    4,0x24,2,0,5,0x24,6,0,1,7,5,0x82,3,8,0,255,
    9,4,1,0,2,0x0a,0,0,0,7,5,1,2,64,0,0,7,5,0x81,2,64,0,0)
}

/** Packet-level control endpoint. Inputs are sampled only on bitEnable.
  * Registered decode has three sample-clock edges to settle before the next
  * enabled edge. Address/configuration changes commit only on status ACK.
  */
class UsbControl(vid: Int = 0, pid: Int = 0) extends RawModule {
  protected def statusAcknowledged(ack: Bool,sent: Bool): Bool=ack && sent
  require(vid >= 0 && vid <= 65535 && pid >= 0 && pid <= 65535)
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bitEnable = IO(Input(Bool())); val busReset = IO(Input(Bool()))
  val inRequest = IO(Input(Bool())); val inReady = IO(Input(Bool())); val inAck = IO(Input(Bool()))
  val setup = IO(Input(Bool())); val outReady = IO(Input(Bool()))
  val outValid = IO(Input(Bool())); val outError = IO(Input(Bool())); val outData = IO(Input(UInt(8.W)))
  val inData = IO(Output(UInt(8.W))); val inValid = IO(Output(Bool())); val inZlp = IO(Output(Bool()))
  val stall = IO(Output(Bool())); val address = IO(Output(UInt(7.W)))
  val configured = IO(Output(Bool())); val usbEnable = IO(Output(Bool()))
  val sessionFlush = IO(Output(Bool()))
  val inToggleReset = IO(Output(UInt(16.W))); val outToggleReset = IO(Output(UInt(16.W)))

  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val Seq(idle,setupState,readState,writeState,statusState,outStatus,stalled) =
      (0 until 7).map(i => (1 << i).U(7.W))
    val state = RegInit(idle)
    val header = Reg(Vec(8, UInt(8.W)))
    val setupCount = RegInit(0.U(4.W))
    val cursor = RegInit(0.U(7.W)); val committed = RegInit(0.U(7.W))
    val total = RegInit(0.U(7.W)); val requested = RegInit(0.U(16.W))
    // Control state only advances on every fourth sample edge. Compute narrow
    // lookahead values on the intervening samples instead of chaining compare,
    // increment and state admission on the consuming edge.
    val nextCursor = RegNext(cursor + 1.U,1.U)
    val dataRemaining = RegNext(cursor < total,false.B)
    val response = RegInit(0.U(2.W)) // 0 zeros, 1 device, 2 config, 3 configuration value
    val pending = RegInit(0.U(2.W)) // 0 none, 1 address, 2 configuration, 3 clear halt
    val pendingValue = RegInit(0.U(8.W))
    val addressQ = RegInit(0.U(7.W)); val configuredQ = RegInit(false.B)
    val enabledQ = RegInit(false.B)
    val statusSent = RegInit(false.B); val zlpSent = RegInit(false.B)
    // The only advertised control-write payload is seven-byte line coding.
    // Saturate/reject malformed extra bytes rather than wrap a wide counter.
    val writeCount = RegInit(0.U(4.W))
    val flush = RegInit(false.B)
    val inToggle = RegInit(0.U(16.W)); val outToggle = RegInit(0.U(16.W))
    address := addressQ; configured := configuredQ; usbEnable := enabledQ
    sessionFlush := flush; inToggleReset := inToggle; outToggleReset := outToggle
    // Hold toggle reset through the next enabled SIE edge, not merely one sample.
    when(bitEnable) { flush := false.B; inToggle := 0.U; outToggle := 0.U }

    // Small synchronous ROM banks; two-stage read avoids a wide byte mux.
    def readDescriptor(descriptor: Seq[Int]): UInt = {
      val groups = descriptor.grouped(8).toSeq
      val bankBytes = groups.map { bytes =>
        RegNext(VecInit(bytes.padTo(8,0).map(_.U(8.W)))(cursor(2,0)), 0.U)
      }
      val bankIndex = RegNext(cursor(6,3), 0.U)
      RegNext(Mux(bankIndex < groups.size.U,VecInit(bankBytes)(bankIndex),0.U),0.U)
    }
    val deviceByte = readDescriptor(UsbDescriptors.device(vid,pid))
    val configurationByte = readDescriptor(UsbDescriptors.configuration)
    val replyByte = Mux(response === 1.U,deviceByte,Mux(response === 2.U,configurationByte,
      Mux(response === 3.U, configuredQ.asUInt, 0.U))
    )
    // ROM already has a registered output. Register the remaining output select.
    inData := RegNext(replyByte, 0.U)
    val terminalZlp = RegNext(total < requested && total(2,0) === 0.U,false.B)
    val readComplete = RegNext(cursor >= total &&
      (cursor === requested || cursor(2,0) =/= 0.U || zlpSent),false.B)
    inValid := RegNext((state === readState && (dataRemaining || terminalZlp)) || state === statusState, false.B)
    inZlp := RegNext(state === statusState || (state === readState && !dataRemaining), false.B)
    stall := RegNext(state === stalled, false.B)

    val requestType = header(0); val request = header(1)
    val value = Cat(header(3),header(2)); val index = Cat(header(5),header(4))
    val length = Cat(header(7),header(6))
    // Descriptor type arrives several bytes before wLength. Split its decode
    // from the length clamp; both stages settle before the SETUP EOP.
    val descriptorLength = RegNext(Mux(header(3) === 1.U,18.U(7.W),67.U(7.W)),0.U)
    val recipient = requestType(1,0)
    val endpointValid = index(15,8) === 0.U && index(6,4) === 0.U &&
      (index(3,0) === 0.U || index(3,0) === 1.U || (index(7) && index(3,0) === 2.U))
    // Capture SETUP bytes before the indexed register write. The header write
    // then completes one sample after admission, before the next protocol edge.
    val headerWrite=RegNext(bitEnable && !busReset && outReady && !setup && !outError &&
      state===setupState && outValid && setupCount<8.U,false.B)
    val headerIndex=RegNext(setupCount(2,0))
    val headerData=RegNext(outData)
    when(headerWrite){header(headerIndex):=headerData}
    val decodedValid = WireDefault(false.B)
    val decodedReply = WireDefault(0.U(2.W))
    val decodedLength = WireDefault(0.U(7.W))
    val decodedPending = WireDefault(0.U(2.W))
    val decodedValue = WireDefault(header(2))
    when(requestType(6,5) === 0.U && requestType(4,2) === 0.U && recipient =/= 3.U) {
      switch(request) {
        is(0.U) { // GET_STATUS; baseline advertises no remote wake and no persistent halt.
          decodedValid := requestType(7) && value === 0.U && length === 2.U &&
            Mux(recipient === 0.U,index === 0.U,Mux(recipient === 1.U,index < 2.U,endpointValid))
          decodedLength := 2.U
        }
        is(1.U) { // CLEAR_FEATURE(ENDPOINT_HALT)
          decodedValid := !requestType(7) && recipient === 2.U && value === 0.U && length === 0.U && endpointValid
          decodedPending := 3.U; decodedValue := header(4)
        }
        is(5.U) {
          decodedValid := requestType === 0.U && value < 128.U && index === 0.U && length === 0.U
          decodedPending := 1.U
        }
        is(6.U) {
          decodedValid := requestType === 0x80.U && header(2) === 0.U && index === 0.U &&
            (header(3) === 1.U || header(3) === 2.U)
          decodedReply := Mux(header(3) === 1.U,1.U,2.U)
          decodedLength := Mux(length < descriptorLength,length,descriptorLength)
        }
        is(8.U) {
          decodedValid := requestType === 0x80.U && addressQ =/= 0.U && value === 0.U && index === 0.U && length === 1.U
          decodedReply := 3.U; decodedLength := 1.U
        }
        is(9.U) {
          decodedValid := requestType === 0.U && addressQ =/= 0.U && value <= 1.U && index === 0.U && length === 0.U
          decodedPending := 2.U
        }
        is(10.U) {
          decodedValid := requestType === 0x81.U && configuredQ && value === 0.U && index < 2.U && length === 1.U
          decodedLength := 1.U
        }
      }
    }.elsewhen(requestType(6,5) === 1.U && requestType(4,2) === 0.U && configuredQ && recipient === 1.U && index < 2.U) {
      // Retained source contract: ACM requests acknowledged; no modem/line-coding hardware.
      decodedValid := (request === 0x20.U && !requestType(7) && length === 7.U) ||
        (request === 0x21.U && requestType(7) && length === 7.U) ||
        ((request === 0x22.U || request === 0x23.U) && !requestType(7) && length === 0.U)
      decodedLength := 7.U
    }
    // Header bytes are stable well before EOP. Register expensive validation.
    val decodeValidQ = RegNext(decodedValid, false.B)
    val decodeReplyQ = RegNext(decodedReply, 0.U)
    val decodeLengthQ = RegNext(decodedLength, 0.U)
    val decodePendingQ = RegNext(decodedPending, 0.U)
    val decodeValueQ = RegNext(decodedValue, 0.U)

    when(busReset) {
      state := idle; setupCount := 0.U; cursor := 0.U; committed := 0.U
      addressQ := 0.U; configuredQ := false.B; enabledQ := true.B
      pending := 0.U; statusSent := false.B; zlpSent := false.B; flush := true.B
      inToggle := 0.U; outToggle := 0.U
    }.elsewhen(bitEnable) {
      when(outReady && setup) {
        state := setupState; setupCount := 0.U; pending := 0.U
        cursor := 0.U; committed := 0.U; statusSent := false.B; zlpSent := false.B
      }.elsewhen(outReady && outError) {
        // A bad packet never commits header state or a side effect.
        when(state === setupState) { state := idle; pending := 0.U }
        when(state === writeState) { writeCount := 0.U }
      }.otherwise {
        when(outReady) {
          when(state === setupState) {
            when(outValid) {
              when(setupCount < 15.U) { setupCount := setupCount + 1.U }
            }.otherwise {
              pending := decodePendingQ; pendingValue := decodeValueQ
              total := decodeLengthQ; requested := length; response := decodeReplyQ
              cursor := 0.U; committed := 0.U; writeCount := 0.U
              when(setupCount =/= 8.U || !decodeValidQ) { state := stalled; pending := 0.U }
                .elsewhen(length === 0.U) { state := statusState }
                .elsewhen(requestType(7)) { state := readState }
                .otherwise { state := writeState }
            }
          }.elsewhen(state === writeState) {
            when(outValid) {
              when(writeCount < 8.U) { writeCount := writeCount + 1.U }.otherwise { state := stalled }
            }
              .otherwise { when(writeCount === requested) { state := statusState }.otherwise { state := stalled } }
          }.elsewhen(state === outStatus || state === readState) {
            when(!outValid) { state := idle }.otherwise { state := stalled }
          }
        }
        when(inReady) {
          when(state === readState) {
            when(inRequest) { cursor := committed; zlpSent := false.B }
              .elsewhen(inAck) {
                committed := cursor
                when(readComplete) { state := outStatus }
              }.otherwise {
                when(dataRemaining) { cursor := nextCursor }.otherwise { zlpSent := true.B }
              }
          }.elsewhen(state === statusState) {
            // SIE does not publish a byte-consume pulse for a ZLP. Its locked
            // ACK qualification guarantees DATA completion before inAck.
            when(inRequest) { statusSent := true.B }
              .elsewhen(statusAcknowledged(inAck,statusSent)) {
                state := idle; pending := 0.U
                switch(pending) {
                  is(1.U) { addressQ := pendingValue(6,0); configuredQ := false.B; flush := true.B }
                  is(2.U) { configuredQ := pendingValue(0); flush := true.B; inToggle := 65535.U; outToggle := 65535.U }
                  is(3.U) {
                    when(pendingValue(7)) { inToggle := (1.U(16.W) << pendingValue(3,0))(15,0) }
                      .otherwise { outToggle := (1.U(16.W) << pendingValue(3,0))(15,0) }
                  }
                }
              }.elsewhen(!inAck) { statusSent := true.B }
          }
        }
      }
    }
  }
}
