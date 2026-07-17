#!/usr/bin/env python
"""
benchmark_scheduler.py — head-to-head: inhibition-based scheduling
(spiking_scheduler.schedule) vs. classic greedy graph coloring, on the
SAME random conflict graphs.

This is the experiment that turns "cool biological framing" into a real
claim. The inhibition scheduler is, structurally, a repeated-maximal-
independent-set peeling process: fire agents in priority order, a firing
inhibits every file-conflicting neighbor for the rest of THIS wave, then
peel off everyone who fired and repeat on what's left. Classic greedy
graph coloring (Welsh-Powell: sort by descending degree, assign each
node the lowest color not used by an already-colored neighbor) is the
textbook non-biological baseline for exactly this problem -- minimizing
the number of "waves" (colors) in a conflict graph.

Three schedulers compared on identical graphs:
  1. INHIBITION   -- spiking_scheduler.schedule() (priority-ordered, wave-peeling)
  2. DEGREE-GREEDY -- Welsh-Powell single-pass coloring, descending degree order
  3. PRIORITY-GREEDY -- single-pass coloring in the SAME priority order the
                        inhibition scheduler uses (isolates "peeling vs.
                        single-pass" from "what order", since inhibition
                        uses priority, not degree)

All three are checked for conflict-freedom. Wave/color COUNTS are compared
directly -- fewer is better (more concurrency per unit time).

    python benchmark_scheduler.py           # 500 random graphs, full report
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spiking_scheduler import AgentSpec, schedule, _overlaps  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Baseline 1: Welsh-Powell greedy coloring, ordered by descending degree.
# The standard non-biological baseline for "minimize the number of groups
# such that no group contains a conflicting pair."
def greedy_color_by_degree(agents: list) -> list:
    n = len(agents)
    adj = {a.name: set() for a in agents}
    for i in range(n):
        for j in range(i + 1, n):
            if _overlaps(agents[i], agents[j]):
                adj[agents[i].name].add(agents[j].name)
                adj[agents[j].name].add(agents[i].name)

    order = sorted(agents, key=lambda a: -len(adj[a.name]))
    color_of = {}
    for a in order:
        used = {color_of[nb] for nb in adj[a.name] if nb in color_of}
        c = 0
        while c in used:
            c += 1
        color_of[a.name] = c

    n_colors = max(color_of.values()) + 1 if color_of else 0
    return [[name for name, c in color_of.items() if c == k] for k in range(n_colors)]


# ─────────────────────────────────────────────────────────────────────────────
# Baseline 2: single-pass greedy coloring in the SAME order the inhibition
# scheduler uses (priority descending). Isolates the "peel repeated maximal
# independent sets" behavior from "which order agents are considered in" --
# inhibition could just be winning because of its ordering, not its mechanism.
def greedy_color_by_priority(agents: list) -> list:
    n = len(agents)
    adj = {a.name: set() for a in agents}
    for i in range(n):
        for j in range(i + 1, n):
            if _overlaps(agents[i], agents[j]):
                adj[agents[i].name].add(agents[j].name)
                adj[agents[j].name].add(agents[i].name)

    order = sorted(agents, key=lambda a: -a.priority)
    color_of = {}
    for a in order:
        used = {color_of[nb] for nb in adj[a.name] if nb in color_of}
        c = 0
        while c in used:
            c += 1
        color_of[a.name] = c

    n_colors = max(color_of.values()) + 1 if color_of else 0
    return [[name for name, c in color_of.items() if c == k] for k in range(n_colors)]


# ─────────────────────────────────────────────────────────────────────────────
def _conflict_free(agents: list, waves: list) -> bool:
    by_name = {a.name: a for a in agents}
    seen = set()
    for wave in waves:
        for i in range(len(wave)):
            seen.add(wave[i])
            for j in range(i + 1, len(wave)):
                if _overlaps(by_name[wave[i]], by_name[wave[j]]):
                    return False
    return seen == {a.name for a in agents}          # every agent scheduled exactly once


def _random_agents(rng: random.Random, n_agents: int, n_files: int) -> list:
    files = [f"file_{i}.gd" for i in range(n_files)]
    agents = []
    for i in range(n_agents):
        k = rng.randint(1, min(3, n_files))
        agents.append(AgentSpec(
            name=f"agent_{i}",
            files=set(rng.sample(files, k)),
            priority=rng.uniform(0.1, 10.0),
        ))
    return agents


def run_benchmark(n_graphs: int = 500, seed: int = 42) -> None:
    rng = random.Random(seed)
    results = {"inhibition": [], "degree_greedy": [], "priority_greedy": []}
    timings = {"inhibition": 0.0, "degree_greedy": 0.0, "priority_greedy": 0.0}
    violations = {"inhibition": 0, "degree_greedy": 0, "priority_greedy": 0}
    inhibition_wins = inhibition_losses = ties = 0

    for _ in range(n_graphs):
        n_agents = rng.randint(2, 9)
        n_files = rng.randint(2, max(3, n_agents // 2))
        agents = _random_agents(rng, n_agents, n_files)

        t0 = time.perf_counter()
        w_inhib = schedule(agents)
        timings["inhibition"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        w_degree = greedy_color_by_degree(agents)
        timings["degree_greedy"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        w_priority = greedy_color_by_priority(agents)
        timings["priority_greedy"] += time.perf_counter() - t0

        for label, waves in (("inhibition", w_inhib), ("degree_greedy", w_degree),
                              ("priority_greedy", w_priority)):
            if not _conflict_free(agents, waves):
                violations[label] += 1
            results[label].append(len(waves))

        if len(w_inhib) < len(w_degree):
            inhibition_wins += 1
        elif len(w_inhib) > len(w_degree):
            inhibition_losses += 1
        else:
            ties += 1

    print("=" * 72)
    print(f"  SCHEDULER BENCHMARK — {n_graphs} random conflict graphs (seed={seed})")
    print("=" * 72)
    print(f"  {'method':<18}{'avg waves':>12}{'total waves':>14}{'violations':>13}{'time (ms)':>12}")
    for label in ("inhibition", "degree_greedy", "priority_greedy"):
        vals = results[label]
        avg = sum(vals) / len(vals)
        print(f"  {label:<18}{avg:>12.3f}{sum(vals):>14}{violations[label]:>13}"
              f"{timings[label]*1000:>12.1f}")

    print()
    print(f"  vs. degree-ordered Welsh-Powell (the standard non-biological baseline):")
    print(f"    inhibition used FEWER waves on {inhibition_wins}/{n_graphs} graphs "
          f"({100*inhibition_wins//n_graphs}%)")
    print(f"    inhibition used MORE waves on {inhibition_losses}/{n_graphs} graphs "
          f"({100*inhibition_losses//n_graphs}%)")
    print(f"    tied on {ties}/{n_graphs} graphs ({100*ties//n_graphs}%)")

    total_inhib = sum(results["inhibition"])
    total_degree = sum(results["degree_greedy"])
    total_priority = sum(results["priority_greedy"])
    print()
    print(f"  total waves across all graphs: inhibition={total_inhib}  "
          f"degree_greedy={total_degree}  priority_greedy={total_priority}")
    if total_degree:
        delta = 100 * (total_degree - total_inhib) / total_degree
        print(f"  inhibition vs degree_greedy: {delta:+.1f}% waves (negative = inhibition worse)")
    if total_priority:
        delta2 = 100 * (total_priority - total_inhib) / total_priority
        print(f"  inhibition vs priority_greedy (same order, isolates the peeling "
              f"mechanism): {delta2:+.1f}%")

    print()
    print("  HONEST READ: inhibition-scheduling and priority-ordered single-pass")
    print("  greedy coloring should land at or near IDENTICAL wave counts when both")
    print("  use the same priority order -- the wave-peeling process the network")
    print("  implements is mathematically a greedy independent-set coloring. The")
    print("  differentiator is NOT a lower wave count; it's that the same substrate")
    print("  that computes the schedule is a real neural network with tunable")
    print("  synapses (leak, refractory, weight), so priority weighting, partial")
    print("  conflicts, and soft preferences fall out of existing primitives")
    print("  instead of needing bespoke scheduling code.")


if __name__ == "__main__":
    run_benchmark()
