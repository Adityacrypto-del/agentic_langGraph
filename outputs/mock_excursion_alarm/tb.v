`timescale 1ns/1ps
module tb;
  integer total = 0, failed = 0;
  reg clk = 0;
  reg rst_n = 0;
  reg sample_valid = 0;
  reg signed [7:0] temp = 0;
  wire alarm;
  always #5 clk = ~clk;
  task check(input [63:0] exp, input [63:0] act, input [255:0] label);
    begin
      total = total + 1;
      if (exp !== act) begin
        failed = failed + 1;
        $display("FAIL: %0s exp=%0d act=%0d t=%0t", label, exp, act, $time);
      end
    end
  endtask
  excursion_alarm dut(.clk(clk), .rst_n(rst_n), .sample_valid(sample_valid), .temp(temp), .alarm(alarm));
  // drive one input on the negedge, then wait until 1 ns after the posedge that samples it
  task drive(input v, input signed [7:0] t);
    begin
      @(negedge clk); sample_valid = v; temp = t;
      @(posedge clk); #1;
    end
  endtask
  initial begin
    $dumpfile("wave.vcd"); $dumpvars(0, tb);
    #12 check(0, alarm, "reset: alarm low");
    @(negedge clk); rst_n = 1;
    drive(1, 17); check(0, alarm, "1st hot (17)");
    drive(1, 20); check(0, alarm, "2nd hot (20)");
    drive(1, 40); check(1, alarm, "3rd hot -> alarm");
    drive(1, 50); check(1, alarm, "4th bad: saturates, alarm stays");
    drive(1, 60); check(1, alarm, "5th bad: still saturated");
    drive(1, 16); check(0, alarm, "16 (8C) is in range: clears");
    drive(1, 3);  drive(1, 3); check(0, alarm, "2 x temp=3: no alarm yet");
    drive(1, 4);  check(0, alarm, "temp=4 (2C) in range resets count");
    drive(1, 3);  drive(1, 3); drive(1, 3); check(1, alarm, "3 x temp=3 -> alarm");
    drive(1, 10); check(0, alarm, "in range clears");
    drive(1, -2); drive(1, -2); drive(1, -128); check(1, alarm, "negative temps are out of range (signed)");
    drive(1, 4);  check(0, alarm, "clear after negatives");
    drive(1, 17); drive(0, 4); drive(0, 4); drive(1, 17); check(0, alarm, "invalid cycles ignored: 2 bad");
    drive(1, 17); check(1, alarm, "3rd valid bad across ignored cycles");
    drive(1, 4);  drive(0, 100); drive(0, 100); drive(0, 100); check(0, alarm, "invalid out-of-range ignored");
    drive(1, 17); drive(1, 17); drive(1, 17); check(1, alarm, "alarm before async reset");
    #2 rst_n = 0; #1 check(0, alarm, "async reset clears without a clock edge");
    @(negedge clk); rst_n = 1;
    drive(1, 17); check(0, alarm, "count restarted after reset");
    sample_valid = 0;
    if (failed == 0) $display("TEST_RESULT: PASS total=%0d failed=%0d", total, failed);
    else $display("TEST_RESULT: FAIL total=%0d failed=%0d", total, failed);
    $finish;
  end
  initial begin #2000000; $display("TEST_RESULT: FAIL total=0 failed=1 timeout"); $finish; end
endmodule
