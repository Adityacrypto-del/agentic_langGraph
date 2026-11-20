module vaccine_fridge_alarm (
    input wire clk,
    input wire rst_n,
    input wire sample_valid,
    input wire signed [7:0] temp,
    input wire ack,
    output reg alarm,
    output reg [1:0] state,
    output reg [1:0] bad_count
);

parameter N = 3;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        alarm <= 0;
        state <= 2'b00; // NORMAL
        bad_count <= 2'b00;
    end else begin
        case (state)
            2'b00: begin // NORMAL
                if (sample_valid && temp <= -8'd16) begin // Freezing reading
                    state <= 2'b11; // ALARM_FREEZE
                end else if (sample_valid && (temp < 4 || temp > 16)) begin // Bad reading
                    bad_count <= 2'b01;
                    state <= 2'b01; // SUSPECT
                end
            end
            2'b01: begin // SUSPECT
                if (sample_valid && temp <= -8'd16) begin // Freezing reading
                    state <= 2'b11; // ALARM_FREEZE
                end else if (sample_valid && (temp < 4 || temp > 16)) begin // Bad reading
                    bad_count <= bad_count + 2'b01;
                    if (bad_count == N) begin
                        state <= 2'b10; // ALARM_EXCURSION
                    end
                end else begin // In-range reading
                    bad_count <= 2'b00;
                    state <= 2'b00; // NORMAL
                end
            end
            2'b10: begin // ALARM_EXCURSION
                if (ack) begin
                    state <= 2'b00; // NORMAL
                    bad_count <= 2'b00;
                end
            end
            2'b11: begin // ALARM_FREEZE
                if (ack) begin
                    state <= 2'b00; // NORMAL
                    bad_count <= 2'b00;
                end
            end
        endcase
    end
end

assign alarm = (state == 2'b10 || state == 2'b11);

endmodule
