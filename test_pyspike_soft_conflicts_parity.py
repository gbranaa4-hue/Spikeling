#!/usr/bin/env python
"""
test_pyspike_soft_conflicts_parity.py — proves the pyspike-ported
schedule_weighted_inhibition (C) and schedule_ternary_gated (D) from
test_soft_conflicts.py produce IDENTICAL wave assignments AND realized-risk
totals to the old f-string+regex-parse versions, across many random graphs.

The old versions rounded weights to 4 decimals (f"{w:.4f}") before parsing;
pyspike passes full-precision floats directly. This test checks whether that
rounding difference ever changes an outcome -- if it never does at this
scale, full precision is a strict improvement (no float-formatting bugs
possible) with no behavior change; if it DOES diverge somewhere, that's
reported honestly rather than assumed away.

    python test_pyspike_soft_conflicts_parity.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compiler.compiler import SpikelingParser   # noqa: E402
from runtime.runtime import SpikelingRuntime      # noqa: E402
import test_soft_conflicts as tsc                 # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# OLD text-based versions, kept here only as the comparison baseline.
def _old_network_text_weighted(agents, sev):
    lines = [f"neuron {a['name']} threshold={int(tsc.THRESH_NEURON)} leak={int(tsc.LEAK)} type=LIF"
             for a in agents]
    for (x, y), s in sev.items():
        w = tsc.BASE_INHIBIT * s
        lines.append(f"connect {x} -> {y} weight={w:.4f}")
        lines.append(f"connect {y} -> {x} weight={w:.4f}")
    return "\n".join(lines)


def _old_schedule_weighted_inhibition(agents, sev):
    pending = list(agents)
    waves = []
    t = 0.0
    while pending:
        names = {a["name"] for a in pending}
        sev_pending = {k: v for k, v in sev.items() if k[0] in names and k[1] in names}
        rt = SpikelingRuntime(SpikelingParser().parse(_old_network_text_weighted(pending, sev_pending)))
        wave = []
        for a in sorted(pending, key=lambda x: -x["priority"]):
            before = rt.neurons[a["name"]].fire_count
            t += 1.0
            drive = tsc._drive_for(a["priority"])
            rt.stimulate(a["name"], t, drive)
            if rt.neurons[a["name"]].fire_count > before:
                wave.append(a["name"])
        waves.append(wave)
        pending = [a for a in pending if a["name"] not in wave]

    realized_risk = 0.0
    for (x, y), s in sev.items():
        if tsc._co_wave(waves, x, y):
            realized_risk += s
    return waves, realized_risk


def _old_schedule_ternary_gated(agents, sev):
    pending = list(agents)
    waves = []
    t = 0.0
    while pending:
        names = {a["name"] for a in pending}
        sev_pending = {k: v for k, v in sev.items() if k[0] in names and k[1] in names}
        hard_pairs = {k: v for k, v in sev_pending.items() if tsc._classify_trit(v) == -1}
        ambiguous_pairs = {k: v for k, v in sev_pending.items() if tsc._classify_trit(v) == 0}
        lines = [f"neuron {a['name']} threshold={int(tsc.THRESH_NEURON)} leak={int(tsc.LEAK)} type=LIF"
                 for a in pending]
        for (x, y) in hard_pairs:
            lines.append(f"connect {x} -> {y} weight=-6.0000")
            lines.append(f"connect {y} -> {x} weight=-6.0000")
        for (x, y), s in ambiguous_pairs.items():
            w = tsc.BASE_INHIBIT * s
            lines.append(f"connect {x} -> {y} weight={w:.4f}")
            lines.append(f"connect {y} -> {x} weight={w:.4f}")
        rt = SpikelingRuntime(SpikelingParser().parse("\n".join(lines)))
        wave = []
        for a in sorted(pending, key=lambda x: -x["priority"]):
            before = rt.neurons[a["name"]].fire_count
            t += 1.0
            drive = tsc._drive_for(a["priority"])
            rt.stimulate(a["name"], t, drive)
            if rt.neurons[a["name"]].fire_count > before:
                wave.append(a["name"])
        waves.append(wave)
        pending = [a for a in pending if a["name"] not in wave]

    realized_risk = 0.0
    for (x, y), s in sev.items():
        if tsc._co_wave(waves, x, y):
            realized_risk += s
    return waves, realized_risk


# ─────────────────────────────────────────────────────────────────────────────
def run(n_graphs: int = 500, seed: int = 7) -> None:
    rng = random.Random(seed)
    mismatches = {"C (weighted_inhibition)": 0, "D (ternary_gated)": 0}
    risk_diffs = {"C (weighted_inhibition)": [], "D (ternary_gated)": []}

    for trial in range(n_graphs):
        n_agents = rng.randint(2, 9)
        n_files = rng.randint(2, max(3, n_agents // 2))
        agents = tsc.make_agents(rng, n_agents, n_files)
        sev = tsc.build_severity_matrix(agents)

        old_c, old_c_risk = _old_schedule_weighted_inhibition(agents, sev)
        new_c, new_c_risk = tsc.schedule_weighted_inhibition(agents, sev)
        if old_c != new_c:
            mismatches["C (weighted_inhibition)"] += 1
            print(f"  C MISMATCH trial {trial}: old={old_c}  new={new_c}")
        risk_diffs["C (weighted_inhibition)"].append(abs(old_c_risk - new_c_risk))

        old_d, old_d_risk = _old_schedule_ternary_gated(agents, sev)
        new_d, new_d_risk = tsc.schedule_ternary_gated(agents, sev)
        if old_d != new_d:
            mismatches["D (ternary_gated)"] += 1
            print(f"  D MISMATCH trial {trial}: old={old_d}  new={new_d}")
        risk_diffs["D (ternary_gated)"].append(abs(old_d_risk - new_d_risk))

    print("=" * 74)
    print(f"  PYSPIKE SOFT-CONFLICT PARITY — {n_graphs} random graphs, seed={seed}")
    print("=" * 74)
    for label in mismatches:
        m = mismatches[label]
        max_risk_diff = max(risk_diffs[label]) if risk_diffs[label] else 0.0
        status = "PASS" if m == 0 else "FAIL"
        print(f"  [{status}] {label}: {m}/{n_graphs} wave-assignment mismatches, "
              f"max realized-risk difference {max_risk_diff:.6f}")


if __name__ == "__main__":
    run()
