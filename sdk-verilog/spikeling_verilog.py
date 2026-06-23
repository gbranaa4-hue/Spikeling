import os
import re
import sys

# ----------------------------------------------------------------------------─
# Spikeling Verilog backend.
#
#   .spk  ->  spikeling_neurons.v   (synthesizable Verilog)
#
# Each neuron compiles to REAL HARDWARE:
#   - a register  (reg [P_WIDTH-1:0] p)        holding membrane potential
#   - a comparator (p >= threshold)            for the fire decision
#   - a counter   (reg [R_WIDTH-1:0] refr)     for the refractory period
#   - a 1-bit output (spike)                   that pulses when it fires
#
# All neurons update in PARALLEL on the rising clock edge — that's the whole
# point of going to hardware vs. the C loop, which does them one at a time.
# ----------------------------------------------------------------------------─

P_WIDTH = 16   # bits for membrane potential register
R_WIDTH = 16   # bits for refractory counter

def find_config_file():
    for fn in os.listdir('.'):
        if fn.endswith(".spk") or fn.endswith(".txt"):
            try:
                with open(fn) as f:
                    if "# Spikeling Neural Configuration" in f.read():
                        return fn
            except (IOError, UnicodeDecodeError):
                continue
    return None

def compile_to_verilog():
    cfg = sys.argv[1] if len(sys.argv) > 1 else find_config_file()
    if not cfg or not os.path.exists(cfg):
        print("Error: no Spikeling config found (.spk / .txt).")
        return

    with open(cfg) as f:
        text = f.read()

    neurons = re.findall(r"neuron (\w+) threshold=(\d+) leak=(\d+)", text)
    if not neurons:
        print("Error: no neuron definitions in '%s'." % cfg)
        return
    m = re.search(r"refractory=(\d+)ms", text)
    # refractory in "ticks": treat 1 clock tick = 1 ms of modeled time here,
    # so a 4ms refractory = 4 ticks. (Scale as you like on real hardware.)
    refr_ticks = int(m.group(1)) if m else 4

    N = len(neurons)
    L = []
    w = L.append

    w("// Auto-generated from %s by spikeling_verilog.py" % cfg)
    w("// Each neuron is a hardware register with comparator + refractory counter.")
    w("// Synthesizable; also runnable in Icarus Verilog / Verilator.")
    w("")
    w("module spikeling_neurons #(")
    w("    parameter P_WIDTH = %d," % P_WIDTH)
    w("    parameter R_WIDTH = %d" % R_WIDTH)
    w(") (")
    w("    input  wire                 clk,")
    w("    input  wire                 rst,")
    w("    // per-neuron input current this tick (packed)")
    w("    input  wire [P_WIDTH-1:0]   stim   [0:%d]," % (N - 1))
    w("    // 1-bit spike output per neuron")
    w("    output reg                  spike  [0:%d]" % (N - 1))
    w(");")
    w("")
    w("    // -- neuron parameters (constants from the .spk) --")
    w("    localparam integer NEURON_COUNT = %d;" % N)
    w("    localparam integer REFR_TICKS   = %d;" % refr_ticks)
    w("")
    # threshold / leak constants
    w("    // thresholds")
    for i, (name, th, lk) in enumerate(neurons):
        w("    localparam [P_WIDTH-1:0] TH_%d = %d; // %s" % (i, int(th), name))
    w("    // leaks (membrane decay per tick)")
    for i, (name, th, lk) in enumerate(neurons):
        w("    localparam [P_WIDTH-1:0] LK_%d = %d; // %s" % (i, int(lk), name))
    w("")
    w("    // -- state registers: THESE ARE THE NEURONS --")
    w("    reg [P_WIDTH-1:0] p    [0:%d];  // membrane potential" % (N - 1))
    w("    reg [R_WIDTH-1:0] refr [0:%d];  // refractory countdown" % (N - 1))
    w("")
    w("    integer i;")
    w("")
    w("    // helper: threshold/leak lookup as functions of index")
    w("    function [P_WIDTH-1:0] thresh_of;")
    w("        input integer idx;")
    w("        begin")
    w("            case (idx)")
    for i in range(N):
        w("                %d: thresh_of = TH_%d;" % (i, i))
    w("                default: thresh_of = {P_WIDTH{1'b1}};")
    w("            endcase")
    w("        end")
    w("    endfunction")
    w("")
    w("    function [P_WIDTH-1:0] leak_of;")
    w("        input integer idx;")
    w("        begin")
    w("            case (idx)")
    for i in range(N):
        w("                %d: leak_of = LK_%d;" % (i, i))
    w("                default: leak_of = 0;")
    w("            endcase")
    w("        end")
    w("    endfunction")
    w("")
    w("    // -- parallel neuron update: every neuron advances each clock --")
    w("    always @(posedge clk) begin")
    w("        if (rst) begin")
    w("            for (i = 0; i < NEURON_COUNT; i = i + 1) begin")
    w("                p[i]     <= 0;")
    w("                refr[i]  <= 0;")
    w("                spike[i] <= 1'b0;")
    w("            end")
    w("        end else begin")
    w("            for (i = 0; i < NEURON_COUNT; i = i + 1) begin")
    w("                spike[i] <= 1'b0;          // default: no spike")
    w("                if (refr[i] != 0) begin")
    w("                    refr[i] <= refr[i] - 1; // in refractory: just count down")
    w("                end else begin")
    w("                    // leaky integration")
    w("                    if (p[i] > leak_of(i))")
    w("                        p[i] <= p[i] - leak_of(i) + stim[i];")
    w("                    else")
    w("                        p[i] <= stim[i];")
    w("                    // threshold compare on the *post-update* estimate")
    w("                    if ((((p[i] > leak_of(i)) ? p[i] - leak_of(i) : 0) + stim[i])")
    w("                         >= thresh_of(i)) begin")
    w("                        p[i]     <= 0;            // reset")
    w("                        refr[i]  <= REFR_TICKS;   // enter refractory")
    w("                        spike[i] <= 1'b1;         // FIRE")
    w("                    end")
    w("                end")
    w("            end")
    w("        end")
    w("    end")
    w("")
    w("endmodule")
    w("")

    with open("spikeling_neurons.v", "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print("Compiled '%s' -> 'spikeling_neurons.v'" % cfg)
    print("  %d neurons, refractory = %d ticks, P_WIDTH=%d" % (N, refr_ticks, P_WIDTH))
    print("  Each neuron = 1 membrane register + 1 refractory counter + comparator.")
    print("  All neurons update in PARALLEL each clock edge.")

if __name__ == "__main__":
    compile_to_verilog()