# 🧠 Spikeling

A neuromorphic **domain-specific language and runtime for spiking neural
networks**, by Gavin Branaa. You describe a network of spiking neurons and
synapses in a compact `.spk` file, and run that one description on any of four
backends:

- an **interactive Python runtime** (development + STDP learning),
- generated **C** (embedded / production),
- generated **Verilog** (FPGA / hardware simulation), and
- **GDScript** (give a Godot game a live spiking "mind").

One language, four targets.

---

## Quick start

```bash
cd core
python -m core                     # run the default example, interactively
python -m core path/to/network.spk # run your own .spk network
```

Full DSL reference, runtime details, and the C-compilation path are in
[`core/README.md`](core/README.md).

## The `.spk` language in 30 seconds

```spk
neuron LeftMic  threshold=110 leak=5 type=LIF
neuron RightMic threshold=110 leak=5 type=LIF
neuron Motor    threshold=80  leak=3 type=LIF

connect LeftMic  -> Motor weight=0.8
connect RightMic -> Motor weight=0.8

action Motor -> [MOTOR_FIRE]

refractory=400ms
learn=STDP rate=0.01
```

| Directive | Meaning |
|---|---|
| `neuron <name> threshold=<n> leak=<n> [type=LIF]` | define a neuron |
| `connect <src> -> <dst> weight=<w>` | weighted synapse |
| `action <neuron> -> [<COMMAND>]` | map a spike to a named command |
| `refractory=<n>ms` | global refractory period |
| `learn=STDP rate=<r>` | enable spike-timing-dependent plasticity |

*(The GDScript backend uses a compact variant — `synapse SRC -> DST weight=N` —
documented in [`godot-runtime/`](godot-runtime/README.md).)*

## Neuron types

| Type | What it is |
|---|---|
| `LIF` | Leaky integrate-and-fire — fast, standard |
| `Izhikevich` | Cortical model — bursting, adaptation |
| `AdEx` | Adaptive exponential — realism/speed balance |
| `Resonator` | Damped oscillator — responds only to input near its own frequency (a frequency-domain primitive). See [`resonator-prototype/`](resonator-prototype/README.md) |

---

## Repository map

| Folder | What it is | Status |
|---|---|---|
| [`core/`](core/README.md) | The canonical Python package: compiler, runtime, encoder, stdlib, examples. **Start here.** | Active — source of truth |
| [`resonator-prototype/`](resonator-prototype/README.md) | The `Resonator` neuron type + benchmarks vs Goertzel/FFT | Active |
| [`godot-runtime/`](godot-runtime/README.md) | GDScript backend — run a `.spk` brain live inside Godot | Active |
| [`godot-plugin/`](godot-plugin/README.md) | Godot editor addon wrapping the brain | Active |
| [`sdk-verilog/`](sdk-verilog/README_INDEX.md) | C + Verilog hardware backend, with testbench | Active |
| [`parallel-audio/`](parallel-audio/README_INDEX.md) | Real-time microphone/audio input engine (C, miniaudio + FFT) | Active, newest |
| [`benchmarks/`](benchmarks/BENCHMARKS.md) | Performance studies (dormant-vs-polling, gated resonators) | Active |
| [`fps-game/`](fps-game/README_INDEX.md) | An FPS whose enemy AI is driven by Spikeling brains | Complete |
| [`ai-apps/`](ai-apps/README_INDEX.md) | Ollama/RAG assistant apps built around Spikeling | Active |
| [`research/`](research/README_INDEX.md) | Stochastic-resonance experiments (does noise help inference?) | Exploratory |
| [`legacy-versions/`](legacy-versions/README_INDEX.md) | Superseded earlier scripts | Reference only |
| `build-artifacts/` | Compiled binaries (generated; excluded from git) | Generated |

**Not included here:** a separate, unrelated project is kept out of this
repository via `.gitignore`.

## Agent orchestration as an SNN

An experimental line of work tests whether a spiking neural network can serve
as the control layer for a multi-agent pipeline — routing tasks, managing
concurrency, and arbitrating conflicts through spike-based inhibition rather
than classical scheduling logic.

| File | What it does | What was verified |
|---|---|---|
| [`core/examples/agent_brain.spk`](core/examples/agent_brain.spk) | SNN definition for agent-routing and winner-take-all inhibition | Routing and lateral inhibition fire correctly in the Python runtime |
| [`spiking_orchestrator.py`](spiking_orchestrator.py) | Drives the agent pipeline from spike events | Integrates with the runtime; event dispatch works end-to-end |
| [`spiking_scheduler.py`](spiking_scheduler.py) | Maps spike activity to agent-slot concurrency scheduling | Mechanism works; falsified as a differentiator — produces identical assignments to classical greedy graph coloring |
| [`agent_runner.py`](agent_runner.py) | Executes individual agents under scheduler control | Runs agents correctly within the allocated slots |
| [`benchmark_scheduler.py`](benchmark_scheduler.py) | Compares SNN scheduler against greedy coloring across workloads | Confirms parity; no throughput advantage found |
| [`test_soft_conflicts.py`](test_soft_conflicts.py) | Tests a ternary consensus gate for soft (probabilistic) conflicts | Shows a small, real accuracy win under high conflict load, at substantial added complexity |
| [`test_incremental_scheduling.py`](test_incremental_scheduling.py) | Tests online incremental task arrival against classical online coloring | Exact tie — no advantage from the SNN path on incremental arrival |

The honest summary: the SNN routing and inhibition primitives work, but the
scheduling and arbitration results did not beat well-known classical baselines.

---

## License

MIT (source code). See [`LICENSE`](LICENSE).
