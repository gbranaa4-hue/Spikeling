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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyspike import Net   # noqa: E402

# PORTED TO PYSPIKE (2026-07-17): this used to parse core/examples/agent_brain.spk
# at every SpikingPipeline() construction. The topology is now built directly
# via pyspike.Net in _build_brain() below -- same benefits as the scheduler
# ports (no text round-trip) plus a real simplification: handlers attach
# straight to their neuron via @net.action() instead of going through the old
# neuron -> COMMAND STRING -> handler-dict indirection. Verified spike-for-
# spike identical `fired` sequences (including the Reviewer<->Corrector
# correction loop and refractory behavior) to the .spk-parsed version across
# the full demo suite before this replaced it (test_pyspike_orchestrator_parity.py).
#
# agent_brain.spk is KEPT in the repo as the human-readable topology
# reference and as the source for the C code generator / hardware backend --
# it is NOT read by this file anymore. If you change the topology, update
# BOTH _build_brain() below and agent_brain.spk, or they will drift; there is
# no automatic sync between them.
BRAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "core", "examples", "agent_brain.spk")   # kept for reference/C-backend only

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
# TERNARY GATE — Reviewer output -> correct-or-not
#
# First real wiring of the trit-gate pattern validated in
# test_soft_conflicts.py's ternary_gated scheduler (see spiking_agent_pipeline.md
# memory). The old logic was a single flat keyword match -- any hit = correct,
# no hit = clean. That collapses "one nitpick" and "breaks the build" into the
# same decision. This scores a SEVERITY in [0,1] instead and bands it into
# hard_safe / ambiguous / hard_unsafe.
#
# HONEST NOTE, found by testing before trusting: the scheduler's ternary gate
# saved real cost by skipping an expensive SNN network build in the hard
# bands. The FIRST version of this gate copied that shape literally -- only
# checking escalation/hedge markers (critical, security, regression, minor,
# typo...) inside the ambiguous band -- and that was a bug, not an
# optimization: those markers are substring checks, exactly as cheap as the
# base issue-markers, so there was no real cost being saved. It also produced
# a false negative: "Found a critical security issue... this introduces a
# regression" scored severity=0.15 from "issue" alone, landed in hard_safe,
# and the escalation language was never even looked at. The domain has no
# real cost asymmetry to exploit (unlike the scheduler, where the ambiguous
# band gated actual expensive computation) -- so ALL markers are scored
# together, always, and bands are read off the combined severity.
# ─────────────────────────────────────────────────────────────────────────────
REVIEW_GATE_HI = 0.65   # severity at/above this: certain issues, correct
REVIEW_GATE_LO = 0.15   # severity at/below this: certain clean, skip

_STRONG_ISSUE_MARKERS = ["wrong", "fails", "incorrect", "breaks", "bug", "broken", "crash"]
_WEAK_ISSUE_MARKERS = ["missing", "overclaim", "issue", "does not", "doesn't", "should"]
_UPGRADE_MARKERS = ["critical", "major", "security", "data loss", "regression", "breaks the build"]
_DOWNGRADE_MARKERS = ["minor", "nit", "nitpick", "trivial", "typo", "style", "cosmetic"]


def _review_severity(review_output: str) -> float:
    low = review_output.lower()
    score = 0.0
    for m in _STRONG_ISSUE_MARKERS:
        if m in low:
            score += 0.30
    for m in _WEAK_ISSUE_MARKERS:
        if m in low:
            score += 0.15
    for m in _UPGRADE_MARKERS:
        if m in low:
            score += 0.35
    for m in _DOWNGRADE_MARKERS:
        if m in low:
            score -= 0.20
    return max(0.0, min(1.0, score))


