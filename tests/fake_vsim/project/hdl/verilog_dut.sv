module verilog_dut #(parameter string NAME = "default", parameter int COUNT = 1)
    (input logic clock, input logic d, output logic q);
    always_ff @(posedge clock) q <= d;
endmodule
