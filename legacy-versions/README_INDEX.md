# legacy-versions

Earlier, standalone scripts that predate or duplicate `core/`. Kept for
reference/history only — do not build new work on these, use `core/`
instead.

## Files
- `spikeling.py` — old standalone interpreter/benchmark runner, superseded by `spikeling_v10.py` and then by `core/runtime/runtime.py`.
- `spikeling_v10.py` — a later (6/18) standalone DSL interpreter with inline visualization. More recent than `spikeling.py` but still not part of the modular `core/` package.
- `spikeling_compiler.py` — a 39-line minimal compiler stub. The real compiler is `core/compiler/compiler.py`.
- `spikeling_sdk.py` — a tiny (30-line) async SDK usage demo.
- `spikelingrust.py` — despite the name, contains no Rust code — just a brief async comparison sketch. Appears abandoned.
- `spikeling_engine.exe`, `spikeling_native.c` — an earlier, smaller standalone build of the C engine (135 KB), predating both the `sdk-verilog` and `parallel-audio` variants.
- `profile.spk.txt` — a `.spk` test config saved with a `.txt` extension (duplicate/precursor of `profile.spk` found in `sdk-verilog/` and `parallel-audio/`).
- `neuron input 1 threshold=0.3 leak=0.txt` — a scratch note, likely an early sketch of `.spk` neuron syntax before the DSL was formalized.

## Status
Superseded. Safe to keep as history but not to extend.
