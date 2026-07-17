#!/usr/bin/env python
"""
test_incremental_scheduling.py — the last untested candidate from the
soft-conflict follow-up: does the spiking substrate earn its cost on
INCREMENTAL scheduling (agents arriving one at a time mid-wave, deciding
each admission without recomputing everyone already scheduled)?

Three approaches, same random arrival streams:

  A. BATCH-RECOMPUTE  -- the naive baseline: every time a new agent shows
                          up, recolor the WHOLE accumulated set from
                          scratch (degree-order greedy coloring). Correct,
                          but cost grows with total-agents-seen-so-far on
                          EVERY arrival -- O(n) work per arrival, O(n^2)
                          total for a stream of length n.
  B. ONLINE-GREEDY     -- the real classical incremental baseline: colour
                          each new agent ONCE, using only the colors of its
                          ALREADY-ARRIVED neighbors, and never touch a
                          previously assigned color again. This is the
                          standard "greedy coloring is naturally online"
                          fact -- O(degree) work per arrival, no rebuild.
  C. INCREMENTAL SPIKING -- add one neuron + its synapses to a LIVE,
                          already-running SpikelingRuntime instance (no
                          reparse, no rebuild -- Python objects are mutated
                          in place) and stimulate it once. Prior neurons'
                          membrane state is untouched. If the substrate's
                          "no recompute needed" story is real, this should
                          match B's operation-count profile (O(degree) per
                          arrival) while being a genuinely different
                          mechanism (accumulated membrane potential instead
                          of a color-conflict lookup).

COST is measured as OPERATION COUNTS (edges touched / stimulate calls),
not wall-clock -- isolates algorithmic behavior from Python/parsing
overhead, which would otherwise just re-litigate the earlier "same
algorithm, slower substrate" result instead of testing what's new here
(incrementality, not raw speed).

    python test_incremental_scheduling.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime.runtime import SpikelingRuntime, NeuronState, Synapse   # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
def make_stream(rng: random.Random, n_agents: int, n_files: int):
    files = [f"file_{i}.gd" for i in range(n_files)]
    stream = []
    for i in range(n_agents):
        k = rng.randint(1, min(3, n_files))
        stream.append({
            "name": f"agent_{i}",
            "files": set(rng.sample(files, k)),
            "priority": rng.uniform(0.1, 10.0),
        })
    rng.shuffle(stream)      # ARRIVAL order, independent of any priority/id order
    return stream


def conflicts(a, b) -> bool:
    return not a["files"].isdisjoint(b["files"])


# ─────────────────────────────────────────────────────────────────────────────
# A. Batch-recompute: full degree-order greedy recoloring on EVERY arrival.
def schedule_batch_recompute(stream: list) -> tuple:
    seen = []
    ops = 0
    color_of = {}
    for newcomer in stream:
        seen.append(newcomer)
        # full recolor of everyone seen so far, from scratch
        adj = {a["name"]: set() for a in seen}
        for i in range(len(seen)):
            for j in range(i + 1, len(seen)):
                ops += 1
                if conflicts(seen[i], seen[j]):
                    adj[seen[i]["name"]].add(seen[j]["name"])
                    adj[seen[j]["name"]].add(seen[i]["name"])
        color_of = {}
        order = sorted(seen, key=lambda a: -len(adj[a["name"]]))
        for a in order:
            used = {color_of[nb] for nb in adj[a["name"]] if nb in color_of}
            c = 0
            while c in used:
                c += 1
            color_of[a["name"]] = c
            ops += 1
    n_colors = max(color_of.values()) + 1 if color_of else 0
    waves = [[n for n, c in color_of.items() if c == k] for k in range(n_colors)]
    return waves, ops


# ─────────────────────────────────────────────────────────────────────────────
# B. Online greedy: color each arrival ONCE against already-arrived neighbors.
# Never revisits a prior assignment. The textbook "coloring is naturally
# online" baseline.
def schedule_online_greedy(stream: list) -> tuple:
    seen = []
    ops = 0
    color_of = {}
    for newcomer in stream:
        used = set()
        for prior in seen:
            ops += 1
            if conflicts(newcomer, prior):
                used.add(color_of[prior["name"]])
        c = 0
        while c in used:
            c += 1
        color_of[newcomer["name"]] = c
        seen.append(newcomer)
        ops += 1
    n_colors = max(color_of.values()) + 1 if color_of else 0
    waves = [[n for n, c in color_of.items() if c == k] for k in range(n_colors)]
    return waves, ops


# ─────────────────────────────────────────────────────────────────────────────
# C. Incremental spiking: mutate a LIVE runtime instance in place, one
# arrival at a time. No reparse, no rebuild -- prior neurons' membrane
# potentials are exactly as they were left after their own stimulation.
INHIBIT_WEIGHT = -3.0
DRIVE = 60.0            # must clear THRESH alone -- see the earlier hang bug
THRESH = 50.0
LEAK = 0.0


def _bare_runtime() -> SpikelingRuntime:
    """Construct a SpikelingRuntime without going through the DSL parser --
    neurons/synapses are plain Python containers, so they can be mutated
    incrementally exactly like any other in-memory data structure."""
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


def _admit_one(rt: SpikelingRuntime, newcomer: dict, seen: list, t: float) -> tuple:
    """Add one agent's neuron + conflict synapses to a LIVE runtime and decide
    admission. Because this runtime's inhibition is EVENT-DRIVEN (applied only
    at the instant the source neuron fires -- see runtime.py _fire), a synapse
    created AFTER its source already fired would otherwise never deliver that
    neighbor's veto: the firing event is in the past, the synapse didn't exist
    yet, propagation doesn't replay. So any already-fired conflicting neighbor
    must have its inhibitory effect applied to the newcomer MANUALLY, right
    now, mirroring exactly what _fire()'s propagation step already does for
    synapses that existed at firing time. This is not a workaround bolted on
    top of the substrate -- it's what 'incremental' has to mean for an
    event-driven network: a late-arriving edge must reconcile against
    already-realized events, the same way a newly-placed lock must check
    already-held locks rather than assume it'll be notified retroactively."""
    ops = 0
    rt.neurons[newcomer["name"]] = NeuronState(
        name=newcomer["name"], threshold=THRESH, leak=LEAK)
    downstream = rt.neurons[newcomer["name"]]
    for prior in seen:
        ops += 1
        if conflicts(newcomer, prior):
            rt.synapses.append(Synapse(newcomer["name"], prior["name"], INHIBIT_WEIGHT))
            rt.synapses.append(Synapse(prior["name"], newcomer["name"], INHIBIT_WEIGHT))
            if rt.neurons[prior["name"]].fire_count > 0:
                # reconcile against an event already in the past
                downstream.membrane_potential = max(
                    -downstream.threshold,
                    downstream.membrane_potential + INHIBIT_WEIGHT * 50.0)
    seen.append(newcomer)
    rt.stimulate(newcomer["name"], t, DRIVE)
    ops += 1
    fired = rt.neurons[newcomer["name"]].fire_count > 0
    return fired, ops


