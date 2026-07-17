#!/usr/bin/env python
"""
spiking_orchestrator.py — run the agent pipeline as a SPIKING NEURAL NETWORK.

The pipeline is no longer a fixed line of stages. It's the network in
core/examples/agent_brain.spk: every specialist agent is a NEURON that only
RUNS (spends tokens) when its membrane potential crosses threshold. A task is
scored into "sensory current"; the spikes that follow decide which agents fire.

    task text --score--> sensory neurons --spikes--> specialist neurons fire
                                                     --> that agent runs (tokens)

WHY THIS SAVES TOKENS (the whole point):
    A neuron below threshold never fires, so its agent never runs. A trivial
    task fires Implementer + Reviewer + Logger and nothing else — Clarifier,
    PreRegister, TestWriter, Corrector all stay dark and cost zero. A big
    ambiguous task lights the whole board. The saving is STRUCTURAL: it falls
    out of the LIF dynamics, it isn't an if-statement someone remembered to add.

WHY IT WON'T LOOP OR SHIP GARBAGE:
    refractory (in the .spk) stops an agent firing twice in one settle, so a
    correct->review->correct chain can't run away. Review gates the ledger:
    Corrector only fires when review's OUTPUT reports issues (result-driven
    stimulation, injected here — it depends on what the agent actually found).

Handlers run SYNCHRONOUSLY as neurons fire, and the runtime runs a fired
neuron's action BEFORE propagating its spike — so the flow self-sequences:
Implementer's agent finishes, THEN the spike drives Reviewer.

Run the demo (no API calls — proves the routing + the token savings):
    python spiking_orchestrator.py --demo
Run a real task through it (calls Claude via voice_commands.do_claude_code):
    python spiking_orchestrator.py "tribe: add a health bar to members"
"""

import json
import os
import re
import sys
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
from compiler.compiler import SpikelingParser      # noqa: E402
from runtime.runtime import SpikelingRuntime        # noqa: E402

BRAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "core", "examples", "agent_brain.spk")

# Every real routing decision gets appended here (one JSON object per line).
# This is the training data for the eventual learned score_task() replacement
# -- score_task() is the one hand-tuned, unverified piece left in the whole
# pipeline (see spiking_agent_pipeline.md memory), and a classifier needs
# real task -> decision pairs to train against, not synthetic demo cases.
DECISIONS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "task_decisions.jsonl")

# neuron -> the action command the runtime fires when it spikes (mirror of the
# `action` lines in the .spk; kept here so the orchestrator can register a
# handler per command)
COMMANDS = {
    "Clarifier":   "CMD_RUN_CLARIFY",
    "PreRegister": "CMD_RUN_PREREG",
    "Implementer": "CMD_RUN_IMPLEMENT",
    "TestWriter":  "CMD_RUN_TESTS",
    "Reviewer":    "CMD_RUN_REVIEW",
    "Corrector":   "CMD_RUN_CORRECT",
    "VaultLogger": "CMD_RUN_LOG",
}


# ─────────────────────────────────────────────────────────────────────────────
# SCORING — task text -> sensory current (0..100 per sensory neuron)
#
# This is the load-bearing, honest-about-it part: something has to decide "how
# much does this task need each agent". The prototype uses transparent
# heuristics; swapping in a learned classifier later changes ONLY this function.
# ─────────────────────────────────────────────────────────────────────────────
def score_task(task: str, project: str = "spikeling") -> dict:
    t = task.lower()
    words = re.findall(r"\w+", t)
    n = len(words)

    # S_Work: is there real work? almost always yes for a non-empty task.
    work = 70 if n >= 2 else 20

    # S_Ambiguous: short, vague, or a bare question with no concrete target.
    vague_markers = ["something", "somehow", "maybe", "fix stuff", "make it better",
                     "improve", "clean up", "etc"]
    ambiguous = 0
    if n <= 4:
        ambiguous += 45
    if any(m in t for m in vague_markers):
        ambiguous += 40
    if not re.search(r"\b(add|remove|change|rename|fix|move|write|implement|create|"
                     r"delete|refactor|update|build)\b", t):
        ambiguous += 25   # no clear verb -> what am I actually doing?

    # S_Complex: long, multi-clause, or names systems/rewrites.
    complex_markers = ["system", "refactor", "rewrite", "pipeline", "architecture",
                       "multiple", "several", "across", "integrate", "and also",
                       "as well as"]
    cplx = 0
    if n >= 18:
        cplx += 40
    if t.count(" and ") >= 2:
        cplx += 25
    if any(m in t for m in complex_markers):
        cplx += 35

    # S_Tests: explicitly about tests / verification.
    tests = 70 if re.search(r"\b(test|tests|testing|verify|coverage|assert|regression)\b", t) else 10

    # S_Research: a research codebase, or method/measurement language.
    research = 65 if (project.lower() in RESEARCH_PROJECTS
                      or re.search(r"\b(measure|experiment|benchmark|reservoir|"
                                   r"hypothesis|pre-?register)\b", t)) else 5

    clip = lambda v: max(0, min(100, v))
    return {
        "S_Work": clip(work), "S_Ambiguous": clip(ambiguous), "S_Complex": clip(cplx),
        "S_Tests": clip(tests), "S_Research": clip(research),
    }


