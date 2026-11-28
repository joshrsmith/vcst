module gui_dut_verilog (
    input  wire clock,
    input  wire d,
    output reg  q
);
    always @(posedge clock) q <= d;

    // Drives no output, so that an optimizing simulator could remove it: the test reads it, and so does run_once.do, as
    // a user debugging in the GUI does
    wire not_d;
    assign not_d = !d;
endmodule
