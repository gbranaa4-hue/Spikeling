"""
spikeling/examples/signal_test.py
==================================
Synthetic signal generators + a test harness for signal_detector.spk.

Three event types, each shaped to land on a different part of a
16-chunk SignalEncoder buffer:

  transient — sharp burst of energy at the START of the buffer, then quiet
  rising    — energy ramps up, peaking at the END of the buffer
  steady    — roughly constant energy across the WHOLE buffer (like noise)

Run directly:  python examples/signal_test.py
"""

import sys
import os
import math
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.compiler import compile_file
from runtime.runtime import SpikelingRuntime
from encoder.encoder import SignalEncoder


BUFFER_LEN = 160  # 160 samples / 16 channels = 10 samples per chunk


def make_transient(noise: float = 0.02) -> list[float]:
    """
    Loud burst spanning the first 6 of 16 encoder chunks (samples 0-59),
    silent after — matches HiddenEarly's wiring to In0..In5.
    """
    sig = []
    for i in range(BUFFER_LEN):
        if i < 60:
            v = 0.9 + random.uniform(-noise, noise)
        else:
            v = random.uniform(-noise, noise)
        sig.append(v)
    return sig


def make_rising(noise: float = 0.02) -> list[float]:
    """
    Quiet for the first 10 chunks, loud for the last 6 of 16 encoder
    chunks (samples 100-159) — matches HiddenLate's wiring to In10..In15.
    """
    sig = []
    for i in range(BUFFER_LEN):
        if i >= 100:
            v = 0.9 + random.uniform(-noise, noise)
        else:
            v = random.uniform(-noise, noise)
        sig.append(v)
    return sig


def make_steady(level: float = 0.5, noise: float = 0.05) -> list[float]:
    """Roughly constant amplitude across the whole buffer."""
    return [level + random.uniform(-noise, noise) for _ in range(BUFFER_LEN)]


def fire_signal(runtime, encoder, signal, base_time_ms, drive=80.0):
    """
    Encode + inject a signal buffer into the network's input neurons.
    Returns dict of {output_neuron_name: fired_bool}.
    """
    spike_train = encoder.encode(signal)
    neuron_names = list(runtime.neurons.keys())

    for neuron_idx, delay_ms in spike_train:
        name = neuron_names[neuron_idx % len(neuron_names)]
        t = base_time_ms + delay_ms
        runtime.stimulate(name, t, drive=drive)

    outputs = ["OutputTransient", "OutputRising", "OutputSteady"]
    return {name: runtime.neurons[name].fire_count for name in outputs}


def reset_network(runtime):
    """Zero out membrane potentials between independent trials."""
    for n in runtime.neurons.values():
        n.membrane_potential = 0.0


def run_trial(label, signal_fn, runtime, encoder, base_time_ms):
    reset_network(runtime)
    counts_before = {
        n: runtime.neurons[n].fire_count
        for n in ("OutputTransient", "OutputRising", "OutputSteady")
    }
    signal = signal_fn()
    fire_signal(runtime, encoder, signal, base_time_ms)
    counts_after = {
        n: runtime.neurons[n].fire_count
        for n in ("OutputTransient", "OutputRising", "OutputSteady")
    }
    deltas = {n: counts_after[n] - counts_before[n] for n in counts_after}
    winner = max(deltas, key=deltas.get) if any(deltas.values()) else "NONE"
    print(f"  [{label:10s}] fired -> {deltas}   winner: {winner}")
    return winner


if __name__ == "__main__":
    base = os.path.dirname(__file__)
    ast = compile_file(os.path.join(base, "signal_detector.spk"), output_dir=base)
    rt = SpikelingRuntime(ast)
    enc = SignalEncoder(num_neurons=16, window_ms=100.0, threshold=0.1)

    import time
    now = time.time() * 1000.0

    print("Trial 1 (no training yet — wiring only):")
    run_trial("transient", make_transient, rt, enc, now)
    now += 200
    run_trial("rising", make_rising, rt, enc, now)
    now += 200
    run_trial("steady", make_steady, rt, enc, now)
