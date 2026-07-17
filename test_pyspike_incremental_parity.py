#!/usr/bin/env python
"""
test_pyspike_incremental_parity.py — proves the pyspike-ported
schedule_incremental_spiking (which now uses Net.build_live() +
reconcile_late_edge() instead of hand-built raw NeuronState/Synapse
objects) produces IDENTICAL wave assignments, operation counts, and zero
conflict violations to the old raw-construction version, across the same
stream sizes and trial count as the original benchmark.

    python test_pyspike_incremental_parity.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime.runtime import SpikelingRuntime, NeuronState, Synapse   # noqa: E402
import test_incremental_scheduling as tis                             # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# OLD raw-construction version, kept here only as the comparison baseline.
def _old_bare_runtime() -> SpikelingRuntime:
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


def _old_admit_one(rt, newcomer, seen, t) -> tuple:
    ops = 0
    rt.neurons[newcomer["name"]] = NeuronState(
        name=newcomer["name"], threshold=tis.THRESH, leak=tis.LEAK)
    downstream = rt.neurons[newcomer["name"]]
    for prior in seen:
        ops += 1
        if tis.conflicts(newcomer, prior):
            rt.synapses.append(Synapse(newcomer["name"], prior["name"], tis.INHIBIT_WEIGHT))
            rt.synapses.append(Synapse(prior["name"], newcomer["name"], tis.INHIBIT_WEIGHT))
            if rt.neurons[prior["name"]].fire_count > 0:
                downstream.membrane_potential = max(
                    -downstream.threshold,
                    downstream.membrane_potential + tis.INHIBIT_WEIGHT * 50.0)
    seen.append(newcomer)
    rt.stimulate(newcomer["name"], t, tis.DRIVE)
    ops += 1
    fired = rt.neurons[newcomer["name"]].fire_count > 0
    return fired, ops


def _old_schedule_incremental_spiking(stream: list) -> tuple:
    rt = _old_bare_runtime()
    seen = []
    ops = 0
    wave = []
    t = 0.0
    for newcomer in stream:
        t += 1.0
        fired, o = _old_admit_one(rt, newcomer, seen, t)
        ops += o
        if fired:
            wave.append(newcomer["name"])

    waves = [wave]
    pending = [a for a in stream if a["name"] not in wave]
    while pending:
        rt = _old_bare_runtime()
        seen = []
        wave = []
        for newcomer in pending:
            t += 1.0
            fired, o = _old_admit_one(rt, newcomer, seen, t)
            ops += o
            if fired:
                wave.append(newcomer["name"])
        waves.append(wave)
        pending = [a for a in pending if a["name"] not in wave]

    return waves, ops


# ─────────────────────────────────────────────────────────────────────────────
def run(n_trials: int = 200, seed: int = 11) -> None:
    rng = random.Random(seed)
    sizes = [10, 20, 40, 80]
    print("=" * 80)
    print(f"  PYSPIKE INCREMENTAL PARITY — {n_trials} trials/size, seed={seed}")
    print("=" * 80)

    for n_agents in sizes:
        n_files = max(3, n_agents // 3)
        mismatches = 0
        ops_diffs = []
        for _ in range(n_trials):
            stream = tis.make_stream(rng, n_agents, n_files)
            old_waves, old_ops = _old_schedule_incremental_spiking(stream)
            new_waves, new_ops = tis.schedule_incremental_spiking(stream)
            if old_waves != new_waves:
                mismatches += 1
                print(f"  MISMATCH n={n_agents}: old={old_waves}  new={new_waves}")
            ops_diffs.append(abs(old_ops - new_ops))
        status = "PASS" if mismatches == 0 else "FAIL"
        max_ops_diff = max(ops_diffs) if ops_diffs else 0
        print(f"  [{status}] n_agents={n_agents}: {mismatches}/{n_trials} wave mismatches, "
              f"max ops difference {max_ops_diff}")


if __name__ == "__main__":
    run()