def gate_review(review_output: str) -> dict:
    """Classify a review into a trit band and a correct/skip decision.
    Returns {decision, band, severity} -- logged so the gate's real-world
    calibration can be checked later, the same honest-benchmark discipline
    used on the scheduler (see spiking_agent_pipeline.md)."""
    severity = _review_severity(review_output)
    if severity >= REVIEW_GATE_HI:
        return {"decision": True, "band": "hard_unsafe", "severity": severity}
    if severity <= REVIEW_GATE_LO:
        return {"decision": False, "band": "hard_safe", "severity": severity}
    return {"decision": severity >= 0.5, "band": "ambiguous", "severity": severity}


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC SPECIALISTS -- the self-growing-network capability wired into the
# real pipeline (see test_self_growing_network.py, spiking_agent_pipeline.md).
#
# Today's topology is FIXED at construction: seven specialists, decided in
# advance. But an agent can discover mid-task that it needs a sub-specialist
# nobody anticipated. If it says so in its output, the pipeline spawns one
# LIVE -- a real neuron, wired in and reviewed like any other -- instead of
# either ignoring the request or forcing everything through Implementer.
#
# Convention: an agent signals this by including a line
#   NEEDS_SPECIALIST: <Name>: <what it should do>
# in its output. Deliberately simple and grep-able rather than structured,
# so it's easy for a real Claude Code call to produce reliably.
#
# GROWTH IS CAPPED, explicitly -- same lesson as DRIVE_FLOOR in the earlier
# scheduler hang: a live-growing mechanism with no stop condition is a real
# runaway risk, not hypothetical. At most MAX_DYNAMIC_SPECIALISTS new
# neurons per pipeline run, and never the same name twice.
# ─────────────────────────────────────────────────────────────────────────────
SPAWN_SPECIALIST_RE = re.compile(r"NEEDS_SPECIALIST:\s*(\w+):\s*(.+)")
MAX_DYNAMIC_SPECIALISTS = 2


