module excursion_alarm (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              sample_valid,
    input  wire signed [7:0] temp,
    output wire              alarm
);
    reg [1:0] count;
    wire out_of_range = (temp < 8'sd4) || (temp > 8'sd16);   // signed compare
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) count <= 2'd0;
        else if (sample_valid) begin
            if (!out_of_range) count <= 2'd0;
            else if (count != 2'd3) count <= count + 2'd1;  // saturate at 3
        end
    end
    assign alarm = (count == 2'd3);
endmodule
