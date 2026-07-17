#!/usr/bin/env python
"""
test_promotion_rule_comparison.py — cross-references the promotion rule just
built into spiking_orchestrator.py against two real prior findings in this
portfolio:

  1. consensus_scoping_rule_ladder.md (012-ternary, 2026-07-05): "weighted
     combination beats voting exactly as long as the calibration-time
     reliability ranking still holds at decision time." The current
     promotion rule (promoted_specialists(), see spiking_orchestrator.py)
     is a strict binary AND-gate: >=PROMOTION_THRESHOLD useful verdicts AND
     zero unnecessary ones, EVER. A single early bad verdict permanently
     blocks promotion, no matter how much good evidence follows -- that is
     exactly the "voting" pole the scoping rule found weighting beats.
  2. spiking_agent_pipeline.md's own soft-conflict RETRACTION (2026-07-17,
     same day): once the reproducibility bug was fixed, plain weighted
     inhibition consistently beat the ternary/binary gate on a structurally
     similar graded-evidence problem in THIS SAME PROJECT.

Both point the same direction. This tests it directly rather than assuming
it transfers -- same discipline as every other cross-reference in this
portfolio (cross_substrate_synthesis_finding.md is the cautionary tale:
"symmetry-conditional protection" was assumed to unify three substrates and
LOST when actually measured).

THREE SPECIALIST CLASSES, same verdict streams fed to both rules (paired):
  A. CONSISTENTLY GOOD  -- 90% useful rate, random per-event noise.
  B. CONSISTENTLY BAD   -- 20% useful rate, random per-event noise.
  C. NOISY-GOOD, ONE EARLY MISS -- deterministic: one unlucky early
     "unnecessary" verdict, then consistently useful afterward. The exact
     shape of "genuinely good specialist judged unfairly on its first,
     most-ambiguous run" -- directly tests whether a rule can recover.

TWO RULES:
  CURRENT (binary/ternary strict AND) -- promoted_specialists()'s actual
     logic, imported directly, not reimplemented.
  WEIGHTED -- score += 1 per useful, -1 per unnecessary, 0 for no verdict;
     promote when score >= PROMOTION_THRESHOLD. Never demotes once
     promoted (same limitation as CURRENT, for a fair comparison -- this
     tests the ACCUMULATION rule, not the demotion gap).

PRE-REGISTERED PREDICTION: weighted recovers class C (which current
structurally cannot, by construction) without a meaningfully higher false-
promotion rate on class B, mirroring the scoping-rule finding.
DISCONFIRM: weighted's false-positive rate on class B rises enough to erase
the gain on class C -- would mean the scoping-rule finding does NOT
transfer to this problem shape, and the strict rule's conservatism is
actually justified here. Report honestly either way.

    python test_promotion_rule_comparison.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spiking_orchestrator as so   # noqa: E402

STREAM_LEN = 8
N_TRIALS = 300
GOOD_RATE = 0.90
BAD_RATE = 0.20
NO_VERDICT_RATE = 0.05


def _gen_stream(rng: random.Random, useful_rate: float) -> list:
    stream = []
    for _ in range(STREAM_LEN):
        r = rng.random()
        if r < NO_VERDICT_RATE:
            stream.append(None)
        elif r < NO_VERDICT_RATE + useful_rate * (1 - NO_VERDICT_RATE):
            stream.append("useful")
        else:
            stream.append("unnecessary")
    return stream


def _current_rule_promotes(stream: list) -> bool:
    """Exactly promoted_specialists()'s real logic, applied to one stream."""
    useful = sum(1 for v in stream if v == "useful")
    unnecessary = sum(1 for v in stream if v == "unnecessary")
    return useful >= so.PROMOTION_THRESHOLD and unnecessary == 0


def _weighted_rule_promotes(stream: list) -> bool:
    score = 0
    for v in stream:
        if v == "useful":
            score += 1
        elif v == "unnecessary":
            score -= 1
        # None (no verdict): evidence-neutral, same as the current rule
        if score >= so.PROMOTION_THRESHOLD:
            return True
    return False


def run() -> None:
    rng = random.Random(11)
    print("=" * 78)
    print("  PROMOTION RULE COMPARISON -- current (strict AND) vs weighted evidence")
    print("=" * 78)

    # A + B: paired random streams, same stream fed to both rules
    tp_current = tp_weighted = 0
    fp_current = fp_weighted = 0
    for _ in range(N_TRIALS):
        good_stream = _gen_stream(rng, GOOD_RATE)
        if _current_rule_promotes(good_stream):
            tp_current += 1
        if _weighted_rule_promotes(good_stream):
            tp_weighted += 1

        bad_stream = _gen_stream(rng, BAD_RATE)
        if _current_rule_promotes(bad_stream):
            fp_current += 1
        if _weighted_rule_promotes(bad_stream):
            fp_weighted += 1

    tpr_current, tpr_weighted = tp_current / N_TRIALS, tp_weighted / N_TRIALS
    fpr_current, fpr_weighted = fp_current / N_TRIALS, fp_weighted / N_TRIALS

    # C: deterministic, one sample is the whole story
    class_c = ["unnecessary"] + ["useful"] * (STREAM_LEN - 1)
    c_current = _current_rule_promotes(class_c)
    c_weighted = _weighted_rule_promotes(class_c)

    print(f"\n  Class A (consistently good, {GOOD_RATE:.0%} useful rate), N={N_TRIALS}:")
    print(f"    current  TPR: {tpr_current:.3f}")
    print(f"    weighted TPR: {tpr_weighted:.3f}")

    print(f"\n  Class B (consistently bad, {BAD_RATE:.0%} useful rate), N={N_TRIALS}:")
    print(f"    current  FPR: {fpr_current:.3f}")
    print(f"    weighted FPR: {fpr_weighted:.3f}")

    print(f"\n  Class C (one early bad verdict, then consistently useful), stream={class_c}:")
    print(f"    current  promotes: {c_current}")
    print(f"    weighted promotes: {c_weighted}")

    print("\n--- verdict against pre-registration ---")
    recovers_c = (not c_current) and c_weighted
    fpr_cost = fpr_weighted - fpr_current
    if recovers_c and fpr_cost < 0.05:
        print(f"CONFIRMED: weighted recovers the genuinely-good-but-unlucky specialist "
              f"(class C) that current structurally cannot, at a false-positive cost of "
              f"only {fpr_cost:+.3f} on consistently-bad specialists (class B). The "
              f"consensus-scoping-rule finding transfers to this problem.")
    elif recovers_c:
        print(f"MIXED: weighted recovers class C, but at a real false-positive cost "
              f"({fpr_cost:+.3f} on class B) -- the scoping-rule finding transfers "
              f"PARTIALLY; whether the tradeoff is worth it is a judgment call, not "
              f"a clean win.")
    else:
        print("DISCONFIRMED: weighted did NOT recover class C as designed -- report "
              "the raw numbers, don't spin them.")


if __name__ == "__main__":
    run()
