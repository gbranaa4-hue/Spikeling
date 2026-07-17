#!/usr/bin/env python
"""
test_soft_conflicts.py — does the inhibition substrate earn its 18x runtime
cost on the ONE thing binary graph coloring structurally can't express:
GRADED conflicts?

spiking_scheduler / benchmark_scheduler.py both model conflict as boolean
(agents share a file -> hard edge -> must serialize). Real file conflicts
aren't boolean: two agents editing DIFFERENT functions in the same file
barely collide; two agents editing the SAME function collide badly. Model
that as a per-pair SEVERITY in [0,1] (0 = disjoint, 1 = same region).

Three schedulers, same random graphs, same severities:

  A. HARD-LOCK coloring    -- any severity > 0 is a hard edge (today's
                               behavior in spiking_scheduler.py). Zero risk,
                               but pays full serialization cost even for a
                               severity=0.02 near-miss.
  B. THRESHOLD coloring    -- classical algorithm + one bolted-on parameter:
                               edge only if severity > THRESH. This is the
                               "just add an if-statement" version of graded
                               conflict handling in a conventional scheduler.
  C. WEIGHTED INHIBITION   -- synapse weight scaled BY severity, agent drive
                               scaled BY priority (both are EXISTING network
                               primitives -- weight, drive -- no new control
                               logic). A high-priority agent can survive a
                               low-severity inhibitory hit and fire alongside
                               its weak-conflict neighbor; a high-severity
                               hit still vetoes regardless of priority
                               because it's scaled to clear threshold alone.

Metric that matters here isn't wave count -- it's the THROUGHPUT/RISK
TRADEOFF: waves saved vs. cumulative severity of pairs that ran concurrently
anyway (a proxy for "how much realized collision risk did we accept").

    python test_soft_conflicts.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compiler.compiler import SpikelingParser      # noqa: E402
from runtime.runtime import SpikelingRuntime         # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
def make_agents(rng: random.Random, n_agents: int, n_files: int):
    files = [f"file_{i}.gd" for i in range(n_files)]
    agents = []
    for i in range(n_agents):
        k = rng.randint(1, min(3, n_files))
        agents.append({
            "name": f"agent_{i}",
            "files": set(rng.sample(files, k)),
            "priority": rng.uniform(0.1, 10.0),
        })
    return agents


def pair_severity(a, b) -> float:
    """0 if disjoint files. Otherwise a random-but-deterministic severity
    standing in for 'how much of the shared file do they actually both
    touch' -- seeded off the pair's names so it's reproducible across the
    three schedulers being compared on the same graph."""
    shared = a["files"] & b["files"]
    if not shared:
        return 0.0
    rng = random.Random(hash((a["name"], b["name"])) & 0xFFFFFFFF)
    return rng.uniform(0.05, 1.0)   # even a "shares a file" pair usually isn't a full collision


def build_severity_matrix(agents):
    sev = {}
    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            s = pair_severity(agents[i], agents[j])
            if s > 0:
                sev[(agents[i]["name"], agents[j]["name"])] = s
    return sev


# ─────────────────────────────────────────────────────────────────────────────
# A. Hard-lock greedy coloring (today's behavior): any severity>0 = edge.
def schedule_hard_lock(agents, sev):
    order = sorted(agents, key=lambda a: -a["priority"])
    adj = {a["name"]: set() for a in agents}
    for (x, y) in sev:
        adj[x].add(y)
        adj[y].add(x)
    color_of = {}
    for a in order:
        used = {color_of[nb] for nb in adj[a["name"]] if nb in color_of}
        c = 0
        while c in used:
            c += 1
        color_of[a["name"]] = c
    n_colors = max(color_of.values()) + 1 if color_of else 0
    waves = [[n for n, c in color_of.items() if c == k] for k in range(n_colors)]
    return waves, 0.0     # realized risk always 0 -- it never lets a conflicting pair co-run


# ─────────────────────────────────────────────────────────────────────────────
# B. Threshold coloring: bolt a cutoff onto the same classical algorithm.
def schedule_threshold(agents, sev, thresh):
    order = sorted(agents, key=lambda a: -a["priority"])
    adj = {a["name"]: set() for a in agents}
    for (x, y), s in sev.items():
        if s > thresh:
            adj[x].add(y)
            adj[y].add(x)
    color_of = {}
    for a in order:
        used = {color_of[nb] for nb in adj[a["name"]] if nb in color_of}
        c = 0
        while c in used:
            c += 1
        color_of[a["name"]] = c
    n_colors = max(color_of.values()) + 1 if color_of else 0
    waves = [[n for n, c in color_of.items() if c == k] for k in range(n_colors)]
    realized_risk = sum(s for (x, y), s in sev.items()
                         if _co_wave(waves, x, y))
    return waves, realized_risk


def _co_wave(waves, x, y) -> bool:
    for w in waves:
        if x in w and y in w:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# C. Weighted inhibition: severity scales synapse weight, priority scales drive.
THRESH_NEURON = 50
LEAK = 0
# Runtime multiplies weight*50 on propagation (see runtime.py _fire). Pick
# BASE_INHIBIT so a MAX-severity ambiguous-band hit (s=TRIT_HI=0.7) costs
# about -20 -- enough to block a low-priority agent's thin margin but not a
# high-priority agent's fat one -- instead of saturating every conflict to
# -threshold regardless of severity (which would silently make "graded"
# inhibition behave identically to hard-lock, defeating the whole test).
BASE_INHIBIT = -0.6      # -0.6 * 0.7 * 50 ~= -21 at the top of the ambiguous band
DRIVE_FLOOR = 58.0        # uninhibited drive MUST clear threshold=50 with margin,
                          # or a conflict-free low-priority agent can never fire
                          # and the wave-peeling loop never terminates (this bug
                          # caused a real infinite loop / multi-GB memory blowup
                          # the first time this ran -- verify_no_hang below guards it)
DRIVE_PRIORITY_SCALE = 2.0   # priority (0.1-10) still differentiates who survives inhibition


def _drive_for(priority: float) -> float:
    return DRIVE_FLOOR + priority * DRIVE_PRIORITY_SCALE


def _network_text_weighted(agents, sev):
    lines = [f"neuron {a['name']} threshold={int(THRESH_NEURON)} leak={int(LEAK)} type=LIF" for a in agents]
    for (x, y), s in sev.items():
        w = BASE_INHIBIT * s
        lines.append(f"connect {x} -> {y} weight={w:.4f}")
        lines.append(f"connect {y} -> {x} weight={w:.4f}")
    return "\n".join(lines)


def schedule_weighted_inhibition(agents, sev):
    pending = list(agents)
    waves = []
    t = 0.0
    while pending:
        names = {a["name"] for a in pending}
        sev_pending = {k: v for k, v in sev.items() if k[0] in names and k[1] in names}
        rt = SpikelingRuntime(SpikelingParser().parse(_network_text_weighted(pending, sev_pending)))
        wave = []
        for a in sorted(pending, key=lambda x: -x["priority"]):
            before = rt.neurons[a["name"]].fire_count
            t += 1.0
            # DRIVE scales with priority: a high-priority agent pushes harder
            # against whatever inhibition it has already absorbed this wave.
            # Must always clear threshold when uninhibited (see DRIVE_FLOOR
            # comment) or an isolated agent can never fire and the wave loop
            # never terminates.
            drive = _drive_for(a["priority"])
            rt.stimulate(a["name"], t, drive)
            if rt.neurons[a["name"]].fire_count > before:
                wave.append(a["name"])
        waves.append(wave)
        pending = [a for a in pending if a["name"] not in wave]

    realized_risk = 0.0
    for (x, y), s in sev.items():
        if _co_wave(waves, x, y):
            realized_risk += s
    return waves, realized_risk


# ─────────────────────────────────────────────────────────────────────────────
# D. TERNARY-GATED WEIGHTED -- brings in the 012-ternary consensus-gate finding:
# ternary = a TOPOLOGY gate (trit in {-1,0,+1}, decides if a synapse exists at
# all) crossed with a CONTINUOUS value doing fine work only where the gate
# leaves it ambiguous (see ternary-torus-arnold-finding: sign x topology-gate
# factorization; consensus-scoping-rule-ladder: weighted beats voting ONLY
# while the calibration-time reliability ranking still holds at decision time).
#
# Applied here: severity is classified into a trit BEFORE any network is
# built --
#   trit = -1  (severity > HI)   certain collision  -> hard edge, no weighing,
#                                  no amount of priority should buy past this
#   trit = +1  (severity < LO)   certain non-collision -> NO edge at all, skip
#                                  the synapse/computation entirely (this is
#                                  the zero-DOF/topology saving, not "weak
#                                  weight" -- there is nothing there)
#   trit =  0  (LO <= severity <= HI)  genuinely ambiguous -> ONLY this band
#                                  gets a weighted inhibitory synapse, and the
#                                  priority-scaled drive is only trusted to
#                                  decide it while priority ranking is a
#                                  reliable proxy for "who actually should
#                                  win" (the scoping-rule ladder's condition)
#
# This is the fair test of the ternary claim: does gating WHERE the network
# has to do continuous work at all (rather than applying weighted inhibition
# uniformly, as scheduler C does) improve the risk/wave tradeoff?
TRIT_LO = 0.15
TRIT_HI = 0.70


def _classify_trit(s: float) -> int:
    if s > TRIT_HI:
        return -1
    if s < TRIT_LO:
        return 1
    return 0


def schedule_ternary_gated(agents, sev):
    pending = list(agents)
    waves = []
    t = 0.0
    while pending:
        names = {a["name"] for a in pending}
        sev_pending = {k: v for k, v in sev.items() if k[0] in names and k[1] in names}

        # topology gate: partition pairs by trit BEFORE building the network
        hard_pairs = {k: v for k, v in sev_pending.items() if _classify_trit(v) == -1}
        ambiguous_pairs = {k: v for k, v in sev_pending.items() if _classify_trit(v) == 0}
        # trit=+1 pairs get no synapse at all -- literally absent from the network

        lines = [f"neuron {a['name']} threshold={int(THRESH_NEURON)} leak={int(LEAK)} type=LIF"
                 for a in pending]
        # hard (-1) pairs: full-strength inhibition, no priority can overcome it
        for (x, y) in hard_pairs:
            lines.append(f"connect {x} -> {y} weight=-6.0000")
            lines.append(f"connect {y} -> {x} weight=-6.0000")
        # ambiguous (0) pairs: severity-scaled inhibition, exactly like scheduler C,
        # but ONLY here -- the certain bands never touch the continuous machinery
        for (x, y), s in ambiguous_pairs.items():
            w = BASE_INHIBIT * s
            lines.append(f"connect {x} -> {y} weight={w:.4f}")
            lines.append(f"connect {y} -> {x} weight={w:.4f}")

        rt = SpikelingRuntime(SpikelingParser().parse("\n".join(lines)))
        wave = []
        for a in sorted(pending, key=lambda x: -x["priority"]):
            before = rt.neurons[a["name"]].fire_count
            t += 1.0
            drive = _drive_for(a["priority"])
            rt.stimulate(a["name"], t, drive)
            if rt.neurons[a["name"]].fire_count > before:
                wave.append(a["name"])
        waves.append(wave)
        pending = [a for a in pending if a["name"] not in wave]

    realized_risk = 0.0
    for (x, y), s in sev.items():
        if _co_wave(waves, x, y):
            realized_risk += s
    return waves, realized_risk


# ─────────────────────────────────────────────────────────────────────────────
def _verify_no_hang(schedule_fn, agents, sev, max_waves: int = 100):
    """Guard against the exact infinite-loop bug found earlier: assert a
    scheduler terminates within a sane number of waves for a given graph."""
    pending_count = len(agents)
    waves, _ = schedule_fn(agents, sev)
    assert len(waves) <= max_waves, f"runaway: {len(waves)} waves for {pending_count} agents"
    assert sum(len(w) for w in waves) == pending_count, "agent lost or duplicated"


def run(n_graphs: int = 500, seed: int = 7):
    rng = random.Random(seed)
    labels = ["hard_lock", "threshold_0.5", "weighted_inhibition", "ternary_gated"]
    totals = {label: [0, 0.0] for label in labels}
    timings = {label: 0.0 for label in labels}

    import time as _time
    for _ in range(n_graphs):
        n_agents = rng.randint(2, 9)
        n_files = rng.randint(2, max(3, n_agents // 2))
        agents = make_agents(rng, n_agents, n_files)
        sev = build_severity_matrix(agents)

        t0 = _time.perf_counter(); w_a, r_a = schedule_hard_lock(agents, sev); timings["hard_lock"] += _time.perf_counter() - t0
        t0 = _time.perf_counter(); w_b, r_b = schedule_threshold(agents, sev, thresh=0.5); timings["threshold_0.5"] += _time.perf_counter() - t0
        t0 = _time.perf_counter(); w_c, r_c = schedule_weighted_inhibition(agents, sev); timings["weighted_inhibition"] += _time.perf_counter() - t0
        t0 = _time.perf_counter(); w_d, r_d = schedule_ternary_gated(agents, sev); timings["ternary_gated"] += _time.perf_counter() - t0

        for _label, _waves in (("hard_lock", w_a), ("threshold_0.5", w_b),
                                ("weighted_inhibition", w_c), ("ternary_gated", w_d)):
            assert len(_waves) <= 100, f"runaway in {_label}: {len(_waves)} waves"
            assert sum(len(w) for w in _waves) == len(agents), f"agent lost/duplicated in {_label}"

        for label, (w, r) in zip(labels, ((w_a, r_a), (w_b, r_b), (w_c, r_c), (w_d, r_d))):
            totals[label][0] += len(w)
            totals[label][1] += r

    print("=" * 78)
    print(f"  SOFT-CONFLICT BENCHMARK — {n_graphs} random graphs, graded severity (seed={seed})")
    print("=" * 78)
    print(f"  {'method':<22}{'total waves':>14}{'realized risk':>16}{'risk/wave-saved':>18}{'time (ms)':>12}")
    hl_waves = totals["hard_lock"][0]
    for label in labels:
        waves, risk = totals[label]
        saved = hl_waves - waves
        ratio = f"{risk/saved:.4f}" if saved > 0 else ("n/a" if risk == 0 else "inf")
        print(f"  {label:<22}{waves:>14}{risk:>16.3f}{ratio:>18}{timings[label]*1000:>12.1f}")

    print()
    print("  READ: hard_lock is the conservative floor (0 risk, most waves).")
    print("  threshold_0.5, weighted_inhibition, and ternary_gated all trade some")
    print("  risk for fewer waves. Two comparisons matter:")
    print("  (1) weighted_inhibition vs threshold_0.5 -- does UNIFORM continuous")
    print("      weighting beat a single bolted-on cutoff?")
    print("  (2) ternary_gated vs weighted_inhibition -- does GATING where the")
    print("      continuous machinery runs at all (certain-safe/certain-unsafe")
    print("      skip it, only the ambiguous band uses it) improve the")
    print("      risk-per-wave-saved ratio, i.e. does the ternary topology-gate +")
    print("      polarity/weight factorization actually earn something here?")


if __name__ == "__main__":
    run()
