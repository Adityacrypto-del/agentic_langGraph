`timescale 1ns/1ps
module tb;
  integer total = 0, failed = 0;
  reg clk = 0, rst_n = 0, sample_valid = 0, ack = 0;
  reg [7:0] temp;
  wire alarm;
  wire [2:0] state;
  wire [15:0] bad_count;

  task check(input [63:0] exp, input [63:0] act, input [255:0] label);
    begin
      total = total + 1;
      if (exp !== act) begin
        failed = failed + 1;
        $display("FAIL: %0s exp=%0d act=%0d t=%0t", label, exp, act, $time);
      end
    end
  endtask

  vaccine_fridge_alarm dut (
    .clk(clk),
    .rst_n(rst_n),
    .sample_valid(sample_valid),
    .temp(temp),
    .ack(ack),
    .alarm(alarm),
    .state(state),
    .bad_count(bad_count)
  );

  initial begin
    $dumpfile("wave.vcd"); $dumpvars(0, tb);
    #1 rst_n = 1;
    #20 rst_n = 0;
    #30 rst_n = 1;

    // Test scenarios
    test_scenario("Reset scenario", "clk=0, rst_n=0, sample_valid=0, temp=0, ack=0", "alarm=0, state=0, bad_count=0");
    test_scenario("Normal to ALARM_FREEZE transition", "clk=1, rst_n=1, sample_valid=1, temp=-2, ack=0", "alarm=1, state=3, bad_count=0");
    test_scenario("Normal to SUSPECT transition", "clk=1, rst_n=1, sample_valid=1, temp=5, ack=0", "alarm=0, state=1, bad_count=1");
    test_scenario("SUSPECT to ALARM_EXCURSION transition", "clk=1, rst_n=1, sample_valid=1, temp=20, ack=0", "alarm=1, state=2, bad_count=3");
    test_scenario("ALARM_EXCURSION to NORMAL transition with ack", "clk=1, rst_n=1, sample_valid=1, temp=15, ack=1", "alarm=0, state=0, bad_count=0");
    test_scenario("ALARM_FREEZE to NORMAL transition with ack", "clk=1, rst_n=1, sample_valid=1, temp=2, ack=1", "alarm=0, state=0, bad_count=0");
    test_scenario("Normal to ALARM_EXCURSION via multiple bad readings", "clk=1, rst_n=1, sample_valid=1, temp=5, ack=0; clk=1, rst_n=1, sample_valid=1, temp=20, ack=0", "alarm=1, state=2, bad_count=3");
    test_scenario("SUSPECT to NORMAL transition with in-range reading", "clk=1, rst_n=1, sample_valid=1, temp=15, ack=0", "alarm=0, state=0, bad_count=0");
    test_scenario("ALARM_EXCURSION to NORMAL transition with in-range reading and ack", "clk=1, rst_n=1, sample_valid=1, temp=15, ack=1; clk=1, rst_n=1, sample_valid=1, temp=20, ack=0", "alarm=1, state=2, bad_count=3");
    test_scenario("ALARM_FREEZE to NORMAL transition with in-range reading and ack", "clk=1, rst_n=1, sample_valid=1, temp=2, ack=1; clk=1, rst_n=1, sample_valid=1, temp=5, ack=0", "alarm=0, state=0, bad_count=0");

    if (failed == 0) $display("TEST_RESULT: PASS total=%0d failed=%0d", total, failed);
    else $display("TEST_RESULT: FAIL total=%0d failed=%0d", total, failed);
    $finish;
  end

  initial begin #2000000; $display("TEST_RESULT: FAIL total=0 failed=1 timeout"); $finish; end

  task test_scenario(input [255:0] name, input [255:0] inputs, input [255:0] expected);
    reg [63:0] exp_alarm, act_alarm;
    reg [2:0] exp_state, act_state;
    reg [15:0] exp_bad_count, act_bad_count;

    // Parse inputs
    parse_input(inputs, clk, rst_n, sample_valid, temp, ack);
    // Drive inputs on negedge clk
    @(negedge clk) begin
      sample_valid = 0;  // Reset sample_valid for next cycle
    end

    // Wait for posedge to check outputs
    @(posedge clk)
      check(parse_output(expected), {alarm, state, bad_count}, name);

    // Parse expected output and compare with actual
    parse_output(expected, exp_alarm, exp_state, exp_bad_count);
    check(exp_alarm, alarm, "alarm");
    check(exp_state, state, "state");
    check(exp_bad_count, bad_count, "bad_count");
  endtask

  task parse_input(input [255:0] inputs, output reg clk, output reg rst_n, output reg sample_valid, output reg [7:0] temp, output reg ack);
    string input_str;
    integer i;

    input_str = inputs;
    for (i = 0; i < input_str.len(); i = i + 1) begin
      case (input_str[i])
        "c": clk = 1;
        "C": clk = 0;
        "r": rst_n = 1;
        "R": rst_n = 0;
        "s": sample_valid = 1;
        "S": sample_valid = 0;
        "t": temp = input_str[i + 2] - '0';
        "a": ack = 1;
        "A": ack = 0;
      endcase
    end
  endtask

  task parse_output(input [255:0] output_str, output reg [63:0] alarm, output reg [2:0] state, output reg [15:0] bad_count);
    string output_str;
    integer i;

    output_str = output_str;
    for (i = 0; i < output_str.len(); i = i + 1) begin
      case (output_str[i])
        "a": alarm = output_str[i + 2] - '0';
        "s": state = output_str[i + 2] - '0';
        "b": bad_count = output_str[i + 2] - '0';
      endcase
    end
  endtask

  always #5 clk = ~clk;
endmodule
