#!/usr/bin/env python
"""
test_breathing_modulation.py — Experiment A from the "what if a neural
network could breathe" thread: does a periodic threshold rhythm recover a
STUCK neuron (the exact DRIVE_FLOOR pathology found and hand-patched in
test_soft_conflicts.py) better than plain random jitter, or is "breathing"
just a nicer name for noise?

THE BUG BEING RE-CREATED: in the scheduler tests, a wave-peeling loop
rebuilds a FRESH SpikelingRuntime every wave (membrane_potential resets to
0) and stimulates each pending agent EXACTLY ONCE per wave. If an agent's
single stimulate() call never crosses threshold, it never leaves `pending`
and the loop hangs forever -- that's the real multi-GB memory blowup this
session hit before DRIVE_FLOOR was hand-added as a floor. This experiment
asks: instead of a hardcoded floor, could a THRESHOLD that breathes (dips
low once per cycle) let the neuron recover on its own?

Each "attempt" here is exactly that shape: build a throwaway neuron
(potential=0), stimulate it ONCE with a constant drive, check whether IT
fired. Three threshold conditions, same constant drive, same deficit:

  STATIC     -- threshold never moves. Reproduces the hang (positive control).
  BREATHING  -- threshold(t) = base - amplitude*sin(2*pi*breathe_hz*t).
                Periodic, deterministic dip.
  JITTER     -- threshold(t) = base + gaussian noise, VARIANCE-MATCHED to the
                breathing signal (same average deviation, no periodicity).
                This is the control that decides the question: if jitter
                recovers just as fast as breathing, rhythm bought nothing
                over noise.

PRE-REGISTERED PREDICTION: breathing recovers deterministically within one
cycle once amplitude clears the deficit; jitter recovers only
probabilistically and should take longer on average (and sometimes not at
all within the same tick budget). If that's wrong -- if jitter matches or
beats breathing -- the honest conclusion is "breathing" is not doing
anything specific, it's just noise with a rhythm.

    python test_breathing_modulation.py
"""

import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime.runtime import SpikelingRuntime, NeuronState   # noqa: E402

MAX_TICKS = 500          # give up and call it "stuck" past this many attempts
BASE_THRESHOLD = 50.0
DRIVE = 45.0              # constant deficit of 5 below base threshold -- mirrors
                          # the real DRIVE_FLOOR bug's shape (uninhibited drive
                          # that fell a few points short of threshold)


def _bare_runtime() -> SpikelingRuntime:
    rt = SpikelingRuntime.__new__(SpikelingRuntime)
    rt.neurons = {}
    rt.resonators = {}
    rt.synapses = []
    rt.actions = {}
    rt.refractory_ms = 0.0
    rt.learner = None
    rt.handlers = {}
    rt._spike_log = []
    return rt


def _attempt(threshold: float, drive: float) -> bool:
    """One throwaway neuron, one stimulate() call -- exactly the shape of
    'one agent, one stimulate() per wave' that produced the real hang."""
    rt = _bare_runtime()
    rt.neurons["x"] = NeuronState(name="x", threshold=threshold, leak=0.0)
    rt.stimulate("x", 1.0, drive)
    return rt.neurons["x"].fire_count > 0


# ─────────────────────────────────────────────────────────────────────────────
def run_static(max_ticks: int = MAX_TICKS) -> int:
    """Threshold never moves. Should NEVER recover (positive control,
    reproduces the real hang)."""
    for t in range(1, max_ticks + 1):
        if _attempt(BASE_THRESHOLD, DRIVE):
            return t
    return -1   # never fired within the budget


def run_breathing(breathe_hz: float, amplitude: float, phase0: float,
                  max_ticks: int = MAX_TICKS) -> int:
    for t in range(1, max_ticks + 1):
        threshold = BASE_THRESHOLD - amplitude * math.sin(2 * math.pi * breathe_hz * t + phase0)
        if _attempt(threshold, DRIVE):
            return t
    return -1


def run_jitter(rng: random.Random, amplitude: float, max_ticks: int = MAX_TICKS) -> int:
    # variance-match: sin(x) has variance 1/2, so a zero-mean gaussian with
    # std = amplitude/sqrt(2) has the SAME variance as amplitude*sin(...) --
    # equal average deviation from baseline, no periodicity.
    std = amplitude / math.sqrt(2)
    for t in range(1, max_ticks + 1):
        threshold = BASE_THRESHOLD + rng.gauss(0.0, std)
        if _attempt(threshold, DRIVE):
            return t
    return -1


# ─────────────────────────────────────────────────────────────────────────────
def _summarize(label: str, results: list) -> None:
    n = len(results)
    stuck = sum(1 for r in results if r == -1)
    recovered = [r for r in results if r != -1]
    if recovered:
        recovered.sort()
        mean = sum(recovered) / len(recovered)
        median = recovered[len(recovered) // 2]
        worst = max(recovered)
    else:
        mean = median = worst = float("nan")
    print(f"  {label:<22}{n:>6}{stuck:>10}{len(recovered):>12}"
          f"{mean:>10.1f}{median:>10}{worst:>10}")


def run(n_trials: int = 200, breathe_hz: float = 0.05, seed: int = 3):
    rng = random.Random(seed)
    deficit = BASE_THRESHOLD - DRIVE   # = 5.0

    print("=" * 80)
    print(f"  BREATHING vs JITTER — recovering a stuck neuron (deficit={deficit:.1f}, "
          f"{n_trials} trials/condition, seed={seed})")
    print("=" * 80)

    for amplitude, label in ((3.0, "amplitude < deficit (should NEVER recover, either way)"),
                              (10.0, "amplitude > deficit (the real test)")):
        print(f"\n  --- amplitude={amplitude} :: {label} ---")
        print(f"  {'condition':<22}{'trials':>6}{'stuck':>10}{'recovered':>12}"
              f"{'mean t':>10}{'median t':>10}{'worst t':>10}")

        static_results = [run_static() for _ in range(1)]   # deterministic, one run suffices
        _summarize("static (control)", static_results * n_trials)

        breathing_results = [run_breathing(breathe_hz, amplitude, rng.uniform(0, 2 * math.pi))
                             for _ in range(n_trials)]
        _summarize("breathing", breathing_results)

        jitter_results = [run_jitter(rng, amplitude) for _ in range(n_trials)]
        _summarize("jitter (control)", jitter_results)

    print()
    print("  READ: 'static' should show 100% stuck at both amplitudes (positive control --")
    print("  reproduces the real DRIVE_FLOOR hang exactly). At amplitude=3 (< deficit=5),")
    print("  breathing and jitter should ALSO both be 100% stuck -- neither can help if the")
    print("  swing never reaches the deficit, regardless of shape. The real test is")
    print("  amplitude=10: if breathing recovers in fewer/more-consistent ticks than jitter,")
    print("  rhythm is doing something real. If jitter matches or beats it, breathing is")
    print("  just noise with a story attached.")


if __name__ == "__main__":
    run()
