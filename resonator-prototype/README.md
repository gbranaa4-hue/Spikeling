# Resonator neuron prototype

A different kind of Spikeling neuron. Instead of a leaky integrate-and-fire
unit (charge up, fire, reset), each **Resonator** is a **damped harmonic
oscillator** tuned to its own natural frequency. A mixed input signal drives a
whole bank of them at once, on one timeline — and each one only builds up
amplitude when the input contains energy near *its* frequency.

In other words: a **software analog filterbank built out of neuron-like
primitives**, separating signals by *frequency* rather than by time-slicing.
It plugs into Spikeling as a neuron type (`type=Resonator`) usable anywhere LIF
is — e.g. `signal_detector.spk`, `sound_localizer.spk`, or the FPS enemy's
"hearing" sense.

## How a single resonator works

State is a position `x` and velocity `v`, integrated with a stable
(symplectic) step:

```
x'' = -ω² x  -  2·damping·ω·v  +  coupling·drive
```

- **ω** = 2π·(natural frequency) — which input frequency it resonates with.
- **damping** sets the bandwidth / Q (lower damping = sharper, more selective).
- **coupling** sets how hard the input drives it (scaled by ω² so every channel
  in a bank has comparable gain at its own resonance, regardless of frequency).

Read out `energy()` (RMS of recent motion): high when the matching frequency is
present, low otherwise.

## Files

| File | What it does |
|---|---|
| `resonator_bank.py` | The `Resonator` class + a runnable demo: a 5-channel bank separating tones out of a noisy mixed signal. Run it directly. |
| `accuracy_benchmark.py` | Detection-accuracy test for the resonator detector across noise levels. |
| `vs_established_techniques.py` | Head-to-head comparison against established methods (Goertzel / FFT). |

```bash
python resonator_bank.py            # the filterbank demo
python accuracy_benchmark.py        # accuracy across noise
python vs_established_techniques.py # vs Goertzel / FFT
```

See [`../benchmarks/BENCHMARKS.md`](../benchmarks/BENCHMARKS.md) for the
written-up results.

## Where else this primitive shows up

The same damped-oscillator idea is reused beyond Spikeling — in a fully
nonlinear, coupled form — as the substrate in the physical
reservoir-computing / symmetry work. This folder is the clean, minimal
prototype of the primitive.
