#!/usr/bin/env python
"""
agent_runner.py — execute a scheduled agent plan: run each wave's agents IN
PARALLEL, thread results back, serialise across waves.

spiking_scheduler.py decides WHICH agents may run together (a wave = a
conflict-free set, computed by mutual inhibition over their file-sets). This is
the other half: actually SPAWNING a wave's agents concurrently, collecting what
they return, and carrying those results forward to later waves.

Why threads (not processes): a real agent is a `subprocess.run([claude, ...])`
call -- I/O / child-process bound, which releases the GIL, so a ThreadPoolExecutor
gives true wall-clock parallelism for a wave. Agents in a wave are conflict-free
by construction, so running them at once can't corrupt shared files.

Two ways to supply an agent's work:
  - MOCK: AgentSpec(run=some_callable) -- for tests / dry runs (no tokens).
  - REAL: claude_agent(name, files, task, ...) -- run() shells out to Claude via
    voice_commands.do_claude_code (lazy-imported, so tests never touch the CLI).

Results feed back: each agent's run() receives the accumulated {name: result} of
every PRIOR wave, so a later agent can build on earlier ones.

    python agent_runner.py        # mock demo: proves parallelism + feedback
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spiking_scheduler import AgentSpec, schedule, _overlaps   # noqa: E402


def _invoke(agent: AgentSpec, context: dict):
    """Call an agent's run(), passing prior-wave results if it accepts them."""
    fn = agent.run
    if fn is None:
        return None
    try:
        return fn(context)          # run(context) -> result
    except TypeError:
        return fn()                 # run() -> result  (context-free)


def run_pipeline(agents: list, verbose: bool = True) -> dict:
    """Schedule the agents, then execute wave by wave. A wave's agents run
    concurrently; results accumulate and are handed to every later wave.
    Returns {agent_name: result}."""
    waves = schedule(agents)
    by_name = {a.name: a for a in agents}
    results: dict = {}
    for i, wave in enumerate(waves, 1):
        if verbose:
            print(f"  wave {i}: spawning {len(wave)} in parallel -> {', '.join(wave)}")
        snapshot = dict(results)    # prior waves only -- same input for all in this wave
        # true parallel spawn of the (conflict-free) wave
        with ThreadPoolExecutor(max_workers=max(1, len(wave))) as pool:
            futs = {pool.submit(_invoke, by_name[name], snapshot): name for name in wave}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    results[name] = fut.result()
                except Exception as e:      # one agent failing must not sink the wave
                    results[name] = f"[FAILED] {e}"
                    if verbose:
                        print(f"    !! {name} failed: {e}")
        if verbose:
            print(f"    wave {i} done; results so far: {sorted(results)}")
    return results


def claude_agent(name: str, files: set, task: str, project_dir: Optional[str] = None,
                 tools: Optional[list] = None, priority: float = 1.0) -> AgentSpec:
    """Build a REAL agent whose run() shells out to Claude Code. The task is
    augmented with a short digest of prior-wave results so later agents can build
    on earlier ones. voice_commands is imported LAZILY so tests never load the CLI
    layer."""
    def _run(context: dict):
        import voice_commands as vc
        prompt = task
        if context:
            prior = "\n".join(f"- {k}: {str(v)[:200]}" for k, v in context.items())
            prompt = f"{task}\n\n(Context from earlier agents:\n{prior}\n)"
        return vc.do_claude_code(task=prompt, project_dir=project_dir, tools=tools)
    return AgentSpec(name=name, files=set(files), priority=priority, run=_run)


# ─────────────────────────────────────────────────────────────────────────────
def demo() -> None:
    print("=" * 68)
    print("  AGENT RUNNER — parallel within a wave, results fed forward")
    print("=" * 68)
    log = []

    def make(work_s: float, produces: str):
        # a mock agent: sleeps (stands in for a real subprocess call), records
        # the prior-wave context it received, and returns a result
        def _run(context: dict):
            got = sorted(context.keys())
            time.sleep(work_s)
            log.append((produces, got))
            return f"{produces}(saw={got})"
        return _run

    agents = [
        # wave 1: three disjoint-file agents -> should run at the SAME time
        AgentSpec("terrain",   {"terrain_gen.gd"}, priority=3, run=make(0.30, "terrain")),
        AgentSpec("swim",      {"FPSPlayer.gd"},   priority=2, run=make(0.30, "swim")),
        AgentSpec("materials", {"Tribemanager.gd", "npc.gd"}, priority=5, run=make(0.30, "materials")),
        # these clash with materials on Tribemanager.gd -> later waves
        AgentSpec("boats",     {"Tribemanager.gd", "trade_envoy.gd"}, priority=4, run=make(0.20, "boats")),
        AgentSpec("war_cross", {"Tribemanager.gd", "npc.gd"}, priority=1, run=make(0.20, "war_cross")),
    ]

    t0 = time.time()
    results = run_pipeline(agents)
    wall = time.time() - t0

    print(f"\n  wall-clock: {wall:.2f}s")
    print("  if serial it would be ~1.20s (0.30*3 + 0.20*2); parallel-per-wave")
    print("  collapses wave 1's three 0.30s agents into ONE 0.30s.")
    # prove feedback: a later agent SAW earlier results
    late = [entry for entry in log if entry[0] == "boats"]
    if late:
        print(f"\n  feedback check: 'boats' ran seeing prior results {late[0][1]}")
    print(f"  final results: {results}")


if __name__ == "__main__":
    demo()
