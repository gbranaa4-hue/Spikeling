// Auto-generated from profile.spk by spikeling_verilog.py
// Each neuron is a hardware register with comparator + refractory counter.
// Synthesizable; also runnable in Icarus Verilog / Verilator.

module spikeling_neurons #(
    parameter P_WIDTH = 16,
    parameter R_WIDTH = 16
) (
    input  wire                 clk,
    input  wire                 rst,
    // per-neuron input current this tick (packed)
    input  wire [P_WIDTH-1:0]   stim   [0:1],
    // 1-bit spike output per neuron
    output reg                  spike  [0:1]
);

    // -- neuron parameters (constants from the .spk) --
    localparam integer NEURON_COUNT = 2;
    localparam integer REFR_TICKS   = 400;

    // thresholds
    localparam [P_WIDTH-1:0] TH_0 = 110; // LeftMic
    localparam [P_WIDTH-1:0] TH_1 = 110; // RightMic
    // leaks (membrane decay per tick)
    localparam [P_WIDTH-1:0] LK_0 = 5; // LeftMic
    localparam [P_WIDTH-1:0] LK_1 = 5; // RightMic

    // -- state registers: THESE ARE THE NEURONS --
    reg [P_WIDTH-1:0] p    [0:1];  // membrane potential
    reg [R_WIDTH-1:0] refr [0:1];  // refractory countdown

    integer i;

    // helper: threshold/leak lookup as functions of index
    function [P_WIDTH-1:0] thresh_of;
        input integer idx;
        begin
            case (idx)
                0: thresh_of = TH_0;
                1: thresh_of = TH_1;
                default: thresh_of = {P_WIDTH{1'b1}};
            endcase
        end
    endfunction

    function [P_WIDTH-1:0] leak_of;
        input integer idx;
        begin
            case (idx)
                0: leak_of = LK_0;
                1: leak_of = LK_1;
                default: leak_of = 0;
            endcase
        end
    endfunction

    // -- parallel neuron update: every neuron advances each clock --
    always @(posedge clk) begin
        if (rst) begin
            for (i = 0; i < NEURON_COUNT; i = i + 1) begin
                p[i]     <= 0;
                refr[i]  <= 0;
                spike[i] <= 1'b0;
            end
        end else begin
            for (i = 0; i < NEURON_COUNT; i = i + 1) begin
                spike[i] <= 1'b0;          // default: no spike
                if (refr[i] != 0) begin
                    refr[i] <= refr[i] - 1; // in refractory: just count down
                end else begin
                    // leaky integration
                    if (p[i] > leak_of(i))
                        p[i] <= p[i] - leak_of(i) + stim[i];
                    else
                        p[i] <= stim[i];
                    // threshold compare on the *post-update* estimate
                    if ((((p[i] > leak_of(i)) ? p[i] - leak_of(i) : 0) + stim[i])
                         >= thresh_of(i)) begin
                        p[i]     <= 0;            // reset
                        refr[i]  <= REFR_TICKS;   // enter refractory
                        spike[i] <= 1'b1;         // FIRE
                    end
                end
            end
        end
    end

endmodule
