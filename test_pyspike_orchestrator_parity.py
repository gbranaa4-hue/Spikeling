#!/usr/bin/env python
"""
test_pyspike_orchestrator_parity.py — proves the pyspike-built agent_brain
topology in spiking_orchestrator.py's SpikingPipeline produces IDENTICAL
`fired` sequences (including the Reviewer<->Corrector correction loop and
refractory behavior) to the original .spk-text-parsed version, across the
full demo suite plus extra edge cases.

This is the highest-stakes port so far -- it's the actual production agent
pipeline, not a benchmark script -- so it gets the most thorough parity
check: every demo case, both review outcomes (issues found / not found),
and a couple of additional edge cases the demo suite didn't cover.

    python test_pyspike_orchestrator_parity.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compiler.compiler import SpikelingParser   # noqa: E402
from runtime.runtime import SpikelingRuntime      # noqa: E402
import spiking_orchestrator as so                  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# OLD .spk-text-parsed pipeline, kept here only as the comparison baseline.
class _OldSpikingPipeline:
    def __init__(self, task, project="spikeling", dry_run=True, review_finds_issues=False):
        self.task = task
        self.project = project
        self.dry_run = dry_run
        self.review_finds_issues = review_finds_issues
        self.fired = []
        self.outputs = {}
        self._clock = 0.0
        self._followups = []
        self._corrections = 0
        self._review_gates = []

        with open(so.BRAIN, encoding="utf-8") as f:
            ast = SpikelingParser().parse(f.read())
        self.rt = SpikelingRuntime(ast)
        for neuron, cmd in so.COMMANDS.items():
            self.rt.register_handler(cmd, self._make_handler(neuron))

    def _make_handler(self, neuron):
        def handler():
            self.fired.append(neuron)
            out = self._run_agent(neuron)
            self.outputs[neuron] = out
            if neuron == "Reviewer" and self._review_reports_issues(out) and self._corrections < 2:
                self._corrections += 1
                self._followups.append(("Corrector", 60.0))
        return handler

    def _review_reports_issues(self, review_output):
        if self.dry_run:
            return self.review_finds_issues and self._corrections < 1
        gate = so.gate_review(review_output)
        self._review_gates.append(gate)
        return gate["decision"]

    def _run_agent(self, neuron):
        if self.dry_run:
            return f"[dry-run] {neuron} would run on: {self.task[:60]}"
        return self._run_real_agent(neuron)

    def _run_real_agent(self, neuron):
        import voice_commands as vc
        if neuron == "Clarifier":
            return "(clarify stage — wire to vc.AGENT_CLARIFY_PREAMBLE)"
        tools = getattr(vc, "CLAUDE_CODE_TOOLS", None)
        if neuron == "Reviewer":
            tools = getattr(vc, "REVIEW_TOOLS", tools)
        return vc.do_claude_code(task=self._agent_task(neuron), tools=tools) or ""

    def _agent_task(self, neuron):
        frames = {
            "PreRegister": f"Before any edit, state ONE falsifiable claim about what this change will do: {self.task}",
            "Implementer": self.task,
            "TestWriter":  f"Add or adjust tests for: {self.task}",
            "Reviewer":    f"Peer-review the change for: {self.task}. Read-only. Call out overclaiming.",
            "Corrector":   f"Fix exactly what review flagged for: {self.task}",
            "VaultLogger": f"Write an honest ledger entry for the work on: {self.task}",
        }
        return frames.get(neuron, self.task)

    def run(self):
        scores = so.score_task(self.task, self.project)
        if scores["S_Ambiguous"] >= 50:
            self._drive([("S_Ambiguous", scores["S_Ambiguous"])])
            return {
                "scores": scores, "fired": self.fired, "agents_run": len(self.fired),
                "clarified": True,
                "agents_skipped": [n for n in so.COMMANDS if n not in self.fired],
            }
        work_seeds = [(name, drive) for name, drive in scores.items() if name != "S_Ambiguous"]
        self._drive(work_seeds)
        while self._followups:
            batch = self._followups
            self._followups = []
            self._drive(batch)
        if "Implementer" in self.fired:
            self._drive([("VaultLogger", 60.0)])
        return {
            "scores": scores,
            "fired": self.fired,
            "agents_run": len(self.fired),
            "agents_skipped": [n for n in so.COMMANDS if n not in self.fired],
        }

    def _drive(self, stimulations):
        for name, drive in stimulations:
            self._clock += 50.0
            self.rt.stimulate(name, self._clock, float(drive))


# ─────────────────────────────────────────────────────────────────────────────
def run() -> None:
    cases = [
        # (task, review_finds_issues)
        ("rename the fire_rate variable to shot_delay", False),
        ("add a test for the club-throw damage falloff", False),
        ("fix stuff", False),
        ("refactor the whole tribe economy across trade, war, and alliances "
         "and integrate it with the new terrain system and also add tests", True),
        # extra edge cases beyond the demo suite
        ("write a test for the new resonator bank", False),
        ("write a test for the new resonator bank", True),          # same task, correction path
        ("investigate and benchmark the reservoir memory capacity", False),  # S_Research trigger
        ("a", False),                                                  # minimal/degenerate input
        ("", False),                                                    # empty task
        ("refactor and rewrite the whole architecture across every subsystem "
         "and also add extensive tests and also verify everything and also "
         "benchmark the new pipeline", True),                          # maximal complexity + correction
    ]

    print("=" * 74)
    print("  PYSPIKE ORCHESTRATOR PARITY")
    print("=" * 74)
    mismatches = 0
    for task, issues in cases:
        old = _OldSpikingPipeline(task, dry_run=True, review_finds_issues=issues)
        old_res = old.run()

        new = so.SpikingPipeline(task, dry_run=True, review_finds_issues=issues)
        new_res = new.run()

        ok = (old_res["fired"] == new_res["fired"]
              and old_res["scores"] == new_res["scores"]
              and old_res["agents_run"] == new_res["agents_run"]
              and old_res.get("clarified", False) == new_res.get("clarified", False)
              and sorted(old_res["agents_skipped"]) == sorted(new_res["agents_skipped"]))
        status = "PASS" if ok else "FAIL"
        if not ok:
            mismatches += 1
        print(f"  [{status}] task={task[:50]!r:52} issues={issues!s:5}  "
              f"fired={new_res['fired']}")
        if not ok:
            print(f"         OLD: {old_res}")
            print(f"         NEW: {new_res}")

    print()
    if mismatches == 0:
        print(f"  ALL {len(cases)} CASES PASS: pyspike-built brain matches "
              f".spk-parsed brain exactly, including the correction loop and refractory.")
    else:
        print(f"  {mismatches}/{len(cases)} CASES MISMATCHED -- do not trust the port "
              f"until this is resolved.")


if __name__ == "__main__":
    run()
