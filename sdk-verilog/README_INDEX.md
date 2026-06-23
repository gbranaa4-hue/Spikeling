# sdk-verilog

Standalone distributable SDK for Spikeling: a native C benchmark harness plus
a Verilog hardware backend, so a `.spk` network can be simulated as FPGA
hardware instead of run in Python.

This folder is self-contained (own copy of `spikeling_compiler.py`,
`spikeling_engine.exe`) so it can be copied to another machine and used
without the `core/` package.

## Key files
- `README.txt`, `README_VERILOG.txt` — original authored docs (read these first)
- `spikeling_compiler.py` — older/simpler compiler snapshot (not the canonical one — see `../core/compiler/compiler.py`)
- `spikeling_native.c`, `spikeling_hw.h` — generated C benchmark harness + neuron/synapse tables
- `spikeling_neurons.v`, `spikeling_tb.v` — generated Verilog hardware description + testbench
- `spikeling_verilog.py` — the `.spk` → Verilog compiler backend
- `spikeling_sim` — compiled Icarus Verilog simulator binary
- `spikeling_engine.exe` — compiled Windows reference engine (no audio support — see `../parallel-audio` for that variant)
- `profile.spk`, `big.spk`, `stress.spk` — test network configs (2/8+ neurons)
- `build.bat/.sh`, `build_verilog.bat/.sh` — build scripts for the C and Verilog targets
- `stress/` — duplicate build setup scoped for stress testing

## Resonator hardware backend (new)
- `spikeling_resonator_verilog.py` — generates a synthesizable, fixed-point
  (Q14.18, see file docstring for the full fixed-point design notes)
  Resonator bank module from any `.spk` file with `type=Resonator` neurons,
  plus a self-checking testbench and precomputed stimulus.
- `tone_detector.spk` — copy of `../core/examples/tone_detector.spk`, used
  to generate/verify the above.
- `spikeling_resonators.v`, `tb_resonators.v`, `drive_samples.hex` — generated
  output (regenerate with `python spikeling_resonator_verilog.py tone_detector.spk`).

Verified end-to-end with Icarus Verilog (`iverilog`/`vvp`): correctly detects
440Hz and 1760Hz tones mixed with noise and 3 distractor frequencies, with
zero false positives — same scenario validated in the Python runtime
(`core/examples/test_tone_detector.py`) and C backend
(`core/examples/test_tone_detector.c`), with matching numeric energy values
across all three. This is the third and final backend (Python, C, Verilog)
to have the Resonator neuron type implemented and verified.

**Build note:** both this and the existing `spikeling_neurons.v` (LIF)
module require **`iverilog -g2012`** (SystemVerilog mode) — plain
Verilog-2001 mode fails on the packed array port syntax (`output reg spike
[0:N-1]`). This wasn't documented anywhere before — the LIF Verilog path had
apparently never actually been run through a real simulator until now.
Example:
```
iverilog -g2012 -o tb.vvp spikeling_resonators.v tb_resonators.v
vvp tb.vvp
```

## Status
Functional snapshot, last touched 6/16, **except** the Resonator backend
above which is new and verified. Compiler here is older than `core/`'s —
treat `core/` as the source of truth if the two diverge.
