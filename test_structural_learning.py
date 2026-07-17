#!/usr/bin/env python
"""
test_structural_learning.py — verifies the pipeline's structural-learning
capability: a dynamically-spawned specialist with a consistent real track
record of being judged useful gets PROMOTED into the fixed topology for
future SpikingPipeline instances, without needing to be rediscovered live
each time.

Isolated from the real specialist_history.json via monkeypatching --
these tests must NEVER touch the real file (it's real accumulated usage
history, gitignored on purpose).

Six checks:
  1. VERDICT PARSING       -- VaultLogger's VERDICT lines correctly update
                               the persisted history.
  2. PROMOTION THRESHOLD    -- fewer than PROMOTION_THRESHOLD useful verdicts
                               does NOT promote.
  3. PROMOTION FIRES        -- >=PROMOTION_THRESHOLD useful verdicts, zero
                               unnecessary, DOES promote.
  4. ONE BAD VERDICT BLOCKS -- a single "unnecessary" verdict, ever, blocks
                               promotion regardless of how many useful ones
                               came before or after (strict, one-sided).
  5. PROMOTED IS BUILT IN   -- a NEW pipeline instance, built AFTER
                               promotion, has the name in its topology from
                               construction -- no spawn needed.
  6. NO VERDICT IS NEUTRAL  -- a spawn with no verdict given doesn't count
                               toward promotion OR block it.

    python test_structural_learning.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spiking_orchestrator as so   # noqa: E402


def _isolated_history_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_specialist_history_")
    os.close(fd)
    os.remove(path)   # start with no file, same as a fresh install
    return path


def _run_and_verdict(name: str, verdict: str, history_path: str) -> None:
    """Simulate one full run that spawns `name` and gets judged `verdict`."""
    so.SPECIALIST_HISTORY = history_path
    p = so.SpikingPipeline(
        "rename x to y", dry_run=True,
        spawn_request=("Implementer", name, f"do the {name} work"),
        verdicts={name: verdict},
    )
    p.run()


def check_1_verdict_parsing() -> bool:
    history_path = _isolated_history_path()
    _run_and_verdict("DBMigrator", "useful", history_path)
    history = so.load_specialist_history()
    rec = history.get("DBMigrator", {})
    ok = rec.get("spawned") == 1 and rec.get("judged_useful") == 1 and rec.get("unnecessary", 0) == 0
    print(f"  [{'PASS' if ok else 'FAIL'}] 1. verdict parsing: DBMigrator record={rec}")
    return ok


def check_2_below_threshold_no_promotion() -> bool:
    history_path = _isolated_history_path()
    for _ in range(so.PROMOTION_THRESHOLD - 1):
        _run_and_verdict("Almost", "useful", history_path)
    promoted = so.promoted_specialists()
    ok = "Almost" not in promoted
    print(f"  [{'PASS' if ok else 'FAIL'}] 2. below threshold ({so.PROMOTION_THRESHOLD - 1} useful) "
          f"does NOT promote: promoted={promoted}")
    return ok


def check_3_promotion_fires() -> bool:
    history_path = _isolated_history_path()
    for _ in range(so.PROMOTION_THRESHOLD):
        _run_and_verdict("Reliable", "useful", history_path)
    promoted = so.promoted_specialists()
    ok = "Reliable" in promoted
    print(f"  [{'PASS' if ok else 'FAIL'}] 3. {so.PROMOTION_THRESHOLD} useful verdicts DOES promote: "
          f"promoted={promoted}")
    return ok


def check_4_one_bad_verdict_blocks() -> bool:
    # the bad verdict must land BEFORE promotion ever fires -- once promoted,
    # a name becomes part of the fixed roster and a fresh spawn_request for
    # it is correctly deduped (it already exists), so it stops accumulating
    # NEW evidence via this path. That's a real, separate limitation (no
    # demotion path once promoted -- noted in STRUCTURAL LEARNING follow-
    # ups) and not what this check is testing: this checks that one early
    # 'unnecessary' verdict permanently blocks promotion even after many
    # useful verdicts arrive afterward.
    history_path = _isolated_history_path()
    _run_and_verdict("Flaky", "unnecessary", history_path)
    for _ in range(so.PROMOTION_THRESHOLD + 2):
        _run_and_verdict("Flaky", "useful", history_path)
    promoted = so.promoted_specialists()
    ok = "Flaky" not in promoted
    print(f"  [{'PASS' if ok else 'FAIL'}] 4. one early 'unnecessary' verdict blocks promotion even "
          f"after {so.PROMOTION_THRESHOLD + 2} useful ones afterward: promoted={promoted}")
    return ok


def check_5_promoted_is_built_in() -> bool:
    history_path = _isolated_history_path()
    for _ in range(so.PROMOTION_THRESHOLD):
        _run_and_verdict("GraphQLExpert", "useful", history_path)
    # a FRESH pipeline, no spawn_request at all -- GraphQLExpert should
    # already exist in its topology from construction
    so.SPECIALIST_HISTORY = history_path
    p = so.SpikingPipeline("some other task entirely", dry_run=True)
    ok = "GraphQLExpert" in p._specialists and "GraphQLExpert" in p._base_specialist_names
    print(f"  [{'PASS' if ok else 'FAIL'}] 5. promoted specialist is built into a NEW pipeline "
          f"without a spawn: in _specialists={('GraphQLExpert' in p._specialists)}")
    return ok


def check_6_no_verdict_is_neutral() -> bool:
    history_path = _isolated_history_path()
    so.SPECIALIST_HISTORY = history_path
    # spawn WITHOUT providing a verdict for it
    p = so.SpikingPipeline(
        "rename x to y", dry_run=True,
        spawn_request=("Implementer", "Ambiguous", "do ambiguous work"),
        verdicts={},   # no verdict given at all
    )
    p.run()
    history = so.load_specialist_history()
    rec = history.get("Ambiguous", {})
    ok = rec.get("spawned") == 1 and rec.get("judged_useful", 0) == 0 and rec.get("unnecessary", 0) == 0
    print(f"  [{'PASS' if ok else 'FAIL'}] 6. no verdict given is evidence-neutral: record={rec}")
    return ok


def run() -> None:
    print("=" * 74)
    print("  STRUCTURAL LEARNING -- promotion of proven dynamic specialists")
    print("=" * 74)
    original_path = so.SPECIALIST_HISTORY
    try:
        results = [
            check_1_verdict_parsing(),
            check_2_below_threshold_no_promotion(),
            check_3_promotion_fires(),
            check_4_one_bad_verdict_blocks(),
            check_5_promoted_is_built_in(),
            check_6_no_verdict_is_neutral(),
        ]
    finally:
        so.SPECIALIST_HISTORY = original_path   # never leave the real path swapped out

    print()
    if all(results):
        print(f"  ALL {len(results)} CHECKS PASS: the pipeline's base topology genuinely "
              f"learns from real usage history, not just per-run improvisation.")
    else:
        print(f"  {results.count(False)}/{len(results)} CHECKS FAILED -- do not trust "
              f"structural learning until resolved.")


if __name__ == "__main__":
    run()
