SPIKELING VERILOG BACKEND — real registers, free simulation
============================================================

WHAT THIS IS
  A second backend for the Spikeling DSL. Instead of compiling your .spk
  to C (software model), this compiles it to SYNTHESIZABLE VERILOG, where
  each neuron becomes actual hardware:

    reg [15:0] p[i]      <- membrane potential register  (THE neuron's state)
    reg [15:0] refr[i]   <- refractory countdown counter
    comparator (p >= threshold) -> spike output bit

  All neurons update IN PARALLEL on each clock edge. This is the real
  difference from the C version, which updates them one at a time in a loop.

  You run it in a free software simulator (Icarus Verilog) — no FPGA board
  required. The same Verilog is synthesizable, so if you ever buy a board it
  will run on real silicon unchanged.

WHAT YOU CAN HONESTLY SAY NOW
  "The Spikeling DSL compiles to synthesizable Verilog. Each neuron is a
   hardware register with comparator and refractory-counter logic, verified
   in simulation (Icarus Verilog). All neurons update in parallel per clock."
  That is literally true and you can demonstrate it.

  What you still cannot say: that it runs on a physical FPGA (you haven't
  loaded a board) or at any particular MHz/throughput on silicon (that needs
  synthesis + place-and-route on a real part).

REQUIREMENTS
  - Python 3
  - Icarus Verilog (free)
      Windows:  https://bleyer.org/icarus/   (installs iverilog + vvp)
      Optional: GTKWave (bundled with that installer) to view waveforms

RUN IT (Windows)
  build_verilog.bat                  # stress.spk, 8 neurons
  build_verilog.bat profile.spk 2    # your real 2-neuron reflex profile
  build_verilog.bat big.spk 6000     # large population (simulation is slow!)

RUN IT (Linux/Mac)
  ./build_verilog.sh
  ./build_verilog.sh profile.spk 2

  NOTE: the 2nd argument MUST match the neuron count in the .spk file.

OUTPUT
  - Console: prints the first 20 spikes (tick + neuron id) and a total.
  - spikeling.vcd: open in GTKWave to watch the p[] registers ramp up,
    cross threshold, reset to 0, and the refr[] counters tick down.

FILES
  spikeling_verilog.py   .spk -> spikeling_neurons.v  (the backend)
  spikeling_neurons.v    GENERATED hardware description (do not hand-edit)
  spikeling_tb.v         testbench: drives stimulus, prints spikes, dumps VCD
  build_verilog.bat/.sh  one-command compile + simulate

HOW THE HARDWARE DIFFERS FROM THE C MODEL
  C model:     for (i..N) update neuron[i];   // sequential, 1 at a time
  Verilog:     all N neurons update on the same posedge clk;  // parallel

  In the 8-neuron sim you can see multiple neurons fire on the SAME tick
  (e.g. five at t=13) — impossible in the sequential C loop. That parallelism
  is the entire reason neuromorphic hardware exists.

SCALING NOTE (important + honest)
  This is a naive 1-register-per-neuron design. It is CORRECT and
  DEMONSTRATIVE, not optimized. A real FPGA can't fit thousands of these in
  parallel without time-multiplexing. Simulating big.spk (6000 neurons) in
  iverilog works but is slow. For a demo, use stress.spk (8). The point of
  this backend is to prove the DSL->hardware path is real, not to set a
  throughput record.
