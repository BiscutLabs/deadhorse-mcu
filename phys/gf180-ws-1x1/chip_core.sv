// SPDX-License-Identifier: Apache-2.0
// Deadhorse binding of the pinned wafer.space chip_core socket (D105/D109/D110).
// Pad indices and aliases are specified in pad-map.yaml. No peripheral RTL here.
`default_nettype none
module chip_core #(
    parameter NUM_INPUT_PADS = 12,
    parameter NUM_BIDIR_PADS = 40,
    parameter NUM_ANALOG_PADS = 2
) (
`ifdef USE_POWER_PINS
    inout wire VDD, VSS,
`endif
`ifdef DEADHORSE_PAD_TEST
    input wire model_lfClock, model_porReference,
    input wire [11:0] model_supplyMv,
`endif
    input wire clk, rst_n,
    input wire [NUM_INPUT_PADS-1:0] input_in,
    output wire [NUM_INPUT_PADS-1:0] input_pu, input_pd,
    input wire [NUM_BIDIR_PADS-1:0] bidir_in,
    output wire [NUM_BIDIR_PADS-1:0] bidir_out, bidir_oe, bidir_cs,
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl, bidir_ie, bidir_pu, bidir_pd,
    inout wire [NUM_ANALOG_PADS-1:0] analog
);
`ifndef USE_POWER_PINS
    wire VDD, VSS;
`endif
    wire [39:0] requested_data, requested_drive, sampled;
    (* keep *) wire status_aonReleased, status_servicesReleased, status_mainLevel;
    (* keep *) wire status_sourceStable, status_fault, status_coreReady, status_coreSleeping;
    (* keep *) wire [2:0] status_resetCauses;
    wire spi_enable, i2c_enable, i2c_scl_low, i2c_sda_low, usb_enable;
    assign input_pu = '0;
    assign input_pd = '0;
    assign bidir_cs = '0;
    assign bidir_sl = '0;
    assign bidir_pu = '0;
    assign bidir_pd = '0;
    chip_pad_feedback boundary (
        .requested_data(requested_data), .requested_drive(requested_drive),
        .receiver(bidir_in), .pad_data(bidir_out), .pad_oe(bidir_oe),
        .pad_ie(bidir_ie), .core_input(sampled)
    );
    assign requested_drive[0] = 1'b1; // OSC_EN must drive high during reset.
    assign requested_drive[15:12] = {4{spi_enable}};
    assign requested_data[17:16] = 2'b00;
    assign requested_drive[16] = i2c_enable & i2c_scl_low;
    assign requested_drive[17] = i2c_enable & i2c_sda_low;
    assign requested_drive[35:34] = {2{usb_enable}};
    assign requested_drive[36] = 1'b1;
`ifdef DEADHORSE_PAD_TEST
    SocAnalogModelTest soc (
        .model_lfClock(model_lfClock), .model_porReference(model_porReference),
        .model_supplyMv(model_supplyMv),
`else
    DeadhorseSoc soc (
        .vdd(VDD), .vss(VSS),
`endif
        .oscIn(clk), .oscEn(requested_data[0]),
        .aonClockIn(input_in[0]), .aonClockSelect(input_in[1]),
        .porBypass(input_in[2]), .externalReset_n(rst_n),
        .pins_aonExtraIn(sampled[39:37]),
        .pins_aonExtraOut(requested_data[39:37]),
        .pins_aonExtraEnable(requested_drive[39:37]),
        .pins_inactive_qspiDqIn(sampled[22:19]),
        .pins_inactive_qspiDqOut(requested_data[22:19]),
        .pins_inactive_qspiDqEnable(requested_drive[22:19]),
        .pins_inactive_qspiSclk(requested_data[18]),
        .pins_inactive_qspiSclkEnable(requested_drive[18]),
        .pins_inactive_qspiCs_n(requested_data[24:23]),
        .pins_inactive_qspiCsEnable(requested_drive[24:23]),
        .pins_inactive_actuatorOut(requested_data[33:25]),
        .pins_inactive_actuatorEnable(requested_drive[33:25]),
        .pins_inactive_jtagTck(input_in[3]), .pins_inactive_jtagTms(input_in[4]),
        .pins_inactive_jtagTdi(input_in[5]),
        .pins_inactive_jtagTdo(requested_data[8]),
        .pins_inactive_jtagTdoEnable(requested_drive[8]),
        .pins_inactive_imuDrdy(input_in[10]),
        .pins_inactive_gpioIn(sampled[3:1]),
        .pins_inactive_gpioOut(requested_data[3:1]),
        .pins_inactive_gpioEnable(requested_drive[3:1]),
        .pins_inactive_timerIn(sampled[7:4]),
        .pins_inactive_timerOut(requested_data[7:4]),
        .pins_inactive_timerEnable(requested_drive[7:4]),
        .pins_uartRx_0(input_in[6]), .pins_uartRx_1(input_in[7]),
        .pins_uartRx_2(input_in[8]),
        .pins_uartTx_0(requested_data[9]), .pins_uartTx_1(requested_data[10]),
        .pins_uartTx_2(requested_data[11]),
        .pins_uartTxEnable_0(requested_drive[9]),
        .pins_uartTxEnable_1(requested_drive[10]),
        .pins_uartTxEnable_2(requested_drive[11]),
        .pins_spiMiso(input_in[9]), .pins_spiSclk(requested_data[12]),
        .pins_spiMosi(requested_data[13]), .pins_spiCs_n(requested_data[15:14]),
        .pins_spiEnable(spi_enable),
        .pins_i2cSclIn(sampled[16]), .pins_i2cSdaIn(sampled[17]),
        .pins_i2cSclLow(i2c_scl_low), .pins_i2cSdaLow(i2c_sda_low),
        .pins_i2cEnable(i2c_enable),
        .pins_usbVbus(input_in[11]), .pins_usbDpRx(sampled[34]),
        .pins_usbDnRx(sampled[35]), .pins_usbDpTx(requested_data[34]),
        .pins_usbDnTx(requested_data[35]), .pins_usbTxEnable(usb_enable),
        .pins_usbPullup(requested_data[36]),
        .status_aonReleased(status_aonReleased),
        .status_servicesReleased(status_servicesReleased),
        .status_mainLevel(status_mainLevel), .status_sourceStable(status_sourceStable),
        .status_fault(status_fault), .status_coreReady(status_coreReady),
        .status_coreSleeping(status_coreSleeping), .status_resetCauses(status_resetCauses)
    );
endmodule
`default_nettype wire
