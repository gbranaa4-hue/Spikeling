#!/usr/bin/env python
"""
test_pyspike_scheduler_parity.py — proves the pyspike-ported spiking_scheduler
produces IDENTICAL wave assignments to the old f-string+regex-parse version,
across many random conflict graphs. Not just "looks the same on the demo" --
an actual side-by-side comparison, same discipline as every other benchmark
in this project (see spiking_agent_pipeline.md memory).

    python test_pyspike_scheduler_parity.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compiler.compiler import SpikelingParser   # noqa: E402
from runtime.runtime import SpikelingRuntime      # noqa: E402
from spiking_scheduler import AgentSpec, schedule, INHIBIT_WEIGHT, DRIVE, THRESH, LEAK, _overlaps  # noqa: E402


def _old_text_based_schedule(agents: list) -> list:
    """The ORIGINAL implementation, kept here only as the comparison baseline
    -- f-string generates .spk text, SpikelingParser re-parses it, every wave."""
    def build_network_text(pending):
        lines = [f"neuron {a.name} threshold={THRESH} leak={LEAK} type=LIF" for a in pending]
        for i, a in enumerate(pending):
            for b in pending[i + 1:]:
                if _overlaps(a, b):
                    lines.append(f"connect {a.name} -> {b.name} weight={INHIBIT_WEIGHT}")
                    lines.append(f"connect {b.name} -> {a.name} weight={INHIBIT_WEIGHT}")
        return "\n".join(lines)

    pending = list(agents)
    waves = []
    t = 0.0
    while pending:
        rt = SpikelingRuntime(SpikelingParser().parse(build_network_text(pending)))
        wave = []
        for ag in sorted(pending, key=lambda x: -x.priority):
            before = rt.neurons[ag.name].fire_count
            t += 1.0
            rt.stimulate(ag.name, t, DRIVE)
            if rt.neurons[ag.name].fire_count > before:
                wave.append(ag.name)
        waves.append(wave)
        pending = [a for a in pending if a.name not in wave]
    return waves


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


def run(n_graphs: int = 500, seed: int = 42) -> None:
    rng = random.Random(seed)
    mismatches = 0
    for trial in range(n_graphs):
        n_agents = rng.randint(2, 9)
        n_files = rng.randint(2, max(3, n_agents // 2))
        agents = _random_agents(rng, n_agents, n_files)

        old_waves = _old_text_based_schedule(agents)
        new_waves = schedule(agents)   # the pyspike-ported version, imported live

        if old_waves != new_waves:
            mismatches += 1
            print(f"  MISMATCH on trial {trial}: old={old_waves}  new={new_waves}")

    print("=" * 70)
    print(f"  PYSPIKE SCHEDULER PARITY — {n_graphs} random graphs, seed={seed}")
    print("=" * 70)
    if mismatches == 0:
        print(f"  PASS: all {n_graphs} graphs produced byte-identical wave assignments "
              f"between the old text-based scheduler and the pyspike-ported one.")
    else:
        print(f"  FAIL: {mismatches}/{n_graphs} graphs diverged -- do not trust the port "
              f"until this is resolved.")


if __name__ == "__main__":
    run()