RESEARCH_PROJECTS = {"phononics", "ternary", "methodlm", "symmetry", "quasicrystal", "spikeling"}


# ─────────────────────────────────────────────────────────────────────────────
# THE PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
class SpikingPipeline:
    def __init__(self, task: str, project: str = "spikeling", dry_run: bool = True,
                 review_finds_issues: bool = False):
        self.task = task
        self.project = project
        self.dry_run = dry_run
        self.review_finds_issues = review_finds_issues   # demo knob for the correct path
        self.fired: list[str] = []          # order agents actually ran
        self.outputs: dict[str, str] = {}
        self._clock = 0.0                    # sim ms; advances per agent so re-fires clear refractory
        self._followups: list[tuple] = []    # result-driven stimulations to apply after the cascade
        self._corrections = 0

        with open(BRAIN, encoding="utf-8") as f:
            ast = SpikelingParser().parse(f.read())
        self.rt = SpikelingRuntime(ast)
        for neuron, cmd in COMMANDS.items():
            self.rt.register_handler(cmd, self._make_handler(neuron))

    def _make_handler(self, neuron: str):
        def handler():
            self.fired.append(neuron)
            out = self._run_agent(neuron)
            self.outputs[neuron] = out
            # RESULT-DRIVEN ROUTING: review is the gate. Only a review that
            # reports issues wakes the Corrector, and only a couple of times.
            if neuron == "Reviewer" and self._review_reports_issues(out) and self._corrections < 2:
                self._corrections += 1
                self._followups.append(("Corrector", 60.0))
        return handler

    def _review_reports_issues(self, review_output: str) -> bool:
        if self.dry_run:
            return self.review_finds_issues and self._corrections < 1
        low = review_output.lower()
        return any(k in low for k in ["issue", "bug", "incorrect", "overclaim",
                                      "missing", "wrong", "fails", "does not"])

    def _run_agent(self, neuron: str) -> str:
        """Fire the agent. dry_run just records intent (no tokens); real mode
        calls into voice_commands.do_claude_code with the right preamble/tools."""
        if self.dry_run:
            return f"[dry-run] {neuron} would run on: {self.task[:60]}"
        return self._run_real_agent(neuron)

    def _run_real_agent(self, neuron: str) -> str:
        # Imported lazily so the demo/tests never touch the Claude CLI layer.
        import voice_commands as vc
        # Map each specialist to a concrete Claude Code invocation. Reuse the
        # existing tool tiers + preambles so this rides on the validated pipeline.
        if neuron == "Clarifier":
            # Clarifier STOPS the pipeline if it wants a question answered.
            return "(clarify stage — wire to vc.AGENT_CLARIFY_PREAMBLE)"
        tools = getattr(vc, "CLAUDE_CODE_TOOLS", None)
        if neuron == "Reviewer":
            tools = getattr(vc, "REVIEW_TOOLS", tools)
        return vc.do_claude_code(task=self._agent_task(neuron), tools=tools) or ""

    def _agent_task(self, neuron: str) -> str:
        # each specialist gets the task framed for its job
        frames = {
            "PreRegister": f"Before any edit, state ONE falsifiable claim about what this change will do: {self.task}",
            "Implementer": self.task,
            "TestWriter":  f"Add or adjust tests for: {self.task}",
            "Reviewer":    f"Peer-review the change for: {self.task}. Read-only. Call out overclaiming.",
            "Corrector":   f"Fix exactly what review flagged for: {self.task}",
            "VaultLogger": f"Write an honest ledger entry for the work on: {self.task}",
        }
        return frames.get(neuron, self.task)

    def run(self) -> dict:
        # 1. score the task into sensory current
        scores = score_task(self.task, self.project)

        # 2. CLARIFY IS A GATE, NOT A STAGE. If the task scores ambiguous, the
        #    Clarifier fires FIRST and the pipeline STOPS — you don't implement a
        #    task you don't understand, you ask one question and wait. This is the
        #    same "ask & stop" the real do_agent_task pipeline does, expressed as
        #    an inhibitory gate: a strong S_Ambiguous spike blocks the work path.
        if scores["S_Ambiguous"] >= 50:
            self._drive([("S_Ambiguous", scores["S_Ambiguous"])])
            result = {
                "scores": scores, "fired": self.fired, "agents_run": len(self.fired),
                "clarified": True,
                "agents_skipped": [n for n in COMMANDS if n not in self.fired],
            }
            self._log_decision(result)
            return result

        # 3. seed the work path; each sensory spike cascades synchronously through
        #    the spine (implement -> review), handlers running as neurons fire
        work_seeds = [(name, drive) for name, drive in scores.items() if name != "S_Ambiguous"]
        self._drive(work_seeds)

        # 4. drain result-driven follow-ups (corrections -> re-reviews) at an
        #    advancing clock so refractory clears for legitimate re-fires
        while self._followups:
            batch = self._followups
            self._followups = []
            self._drive(batch)

        # 5. write the ledger ONCE, at the end, after everything has settled
        if "Implementer" in self.fired:
            self._drive([("VaultLogger", 60.0)])

        result = {
            "scores": scores,
            "fired": self.fired,
            "agents_run": len(self.fired),
            "agents_skipped": [n for n in COMMANDS if n not in self.fired],
        }
        self._log_decision(result)
        return result

    def _drive(self, stimulations: list) -> None:
        for name, drive in stimulations:
            self._clock += 50.0            # each stimulation a step later in sim time
            self.rt.stimulate(name, self._clock, float(drive))

    def _log_decision(self, result: dict) -> None:
        """Append this routing decision as one JSON line. Logged for BOTH
        dry-run and real invocations -- dry_run is recorded on the entry so
        training can filter to real usage only, but demo/dry-run cases are
        still useful volume for early sanity checks. This is intentionally
        append-only and fails soft (a logging hiccup must never break the
        pipeline itself)."""
        entry = {
            "ts": time.time(),
            "task": self.task,
            "project": self.project,
            "dry_run": self.dry_run,
            "scores": result["scores"],
            "fired": result["fired"],
            "agents_run": result["agents_run"],
            "clarified": result.get("clarified", False),
            "agents_skipped": result["agents_skipped"],
        }
        try:
            with open(DECISIONS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass


def _print_result(task: str, res: dict) -> None:
    print(f"\n  TASK: {task}")
    hot = {k: v for k, v in res["scores"].items() if v >= 50}
    print(f"  sensory (>=50 fires): {hot}")
    print(f"  AGENTS RUN ({res['agents_run']}): {' -> '.join(res['fired'])}")
    print(f"  skipped (0 tokens): {', '.join(res['agents_skipped']) or 'none'}")


def demo() -> None:
    print("=" * 70)
    print("  SPIKING AGENT PIPELINE — token savings are structural")
    print("=" * 70)
    cases = [
        ("rename the fire_rate variable to shot_delay", False),
        ("add a test for the club-throw damage falloff", False),
        ("fix stuff", False),
        ("refactor the whole tribe economy across trade, war, and alliances "
         "and integrate it with the new terrain system and also add tests", True),
    ]
    for task, issues in cases:
        p = SpikingPipeline(task, dry_run=True, review_finds_issues=issues)
        _print_result(task, p.run())
    print("\n  ^ note how the trivial rename runs 3 agents while the big refactor")
    print("    lights the whole board — the cheap tasks stay cheap, automatically.\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="*", help="task to route (omit with --demo)")
    ap.add_argument("--demo", action="store_true", help="run the no-API routing demo")
    ap.add_argument("--project", default="spikeling")
    ap.add_argument("--real", action="store_true", help="actually run agents via Claude (spends tokens)")
    args = ap.parse_args()
    if args.demo or not args.task:
        demo()
        return
    task = " ".join(args.task)
    p = SpikingPipeline(task, project=args.project, dry_run=not args.real)
    _print_result(task, p.run())


if __name__ == "__main__":
    main()