# ─────────────────────────────────────────────────────────────────────────────
# THE PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
class SpikingPipeline:
    def __init__(self, task: str, project: str = "spikeling", dry_run: bool = True,
                 review_finds_issues: bool = False, spawn_request: tuple = None):
        self.task = task
        self.project = project
        self.dry_run = dry_run
        self.review_finds_issues = review_finds_issues   # demo knob for the correct path
        # demo/test knob for dynamic specialists: (source_neuron, new_name, subtask) --
        # in dry_run mode, source_neuron's output includes the NEEDS_SPECIALIST marker
        # so the spawn mechanism is exercisable without a real agent call.
        self.spawn_request = spawn_request
        self.fired: list[str] = []          # order agents actually ran
        self.outputs: dict[str, str] = {}
        self._clock = 0.0                    # sim ms; advances per agent so re-fires clear refractory
        self._followups: list[tuple] = []    # result-driven stimulations to apply after the cascade
        self._corrections = 0
        self._review_gates: list[dict] = []  # every real gate_review() call, for calibration logging
        self._specialist_tasks: dict = {}    # dynamic specialists' subtask text, for _agent_task()
        self._dynamic_specialists: list[str] = []   # spawned this run, for the growth cap + logging

        self.rt = self._build_brain()

    def _build_brain(self):
        """Build the exact topology described in agent_brain.spk (see that
        file's comments for the design rationale), directly via pyspike
        instead of parsing it as text. Every neuron/weight/leak value here
        must match agent_brain.spk -- there's no automatic sync, see the
        module docstring above.

        Built LIVE (build_live(), not build()) so a specialist's handler can
        spawn a new specialist mid-run -- see _maybe_spawn_specialist() and
        the DYNAMIC SPECIALISTS section above. This changes nothing about the
        static topology itself (verified byte-identical to the batch-built
        version in test_pyspike_orchestrator_parity.py); it only makes growth
        possible after construction."""
        self._net = net = Net(refractory_ms=40)
        rt = net.build_live()

        # sensory layer (stimulated 0..100 by score_task)
        S_Work      = net.neuron("S_Work",      threshold=50, leak=1)
        S_Ambiguous = net.neuron("S_Ambiguous", threshold=50, leak=1)
        S_Complex   = net.neuron("S_Complex",   threshold=50, leak=1)
        S_Tests     = net.neuron("S_Tests",     threshold=50, leak=1)
        S_Research  = net.neuron("S_Research",  threshold=50, leak=1)   # currently unwired, same as the .spk

        # specialists -- one neuron per agent. self._specialists is kept
        # (not a local) because _maybe_spawn_specialist() adds to it later.
        self._specialists = {name: net.neuron(name, threshold=50, leak=2) for name in COMMANDS}
        specialists = self._specialists

        # flow (mirrors agent_brain.spk's "FLOW" section exactly)
        S_Work.to(specialists["Implementer"], weight=1.2)
        S_Ambiguous.to(specialists["Clarifier"], weight=1.2)
        S_Ambiguous.inhibits(specialists["Implementer"], weight=-2.0)
        S_Complex.to(specialists["PreRegister"], weight=1.2)
        S_Complex.to(specialists["Reviewer"], weight=0.7)
        S_Tests.to(specialists["TestWriter"], weight=1.2)
        specialists["Implementer"].to(specialists["Reviewer"], weight=1.2)
        specialists["TestWriter"].to(specialists["Reviewer"], weight=0.6)
        specialists["Corrector"].to(specialists["Reviewer"], weight=1.2)

        # handlers attach directly to their neuron -- no command-string
        # indirection needed with pyspike (the old .spk model required a
        # separate action->COMMAND->handler-dict chain; see COMMANDS below,
        # kept only for the agents_skipped enumeration, not for dispatch)
        for name in COMMANDS:
            net.action(specialists[name])(self._make_handler(name))

        return rt

    def _make_handler(self, neuron: str):
        def handler():
            self.fired.append(neuron)
            out = self._run_agent(neuron)
            self.outputs[neuron] = out
            self._maybe_spawn_specialist(neuron, out)
            # RESULT-DRIVEN ROUTING: review is the gate. Only a review that
            # reports issues wakes the Corrector, and only a couple of times.
            if neuron == "Reviewer" and self._review_reports_issues(out) and self._corrections < 2:
                self._corrections += 1
                self._followups.append(("Corrector", 60.0))
        return handler

    def _maybe_spawn_specialist(self, source_neuron: str, output: str) -> None:
        """If `output` asks for a specialist that doesn't exist yet, spawn one
        LIVE: a real neuron, wired into Reviewer (every dynamic specialist
        gets reviewed too, same as the fixed ones), with a real handler
        attached. Capped and deduped -- see the DYNAMIC SPECIALISTS module
        comment for why that's not optional.

        DELIBERATELY NOT wired with a static synapse FROM source_neuron.
        Two things were tried and rejected by this file's own test
        (test_dynamic_specialists.py) before landing here:
          - a direct source_neuron -> ref synapse fires ref in the SAME
            cascade instant as source_neuron (handlers run before
            propagation, propagation reads a live synapse list) -- but then
            ref -> Reviewer tries to fire Reviewer AT THAT SAME INSTANT,
            and Reviewer is still refractory-locked from firing moments
            earlier in the same cascade, so the review silently never
            happens (found: Reviewer only fired once when it should fire
            twice).
          - combining that synapse WITH a followup double-fires ref itself
            (found: DBMigrator fired twice).
        The working pattern is the SAME one already used for Corrector:
        whether to spawn depends on the agent's OUTPUT, so it's injected as
        a followup stimulation at an ADVANCED clock time, not a static
        synapse -- by the time it fires, Reviewer's refractory has cleared,
        so ref -> Reviewer (a static synapse, like Corrector -> Reviewer)
        correctly cascades into a real second review.

        Scans for ALL requests in the output, not just the first -- a single
        agent turn can legitimately need more than one (e.g. a task that
        touches both infra and security). Each is still subject to the
        per-name dedupe and the total growth cap; if an output lists more
        requests than the remaining cap allows, the earliest-listed ones win
        and the rest are silently dropped (capped, not queued -- consistent
        with "explicit stop condition, no exceptions" everywhere else this
        mechanism is documented)."""
        for m in SPAWN_SPECIALIST_RE.finditer(output or ""):
            name, subtask = m.group(1), m.group(2).strip()
            if name in self._specialists:
                continue   # dedupe -- never spawn the same name twice
            if len(self._dynamic_specialists) >= MAX_DYNAMIC_SPECIALISTS:
                break      # explicit growth cap -- see DRIVE_FLOOR lesson in the memory notes

            ref = self._net.neuron(name, threshold=50, leak=2)
            self._specialists[name] = ref
            self._specialist_tasks[name] = subtask
            self._dynamic_specialists.append(name)

            self._net.action(ref)(self._make_handler(name))
            ref.to(self._specialists["Reviewer"], weight=1.2)
            self._followups.append((name, 60.0))

    def _review_reports_issues(self, review_output: str) -> bool:
        if self.dry_run:
            return self.review_finds_issues and self._corrections < 1
        gate = gate_review(review_output)
        self._review_gates.append(gate)
        return gate["decision"]

    def _run_agent(self, neuron: str) -> str:
        """Fire the agent. dry_run just records intent (no tokens); real mode
        calls into voice_commands.do_claude_code with the right preamble/tools."""
        if self.dry_run:
            out = f"[dry-run] {neuron} would run on: {self.task[:60]}"
            if self.spawn_request and self.spawn_request[0] == neuron:
                _, name, subtask = self.spawn_request
                out += f"\nNEEDS_SPECIALIST: {name}: {subtask}"
            return out
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

    # Applies to EVERY working specialist -- Reviewer, PreRegister, Corrector,
    # and any dynamically-spawned specialist can equally discover a genuine
    # gap, not just Implementer. Excluded: VaultLogger (a summarization pass,
    # not work -- nothing for it to discover) and Clarifier (a stop-and-ask
    # gate, not real work either).
    _SPAWN_HINT = (
        "\n\nIf, while working, you discover this task genuinely needs a kind "
        "of specialist not implied above (e.g. a database migration, a "
        "security review, an API design pass) -- something a rename/"
        "implement/test/review cycle doesn't cover -- say so explicitly on "
        "its own line at the end of your output: "
        "NEEDS_SPECIALIST: <ShortName>: <what it should do>. You may list "
        "more than one line if genuinely more than one is needed. Only do "
        "this for genuinely distinct kinds of work, not routine sub-steps of "
        "what you're already doing."
    )
    _NO_SPAWN_HINT = {"VaultLogger", "Clarifier"}

    def _agent_task(self, neuron: str) -> str:
        # each specialist gets the task framed for its job
        if neuron in self._specialist_tasks:
            # a dynamically-spawned specialist gets the subtask IT was
            # requested to do, not the top-level task -- and, up to the
            # growth cap, can request one of its own the same way
            base = self._specialist_tasks[neuron]
            return base if neuron in self._NO_SPAWN_HINT else base + self._SPAWN_HINT

        frames = {
            "PreRegister": f"Before any edit, state ONE falsifiable claim about what this change will do: {self.task}",
            "Implementer": self.task,
            "TestWriter":  f"Add or adjust tests for: {self.task}",
            "Reviewer":    f"Peer-review the change for: {self.task}. Read-only. Call out overclaiming.",
            "Corrector":   f"Fix exactly what review flagged for: {self.task}",
            "VaultLogger": self._vault_logger_task(),
        }
        base = frames.get(neuron, self.task)
        return base if neuron in self._NO_SPAWN_HINT else base + self._SPAWN_HINT

    def _vault_logger_task(self) -> str:
        note = ""
        if self._dynamic_specialists:
            note = (f" This run dynamically spawned {len(self._dynamic_specialists)} "
                    f"unanticipated specialist(s) mid-task: "
                    f"{', '.join(self._dynamic_specialists)} -- mention what each was "
                    f"for and whether it turned out to be genuinely needed.")
        return f"Write an honest ledger entry for the work on: {self.task}.{note}"

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
            "review_gates": self._review_gates,   # calibration data for the ternary review gate
            "dynamic_specialists": self._dynamic_specialists,   # live-spawned specialists this run
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
