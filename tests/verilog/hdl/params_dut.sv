// A Verilog top level with parameters. Its outputs show the values the parameters were given.
`timescale 1ns/1ps

module params_dut #(
    parameter int WIDTH = 8,
    parameter string NAME = "default"
) (
    input  logic [WIDTH-1:0] a,
    input  logic [WIDTH-1:0] b,
    output logic [WIDTH:0]   sum,
    output logic [7:0]       name_id
);
    assign sum = a + b;

    // Drives no output, so that an optimizing simulator could remove it: a test reads it, to check that the signals
    // inside a design can be read
    logic [WIDTH-1:0] both;
    assign both = a & b;

    // Which of the names given by run.py NAME is, 0 for any other name
    assign name_id = NAME == "default" ? 8'd1 :
                     NAME == "hello" ? 8'd2 :
                     NAME == "data/file.txt" ? 8'd3 : 8'd0;
endmodule
