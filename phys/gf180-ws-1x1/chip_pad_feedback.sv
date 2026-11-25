// SPDX-License-Identifier: Apache-2.0
// D110 pad-boundary combinational glue; no clock, state or CDC is introduced.
module chip_pad_feedback #(
    parameter WIDTH = 40
) (
    input wire [WIDTH-1:0] requested_data,
    input wire [WIDTH-1:0] requested_drive,
    input wire [WIDTH-1:0] receiver,
    output wire [WIDTH-1:0] pad_data,
    output wire [WIDTH-1:0] pad_oe,
    output wire [WIDTH-1:0] pad_ie,
    output wire [WIDTH-1:0] core_input
);
    assign pad_data = requested_data;
    assign pad_oe = requested_drive;
    assign pad_ie = ~requested_drive;
    assign core_input = (requested_drive & requested_data) | (~requested_drive & receiver);
endmodule
