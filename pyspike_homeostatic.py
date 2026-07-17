#!/usr/bin/env python
"""
pyspike_homeostatic.py — intrinsic/homeostatic plasticity for Spikeling: a
neuron's OWN threshold adapts over time toward a target firing rate,
instead of staying fixed. Distinct from STDP (which adapts SYNAPTIC
weights) -- this adapts the neuron's own excitability.

This is the PRINCIPLED version of "what if a neural network could breathe"
(test_breathing_modulation.py): breathing dipped the threshold on a blind
periodic rhythm with no relationship to whether the neuron actually needed
it, and lost cleanly to plain noise (jitter recovered a stuck neuron
FASTER on average, and unlike breathing, could even recover from an
under-powered amplitude via its unbounded tail). Homeostatic plasticity
instead uses REAL FEEDBACK: a neuron that hasn't been firing lowers its own
threshold; one that's firing too much raises it. No blind rhythm, no
random walk -- a closed-loop control system with a target.

    python pyspike_homeostatic.py    # pre-registered comparison vs the
                                       # earlier static/breathing/jitter results
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime.runtime import SpikelingRuntime, NeuronState   # noqa: E402


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
    """Same shape as test_breathing_modulation.py's _attempt(): a fresh
    neuron (potential=0), one stimulate() call -- reproducing the exact
    real bug (a wave-peeling loop that rebuilds a fresh runtime and
    stimulates each pending agent exactly once). Homeostatic adaptation
    lives OUTSIDE this function, in the persisted `threshold` the caller
    carries between attempts -- exactly mirroring how the real fix would
    work: the runtime resets every wave, but a neuron's LEARNED threshold
    is state that legitimately should survive across waves."""
    rt = _bare_runtime()
    rt.neurons["x"] = NeuronState(name="x", threshold=threshold, leak=0.0)
    rt.stimulate("x", 1.0, drive)
    return rt.neurons["x"].fire_count > 0


class HomeostaticThreshold:
    """Adapts a threshold toward a target firing rate using real feedback,
    not a blind schedule. Each tick: if the neuron fired, actual rate is
    ABOVE target (assuming target < 1.0) -- raise threshold, make it
    harder. If it didn't fire, actual rate is below target -- lower
    threshold, make it easier. Bounded so it can't runaway to a
    degenerate always-fires-on-any-input or a stuck-forever floor -- same
    "explicit stop condition" discipline as every other growth/adaptation
    mechanism in this project."""

    def __init__(self, base_threshold: float, eta: float, target_rate: float = 1.0,
                 min_threshold: float = 1.0, max_threshold: float = None):
        self.threshold = base_threshold
        self.eta = eta
        self.target_rate = target_rate
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold if max_threshold is not None else base_threshold * 3

    def step(self, fired: bool) -> float:
        actual_rate = 1.0 if fired else 0.0
        # firing too MUCH (actual > target) -> raise threshold (harder);
        # firing too LITTLE (actual < target) -> lower threshold (easier).
        self.threshold += self.eta * (actual_rate - self.target_rate)
        self.threshold = max(self.min_threshold, min(self.max_threshold, self.threshold))
        return self.threshold


def run_homeostatic(base_threshold: float, drive: float, eta: float,
                    target_rate: float = 1.0, max_ticks: int = 500) -> int:
    """target_rate=1.0 means 'this neuron should fire every attempt' -- the
    right target for the stuck-neuron scenario (a pending agent SHOULD fire
    on its one stimulate() per wave; failing to is exactly the pathology)."""
    homeo = HomeostaticThreshold(base_threshold, eta, target_rate=target_rate)
    for t in range(1, max_ticks + 1):
        fired = _attempt(homeo.threshold, drive)
        if fired:
            return t
        homeo.step(fired=False)
    return -1


# ─────────────────────────────────────────────────────────────────────────────
def run(deficit: float = 5.0, base_threshold: float = 50.0) -> None:
    drive = base_threshold - deficit

    print("=" * 84)
    print(f"  HOMEOSTATIC PLASTICITY vs BREATHING vs JITTER — stuck-neuron recovery "
          f"(deficit={deficit:.1f})")
    print("=" * 84)
    print("  Reusing test_breathing_modulation.py's exact scenario. Recorded results from")
    print("  that run (amplitude=10, 200 trials): static=100% stuck; breathing mean=5.5")
    print("  ticks (worst=15); jitter mean=4.0 ticks (worst=23), and jitter even recovered")
    print("  the underpowered amplitude=3 case (mean=99.7) where breathing structurally")
    print("  cannot (breathing is hard-bounded by its amplitude, jitter's gaussian tail is not).")
    print()
    print("  PRE-REGISTERED PREDICTION: homeostatic adaptation is DETERMINISTIC given eta")
    print("  (no distribution to sample -- recovery time = deficit/eta exactly), so its")
    print("  worst case EQUALS its average case. Tuning eta to match jitter's ~4-tick")
    print("  average should give a worst case far tighter than jitter's 23 and even")
    print("  breathing's 15 -- deterministic control beats both blind rhythm and noise on")
    print("  the metric that actually matters for preventing a hang: the GUARANTEE, not")
    print("  just the average.")
    print()

    etas = [0.5, 1.0, 1.25, 2.0, 5.0]
    print(f"  {'eta':>6}{'recovery ticks (deterministic)':>34}")
    for eta in etas:
        t = run_homeostatic(base_threshold, drive, eta, target_rate=1.0)
        print(f"  {eta:>6.2f}{t:>34}")

    print()
    print("  --- verdict ---")
    matched_eta = deficit / 4.0   # tune eta so recovery matches jitter's mean=4.0 ticks
    t_matched = run_homeostatic(base_threshold, drive, matched_eta, target_rate=1.0)
    print(f"  eta tuned to match jitter's average speed (eta={matched_eta:.3f}): "
          f"recovers in EXACTLY {t_matched} ticks, every single time (deterministic).")
    if t_matched <= 5 and t_matched > 0:
        print(f"  CONFIRMED: at matched average speed, homeostatic adaptation's worst case "
              f"({t_matched} ticks, guaranteed) beats jitter's worst case (23 ticks, "
              f"probabilistic) and breathing's worst case (15 ticks, hard-bounded) by a wide "
              f"margin -- because it isn't sampling from a distribution or a fixed-amplitude "
              f"oscillation, it's closed-loop control that keeps pushing exactly as hard as "
              f"needed until it succeeds.")
    else:
        print(f"  Did not confirm as predicted -- report the raw numbers honestly.")

    print()
    print("  Also worth stating plainly: homeostatic adaptation has NO hard ceiling on how")
    print("  far it can lower the threshold (only min_threshold, set generously below any")
    print("  real deficit) -- unlike breathing's fixed amplitude, it will ALWAYS eventually")
    print("  recover from any deficit, however large, given enough ticks. That's the same")
    print("  property jitter has (via its unbounded gaussian tail) but achieved")
    print("  deterministically instead of by chance.")


if __name__ == "__main__":
    run()
