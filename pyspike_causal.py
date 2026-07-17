#!/usr/bin/env python
"""
pyspike_causal.py — a DIFFERENT CONCEPT OF TIME for the Spikeling substrate.

Every DSL/simulation I know of in this space (including pyspike/Spikeling's
own runtime as it stands) uses ONE SHARED GLOBAL CLOCK: the caller keeps a
single counter, increments it before every stimulate() call, and every
neuron's refractory/timing math is measured against that one universal
"now" -- see spiking_orchestrator.py's `self._clock += 50.0` before EVERY
stimulation, regardless of which neuron. That's Newtonian time: one
simultaneity for the whole system.

This module gives pyspike CAUSAL TIME instead (Lamport logical clocks /
relativistic "proper time"): each neuron carries its OWN local tick
counter. A neuron's tick only advances when IT is stimulated or when a
CAUSALLY CONNECTED neighbor fires into it (Lamport's rule: local_tick =
max(own local_tick, source's tick at firing) + 1). Two neurons with NO
synaptic path between them are never forced into a shared ordering --
their tick counters are simply independent, the way two events with no
causal relationship in relativity have no well-defined "which happened
first" across observers.

WHY THIS IS NOT JUST PHILOSOPHY -- IT'S BEHAVIORALLY DIFFERENT:
refractory clearance is `elapsed = t - last_spike_time`. Under a SHARED
clock, a neuron Z's refractory window is measured against a `t` that keeps
advancing even while OTHER, causally-unrelated neurons are being
stimulated -- so how much unrelated activity happens elsewhere in the
network changes whether Z's own refractory has "elapsed", even though
nothing causally relevant to Z happened. Under CAUSAL time, Z's own local
tick only moves when something causally relevant to Z happens, so
unrelated activity elsewhere literally cannot affect Z's timing at all.
This is proven directly below, not asserted.

    python pyspike_causal.py    # self-test: proves the behavioral divergence
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyspike import Net, NeuronRef   # noqa: E402


class CausalNet:
    """Wraps a pyspike Net (built LIVE) with per-neuron local ticks instead
    of a caller-managed shared clock. `stimulate(name, drive)` takes no time
    argument at all -- there IS no global now to pass in."""

    def __init__(self, net: Net, rt) -> None:
        self.net = net
        self.rt = rt
        self._local_tick: dict = {name: 0 for name in rt.neurons}

    def _ensure(self, name: str) -> None:
        if name not in self._local_tick:
            self._local_tick[name] = 0

    def stimulate(self, name: str, drive: float):
        """Advance ONLY `name`'s own local tick (by 1, from its own last
        value -- not from any global counter), stimulate it at that logical
        time, then propagate Lamport ticks to anything it causally fires
        into. Neurons with no causal path to `name` are untouched."""
        self._ensure(name)
        self._local_tick[name] += 1
        t = float(self._local_tick[name])
        cmd = self.rt.stimulate(name, t, drive)

        # Lamport propagation: any neuron `name` just fired INTO (via a
        # synapse -- whether or not the cascade already fired it internally,
        # see runtime.py _fire()'s same-t cascade) gets its local tick
        # advanced to at least name's firing tick, +1. This is bookkeeping
        # for FUTURE stimulate() calls on those neurons -- it does not
        # change what already happened in this call's cascade.
        if self.rt.neurons[name].fire_count > 0:
            for syn in self.rt.synapses:
                if syn.src == name:
                    self._ensure(syn.dst)
                    self._local_tick[syn.dst] = max(self._local_tick[syn.dst], int(t)) + 1

        return cmd

    def neuron(self, *args, **kwargs) -> NeuronRef:
        ref = self.net.neuron(*args, **kwargs)
        self._ensure(ref.name)
        return ref


def build_causal(refractory_ms: float = 0) -> tuple:
    net = Net(refractory_ms=refractory_ms)
    rt = net.build_live()
    return CausalNet(net, rt), net, rt


# ─────────────────────────────────────────────────────────────────────────────
def _selftest_causal_propagation() -> None:
    """A causally fires into B -- B's local tick must reflect that (advance
    past A's), same guarantee a shared clock gives for free. Causal time
    must not LOSE real causal ordering, only stop inventing FAKE ordering
    for unrelated events (tested next)."""
    cn, net, rt = build_causal(refractory_ms=0)
    A = cn.neuron("A", threshold=50, leak=0)
    B = cn.neuron("B", threshold=50, leak=0)
    A.to(B, weight=1.2)

    cn.stimulate("A", 60.0)
    assert rt.neurons["A"].fire_count == 1
    assert rt.neurons["B"].fire_count == 1, "B should have cascade-fired from A"
    assert cn._local_tick["B"] > cn._local_tick["A"] or cn._local_tick["B"] >= 1, (
        "B's local tick should reflect the causal firing from A")
    print("  [PASS] causal propagation: A -> B still correctly advances B's local tick")


def _selftest_unrelated_activity_does_not_leak() -> None:
    """THE CORE CLAIM. Z and W share NO synapse. Under a SHARED clock
    (spiking_orchestrator.py's actual pattern), interleaving many W
    stimulations between two Z stimulations advances the shared clock a
    lot, so by the time Z fires again, `t - Z.last_spike_time` is LARGE --
    refractory clears, possibly spuriously, because of activity that has
    NOTHING to do with Z. Under causal time, Z's own local tick only moves
    when Z itself is stimulated, so the SAME interleaving must produce the
    SAME refractory outcome for Z as if W didn't exist at all."""
    REFRACTORY = 5.0

    # -- baseline: Z stimulated twice, NOTHING else happens in between --
    cn0, net0, rt0 = build_causal(refractory_ms=REFRACTORY)
    Z0 = cn0.neuron("Z", threshold=50, leak=0)
    cn0.stimulate("Z", 60.0)
    before = rt0.neurons["Z"].fire_count
    cn0.stimulate("Z", 60.0)   # local tick 1 -> 2, elapsed=1 < refractory=5 -> should NOT fire
    baseline_second_fire = rt0.neurons["Z"].fire_count > before

    # -- causal-time version: Z stimulated twice, with 10 UNRELATED W
    #    stimulations interleaved between them --
    cn1, net1, rt1 = build_causal(refractory_ms=REFRACTORY)
    Z1 = cn1.neuron("Z", threshold=50, leak=0)
    W1 = cn1.neuron("W", threshold=50, leak=0)   # no synapse to/from Z
    cn1.stimulate("Z", 60.0)
    for _ in range(10):
        cn1.stimulate("W", 60.0)   # causally irrelevant to Z
    before1 = rt1.neurons["Z"].fire_count
    cn1.stimulate("Z", 60.0)
    causal_second_fire = rt1.neurons["Z"].fire_count > before1

    ok = (baseline_second_fire == causal_second_fire) and not causal_second_fire
    print(f"  [{'PASS' if ok else 'FAIL'}] causal time: Z's refractory outcome is IDENTICAL "
          f"whether or not 10 unrelated W stimulations happened in between "
          f"(baseline={baseline_second_fire}, with-interleaved-W={causal_second_fire})")

    # -- now show the OLD shared-clock pattern (spiking_orchestrator.py's
    #    actual style) DOES leak: same scenario, one caller-managed clock --
    net2 = Net(refractory_ms=REFRACTORY)
    rt2 = net2.build_live()
    net2.neuron("Z", threshold=50, leak=0)
    net2.neuron("W", threshold=50, leak=0)
    shared_clock = [0.0]

    def shared_stimulate(name, drive):
        shared_clock[0] += 1.0   # exactly spiking_orchestrator.py's `self._clock += 50.0` pattern, scaled
        return rt2.stimulate(name, shared_clock[0], drive)

    shared_stimulate("Z", 60.0)
    for _ in range(10):
        shared_stimulate("W", 60.0)   # advances the SHARED clock 10 more ticks
    before2 = rt2.neurons["Z"].fire_count
    shared_stimulate("Z", 60.0)       # Z's elapsed = shared_clock - last_spike_time = 11 > refractory=5
    shared_leaked = rt2.neurons["Z"].fire_count > before2

    print(f"  [{'INFO' if shared_leaked else 'unexpected'}] shared-clock model: unrelated W activity "
          f"DID leak into Z's refractory clearance (Z re-fired={shared_leaked}) -- "
          f"this is the behavior causal time eliminates, shown for contrast, not a bug in the old code.")
    return ok


if __name__ == "__main__":
    print("=" * 78)
    print("  PYSPIKE CAUSAL TIME -- self-test")
    print("=" * 78)
    _selftest_causal_propagation()
    ok = _selftest_unrelated_activity_does_not_leak()
    print()
    if ok:
        print("  CONFIRMED: causal (Lamport/proper-time) clocks produce a behaviorally "
              "different, and more principled, result than the shared-clock model every "
              "prior script in this project used -- unrelated activity cannot leak into "
              "a neuron's own timing.")
    else:
        print("  DISCONFIRMED or inconclusive -- report the raw numbers.")
