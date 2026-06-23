// Testbench for spikeling_neurons.
// Drives stimulus, prints spikes, dumps a waveform (spikeling.vcd).
`timescale 1ns/1ps

module tb;
    localparam P_WIDTH = 16;
    localparam N = `NCOUNT;   // passed in at compile time

    reg clk = 0;
    reg rst = 1;
    reg  [P_WIDTH-1:0] stim  [0:N-1];
    wire               spike [0:N-1];

    // device under test
    spikeling_neurons #(.P_WIDTH(P_WIDTH)) dut (
        .clk(clk), .rst(rst), .stim(stim), .spike(spike)
    );

    // 100 MHz clock
    always #5 clk = ~clk;

    integer i, t;
    integer total_spikes = 0;

    // simple LFSR for varied stimulus
    reg [31:0] lfsr = 32'hACE12345;
    function [31:0] next_rand;
        input [31:0] s;
        begin
            next_rand = s ^ (s << 13);
            next_rand = next_rand ^ (next_rand >> 17);
            next_rand = next_rand ^ (next_rand << 5);
        end
    endfunction

    initial begin
        $dumpfile("spikeling.vcd");
        $dumpvars(0, tb);

        for (i = 0; i < N; i = i + 1) stim[i] = 0;

        // hold reset 2 cycles
        @(posedge clk); @(posedge clk);
        rst = 0;

        // run 200 ticks of stimulus
        for (t = 0; t < 200; t = t + 1) begin
            for (i = 0; i < N; i = i + 1) begin
                lfsr = next_rand(lfsr);
                // intensity 0..63
                stim[i] = lfsr[5:0];
            end
            @(posedge clk);
            // sample spikes (registered, so check after edge settles)
            #1;
            for (i = 0; i < N; i = i + 1) begin
                if (spike[i]) begin
                    total_spikes = total_spikes + 1;
                    if (total_spikes <= 20)
                        $display("  t=%0d  neuron %0d FIRED", t, i);
                end
            end
        end

        $display("");
        $display("Total spikes over 200 ticks across %0d neurons: %0d",
                 N, total_spikes);
        $display("Waveform written to spikeling.vcd (open in GTKWave).");
        $finish;
    end
endmodule
