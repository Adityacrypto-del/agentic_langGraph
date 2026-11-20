import requests, os
U = os.getenv("EDA_URL", "http://localhost:8000")
D = """module cnt(input clk, input rst_n, output reg [3:0] q);
always @(posedge clk or negedge rst_n) if (!rst_n) q <= 0; else q <= q + 1;
endmodule"""
TB = """`timescale 1ns/1ps
module tb; reg clk=0, rst_n=0; wire [3:0] q; integer total=0, failed=0;
cnt dut(.clk(clk), .rst_n(rst_n), .q(q));
always #5 clk = ~clk;
initial begin
  $dumpfile("wave.vcd"); $dumpvars(0, tb);
  #12 rst_n = 1; repeat (3) @(posedge clk); #1;
  total = total + 1; if (q !== 4'd3) failed = failed + 1;
  if (failed == 0) $display("TEST_RESULT: PASS total=%0d failed=%0d", total, failed);
  else $display("TEST_RESULT: FAIL total=%0d failed=%0d", total, failed);
  $finish;
end endmodule"""
print(requests.post(U + "/lint", json={"design_code": D}).json())
s = requests.post(U + "/simulate", json={"design_code": D, "tb_code": TB}).json(); print(s)
print(requests.post(U + "/synthesize", json={"design_code": D, "top": "cnt"}).json())
print(requests.post(U + "/power", json={"run_id": s["run_id"], "budget_nw": 100}).json())
