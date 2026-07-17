#!/usr/bin/env python
"""
pyspike_encoding.py — spike-train encoding: turning a real-valued input into
an actual sequence of spikes, instead of injecting a scalar "drive" directly
into membrane potential (what every other script in this project does).
This is the input-layer half of what makes an SNN an SNN in the standard
literature -- rate (Poisson) coding and temporal (latency) coding are the
two classical schemes.

  RATE CODING (Poisson): a real value in [0,1] becomes a per-tick
      probability of emitting a spike. Higher value = higher firing rate.
      This is how most neuromorphic vision/audio front-ends encode
      intensity.
  TEMPORAL/LATENCY CODING: a real value in [0,1] becomes the DELAY before a
      single spike fires -- higher value = fires SOONER. Carries the same
      information in far fewer spikes (one, not a whole rate-coded train),
      at the cost of being pure single-shot instead of continuously
      driving.

Both are verified against their own definitions (not just "runs without
crashing"): rate coding's empirical firing rate must track the requested
rate; latency coding's fire time must be monotonically decreasing in value.

    python pyspike_encoding.py    # self-test
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime.runtime import SpikelingRuntime, NeuronState   # noqa: E402


def poisson_spike_train(value: float, n_steps: int, max_rate: float = 1.0,
                        rng: random.Random = None) -> list:
    """value in [0,1] -> a list of n_steps booleans, each tick independently
    spiking with probability value*max_rate (a Bernoulli/Poisson-process
    approximation, the standard rate-coding scheme)."""
    rng = rng or random
    p = max(0.0, min(1.0, value)) * max_rate
    return [rng.random() < p for _ in range(n_steps)]


def latency_spike_time(value: float, n_steps: int) -> int:
    """value in [0,1] -> the tick index (0..n_steps-1) at which a SINGLE
    spike fires. Higher value = fires SOONER (value=1.0 -> tick 0;
    value=0.0 -> fires at the last tick, never for value<=0). This is the
    standard latency/rank-order coding scheme: intensity is carried by
    WHEN, not how often."""
    value = max(0.0, min(1.0, value))
    if value <= 0.0:
        return n_steps   # never fires within the window
    return int(round((1.0 - value) * (n_steps - 1)))


def drive_neuron_with_spike_train(threshold: float, leak: float,
                                  spike_train: list, spike_drive: float) -> dict:
    """Feed a boolean spike train into a fresh LIF neuron, ONE stimulate()
    per tick (drive=spike_drive on a True tick, drive=0.0 -- just a leak
    tick -- on a False tick). Returns fire_count and fire_times, so an
    encoding scheme's actual effect on a real neuron can be measured, not
    just the train itself."""
    rt = SpikelingRuntime.__new__(SpikelingRuntime)
    rt.neurons = {"x": NeuronState(name="x", threshold=threshold, leak=leak)}
    rt.resonators, rt.synapses, rt.actions, rt.handlers = {}, [], {}, {}
    rt.refractory_ms, rt.learner, rt._spike_log = 0.0, None, []

    fire_times = []
    for t, spiked in enumerate(spike_train, start=1):
        if spiked:
            rt.stimulate("x", float(t), spike_drive)
        else:
            rt.tick(float(t))
        if rt.neurons["x"].last_spike_time == float(t):
            fire_times.append(t)
    return {"fire_count": rt.neurons["x"].fire_count, "fire_times": fire_times}


# ─────────────────────────────────────────────────────────────────────────────
def _selftest_rate_coding_tracks_value() -> None:
    """A higher value should produce a higher EMPIRICAL firing rate in the
    generated spike train itself (not yet fed to a neuron -- this tests the
    encoding scheme, independent of neuron dynamics)."""
    rng = random.Random(0)
    n_steps = 2000
    results = {}
    for value in (0.1, 0.5, 0.9):
        train = poisson_spike_train(value, n_steps, max_rate=1.0, rng=rng)
        empirical_rate = sum(train) / n_steps
        results[value] = empirical_rate

    ok = results[0.1] < results[0.5] < results[0.9]
    for value in (0.1, 0.5, 0.9):
        print(f"    value={value}  requested_rate={value:.2f}  empirical_rate={results[value]:.3f}")
    print(f"  [{'PASS' if ok else 'FAIL'}] rate coding: empirical firing rate monotonically "
          f"tracks the encoded value")


def _selftest_latency_coding_monotonic() -> None:
    """A higher value must fire SOONER (lower tick index)."""
    n_steps = 100
    values = [0.1, 0.3, 0.5, 0.7, 0.9]
    times = [latency_spike_time(v, n_steps) for v in values]
    ok = all(times[i] > times[i + 1] for i in range(len(times) - 1))
    print(f"    values={values}")
    print(f"    fire_times={times}")
    print(f"  [{'PASS' if ok else 'FAIL'}] latency coding: higher value fires strictly sooner "
          f"(monotonic decreasing fire time)")


def _selftest_encoding_drives_a_real_neuron() -> None:
    """Confirm the encoded trains actually produce more/fewer real spikes
    when fed through an actual LIF neuron, not just as raw booleans."""
    rng = random.Random(1)
    n_steps = 500
    low_train = poisson_spike_train(0.1, n_steps, max_rate=1.0, rng=rng)
    high_train = poisson_spike_train(0.9, n_steps, max_rate=1.0, rng=rng)

    low_result = drive_neuron_with_spike_train(threshold=50.0, leak=5.0,
                                                spike_train=low_train, spike_drive=20.0)
    high_result = drive_neuron_with_spike_train(threshold=50.0, leak=5.0,
                                                spike_train=high_train, spike_drive=20.0)
    ok = high_result["fire_count"] > low_result["fire_count"]
    print(f"    low-rate (0.1) input  -> neuron fired {low_result['fire_count']} times")
    print(f"    high-rate (0.9) input -> neuron fired {high_result['fire_count']} times")
    print(f"  [{'PASS' if ok else 'FAIL'}] a real LIF neuron fires more often under the "
          f"high-rate-encoded train than the low-rate one")


if __name__ == "__main__":
    print("=" * 78)
    print("  PYSPIKE ENCODING -- rate (Poisson) and temporal (latency) spike coding")
    print("=" * 78)
    _selftest_rate_coding_tracks_value()
    _selftest_latency_coding_monotonic()
    _selftest_encoding_drives_a_real_neuron()
