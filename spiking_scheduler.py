#!/usr/bin/env python
"""
spiking_scheduler.py — schedule CONCURRENT agents with a spiking network.

The problem this solves is the one that governed a whole game-build session by
hand: you can run many build-agents at once ONLY if they don't edit the same
files. Two agents both editing Tribemanager.gd will clobber each other, so they
must be serialized; two agents on disjoint files can run in parallel. Doing that
by hand means a human tracking every agent's file-set.

Here the network does it. Each agent is a NEURON. Every pair of agents whose
file-sets OVERLAP gets a pair of MUTUAL INHIBITORY synapses (weight < 0). When an
agent fires (claims its turn), it hyperpolarises every agent it conflicts with, so
those can't fire in the same wave -- while agents on disjoint files, having no
inhibitory link, fire together. One settle of the network = one conflict-free
"wave" of agents that may run concurrently. This is exactly the winner-take-all
behaviour of an inhibitory clique, turned into a scheduler.

Uses the Spikeling LIF runtime + the negative-weight (inhibitory) synapses added
to the DSL. Nothing here is bespoke scheduling logic -- the mutual inhibition IS
the schedule; the Python just reads off which neurons fired.

    python spiking_scheduler.py            # demo on a real session's conflict graph
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
from compiler.compiler import SpikelingParser      # noqa: E402
from runtime.runtime import SpikelingRuntime        # noqa: E402

# tuned so an inhibited agent stays suppressed for a whole wave regardless of how
# many agents are stimulated: firing drains a conflict to -threshold (-50); a
# stimulation of DRIVE=60 then only reaches 10, well under threshold 50. leak=0 on
# the scheduler neurons means a claim doesn't decay mid-wave.
INHIBIT_WEIGHT = -3.0     # * 50 = -150, clamped by the runtime to -threshold
DRIVE = 60.0
THRESH = 50
LEAK = 0


@dataclass
class AgentSpec:
    name: str
    files: set                       # the files this agent will EDIT
    priority: float = 1.0            # higher wins its turn earlier when conflicting
    run: Optional[Callable] = None   # what to actually execute (optional)


def _overlaps(a: AgentSpec, b: AgentSpec) -> bool:
    return not a.files.isdisjoint(b.files)


def _build_network_text(agents: list) -> str:
    """One neuron per agent + mutual inhibitory synapses between every overlapping
    pair. This generated .spk IS the conflict graph."""
    lines = [f"neuron {a.name} threshold={THRESH} leak={LEAK} type=LIF" for a in agents]
    for i, a in enumerate(agents):
        for b in agents[i + 1:]:
            if _overlaps(a, b):
                lines.append(f"connect {a.name} -> {b.name} weight={INHIBIT_WEIGHT}")
                lines.append(f"connect {b.name} -> {a.name} weight={INHIBIT_WEIGHT}")
    return "\n".join(lines)


def schedule(agents: list) -> list:
    """Return a list of WAVES. Each wave is a list of agent names that can run
    CONCURRENTLY -- guaranteed no two in a wave touch overlapping files. Agents
    are greedily packed by priority via the network's inhibition, so each wave is
    a maximal conflict-free set."""
    pending = list(agents)
    waves = []
    t = 0.0
    while pending:
        rt = SpikelingRuntime(SpikelingParser().parse(_build_network_text(pending)))
        wave = []
        # stimulate in priority order: a higher-priority agent fires first and
        # inhibits its conflicts, so a conflicting lower-priority agent, when
        # stimulated moments later, is already hyperpolarised and cannot fire.
        for ag in sorted(pending, key=lambda x: -x.priority):
            before = rt.neurons[ag.name].fire_count
            t += 1.0
            rt.stimulate(ag.name, t, DRIVE)
            if rt.neurons[ag.name].fire_count > before:
                wave.append(ag.name)          # it fired -> it's in this wave
        waves.append(wave)
        pending = [a for a in pending if a.name not in wave]
    return waves


def run(agents: list, verbose: bool = True) -> list:
    """Schedule, then execute wave by wave. Within a wave the agents are
    conflict-free, so a real integration would spawn them in PARALLEL; across
    waves it serialises. Returns the wave plan."""
    waves = schedule(agents)
    by_name = {a.name: a for a in agents}
    for i, wave in enumerate(waves, 1):
        if verbose:
            print(f"  wave {i}  (run these in parallel): {', '.join(wave)}")
        for name in wave:
            ag = by_name[name]
            if ag.run:
                ag.run()
    return waves


# ─────────────────────────────────────────────────────────────────────────────
def _assert_conflict_free(agents: list, waves: list) -> bool:
    by_name = {a.name: a for a in agents}
    for wave in waves:
        for i in range(len(wave)):
            for j in range(i + 1, len(wave)):
                if _overlaps(by_name[wave[i]], by_name[wave[j]]):
                    print(f"  !! CONFLICT in a wave: {wave[i]} & {wave[j]} share files")
                    return False
    return True


def demo() -> None:
    print("=" * 68)
    print("  SPIKING SCHEDULER — mutual inhibition = conflict-free concurrency")
    print("=" * 68)
    # the ACTUAL file-conflict graph from a real tribe-game build session
    agents = [
        AgentSpec("terrain",   {"terrain_gen.gd"}, priority=3),
        AgentSpec("swim",      {"FPSPlayer.gd"}, priority=2),
        AgentSpec("materials", {"tree.gd", "animal.gd", "npc.gd", "Tribemanager.gd"}, priority=5),
        AgentSpec("boats",     {"trade_envoy.gd", "Tribemanager.gd", "npc.gd"}, priority=4),
        AgentSpec("ui_boxes",  {"Tribemanager.gd", "world_tribe.gd", "tribe_chorus.gd"}, priority=1),
        AgentSpec("war_cross", {"npc.gd", "water_crossing.gd", "Tribemanager.gd"}, priority=2),
    ]
    waves = run(agents)
    ok = _assert_conflict_free(agents, waves)
    total = len(agents)
    print(f"\n  {total} agents scheduled into {len(waves)} waves; "
          f"conflict-free: {ok}")
    print("  note: terrain (terrain_gen.gd) and swim (FPSPlayer.gd) touch nobody")
    print("  else, so they ride along in parallel with a Tribemanager agent --")
    print("  and the four Tribemanager agents serialise, exactly as done by hand.")
    # what a naive one-at-a-time scheduler would cost
    print(f"\n  serial (1 agent/wave): {total} waves.  "
          f"this scheduler: {len(waves)} waves  "
          f"({100 * (total - len(waves)) // total}% fewer).")


if __name__ == "__main__":
    demo()