def schedule_incremental_spiking(stream: list) -> tuple:
    rt = _bare_runtime()
    seen = []
    ops = 0
    wave = []
    t = 0.0
    for newcomer in stream:
        t += 1.0
        fired, o = _admit_one(rt, newcomer, seen, t)
        ops += o
        if fired:
            wave.append(newcomer["name"])

    waves = [wave]
    pending = [a for a in stream if a["name"] not in wave]
    # subsequent waves: same incremental-arrival process on what's left,
    # replaying the SAME arrival order (a fresh live runtime per wave --
    # membrane state from a finished wave has no reason to carry over)
    while pending:
        rt = _bare_runtime()
        seen = []
        wave = []
        for newcomer in pending:
            t += 1.0
            fired, o = _admit_one(rt, newcomer, seen, t)
            ops += o
            if fired:
                wave.append(newcomer["name"])
        waves.append(wave)
        pending = [a for a in pending if a["name"] not in wave]

    return waves, ops


# ─────────────────────────────────────────────────────────────────────────────
def _conflict_free(agents_by_name: dict, waves: list) -> bool:
    seen = set()
    for wave in waves:
        for i in range(len(wave)):
            seen.add(wave[i])
            for j in range(i + 1, len(wave)):
                if conflicts(agents_by_name[wave[i]], agents_by_name[wave[j]]):
                    return False
    return True


def run(n_trials: int = 200, seed: int = 11):
    rng = random.Random(seed)
    sizes = [10, 20, 40, 80]
    print("=" * 84)
    print(f"  INCREMENTAL SCHEDULING BENCHMARK — {n_trials} trials/size, seed={seed}")
    print("=" * 84)
    print(f"  {'n_agents':>9}{'method':>24}{'avg waves':>12}{'avg ops':>14}{'violations':>13}")

    for n_agents in sizes:
        n_files = max(3, n_agents // 3)
        totals = {"batch_recompute": [0, 0, 0], "online_greedy": [0, 0, 0],
                  "incremental_spiking": [0, 0, 0]}   # [waves, ops, violations]

        for _ in range(n_trials):
            stream = make_stream(rng, n_agents, n_files)
            by_name = {a["name"]: a for a in stream}

            w_a, ops_a = schedule_batch_recompute(stream)
            w_b, ops_b = schedule_online_greedy(stream)
            w_c, ops_c = schedule_incremental_spiking(stream)

            assert len(w_c) <= n_agents + 1, "runaway in incremental_spiking"

            for label, waves, ops in (("batch_recompute", w_a, ops_a),
                                       ("online_greedy", w_b, ops_b),
                                       ("incremental_spiking", w_c, ops_c)):
                totals[label][0] += len(waves)
                totals[label][1] += ops
                if not _conflict_free(by_name, waves):
                    totals[label][2] += 1

        for label in ("batch_recompute", "online_greedy", "incremental_spiking"):
            waves, ops, viol = totals[label]
            print(f"  {n_agents:>9}{label:>24}{waves/n_trials:>12.2f}{ops/n_trials:>14.1f}{viol:>13}")
        print()

    print("  READ: ops growth vs n_agents is the real signal.")
    print("  batch_recompute should show ~O(n^2) growth (redoes everything on every")
    print("  arrival). online_greedy and incremental_spiking should BOTH show ~O(n)")
    print("  growth if the substrate's 'no recompute needed' claim is real -- i.e.")
    print("  incremental_spiking's ops/n_agents ratio should stay roughly FLAT across")
    print("  sizes, matching online_greedy's shape, not batch_recompute's. Wave-count")
    print("  quality should be compared too: matching online_greedy's colors at")
    print("  online_greedy's cost profile is a TIE (no advantage, no regression) --")
    print("  the substrate would need EITHER fewer waves OR lower ops growth than")
    print("  online_greedy to be a genuine win here.")


if __name__ == "__main__":
    run()
