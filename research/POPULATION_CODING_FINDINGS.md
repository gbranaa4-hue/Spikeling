# Population coding: the consensus-gate scoping rule bridges to neuroscience + robust statistics

`population_coding_test.py` — a third test of the scoping rule found in
`012-ternary/paper/{npc_consensus_findings.md, order_acceptance_findings.md}`
("weighted combination wins under calibrated evidence; discretized voting
wins under uncalibrated/contaminated evidence"), this time checked against
two independent, externally-published results rather than re-derived
internally: population-coding theory (optimal Bayesian/weighted-linear
decoding beats voting under known, Gaussian neuron reliability) and
robust statistics (vote/median estimators resist outlier contamination
better than weighted means when the noise model is unknown at decode
time).

## Setup

15 LIF neurons (Spikeling's own leak/threshold/refractory dynamics, not a
toy abstraction — same equations as `spikeling.gd`), each encoding a
binary stimulus via spike count over a 200-tick window, with its own
tuning strength and per-tick noise level. A decoder is **calibrated once**
on clean trials (estimating each neuron's mean response under s=0/s=1,
inverse-variance weights, and per-neuron vote direction), then deployed
blind to two test regimes:

- **Regime A (clean):** same noise model as calibration.
- **Regime B (contaminated):** 10% of neurons per trial get an extra,
  unmodeled outlier drive (an erratic/unreliable spike burst) — neither
  decoder is told this is happening or which neurons are affected.

**Decoder 1 (weighted-linear):** inverse-variance-weighted sum of each
neuron's response relative to its calibrated midpoint.
**Decoder 2 (majority-vote):** each neuron casts its own vote via its
calibrated midpoint; majority sign wins.

Prediction, stated before tuning the task difficulty or running final
numbers: weighted-linear wins regime A, majority-vote wins or closes the
gap in regime B.

(Note on process: the first run hit a ceiling — both decoders scored
100% in regime A because the task was too easy to show any gap. Tuning
strength was reduced and noise increased to put regime A in an
informative range before re-running. This is recorded honestly because
it's a real methodological step, not because it changes the conclusion —
the *contamination* result was already clear and unaffected before this
adjustment; only the *clean-regime* comparison needed it.)

## Result — both predictions confirmed

| Regime | Weighted-linear | Majority-vote | Gap (vote − weighted) |
|---|---|---|---|
| A (clean) | **0.9995 ± 0.0006** | 0.9958 ± 0.0030 | -0.0037 |
| B (contaminated, 10%) | 0.6101 ± 0.0065 | **0.9838 ± 0.0104** | **+0.3737** |

Regime A: t=-6.40 across 25 seeds — weighted-linear wins, real but
**small in magnitude** (0.37pp). Regime B: t=223.87 — majority-vote wins
**decisively** (+37.4pp), one of the largest, cleanest effects in this
whole research line.

## Honest read of the asymmetry

The two wins are not the same size, and that's worth stating plainly
rather than smoothing over: weighted-linear's edge under clean conditions
is statistically real (huge t-value from low seed-to-seed variance) but
*practically tiny* (both decoders are near-ceiling already). Majority
vote's edge under contamination is both statistically overwhelming and
*practically enormous* — the weighted decoder's accuracy collapses to
61% (barely better than chance) once 10% of neurons go rogue, because a
single large outlier can swamp an inverse-variance-weighted sum, while
the vote only needs a simple majority of (mostly still-reliable)
individual neuron judgments to survive the same contamination. This
matches the textbook reason robust estimators exist: weighted means are
not robust to even modest contamination, by construction.

## What this confirms

The scoping rule isolated from two unrelated game-logic tests
(`npc_consensus_findings.md`'s OR-gate win, `order_acceptance_findings.md`'s
threshold loss) is not a coincidence specific to game decision logic — it
reproduces, using the project's own LIF neuron model, the same boundary
condition that two independent, already-published fields (population
coding theory and robust statistics) predict separately. That's a
stronger form of validation than another internal replication would have
been: an external, falsifiable cross-check this project didn't define the
terms of in advance.

## Honest scope and caveats

- This uses a synthetic LIF population with hand-set tuning/noise
  parameters, not data from real biological neurons or a real
  contamination process — it tests whether the *mechanism* (calibrated
  vs. uncalibrated noise) produces the predicted boundary, not whether
  real cortex actually behaves this way.
- The contamination model (random per-neuron, per-trial additive outlier)
  is one specific, simple corruption model. Real "unreliable" neural
  responses might be structured differently (correlated across neurons,
  state-dependent, etc.) — a fair follow-up would test other
  contamination shapes before generalizing further.
- The regime-A win, while statistically real, is small enough that in
  practice (outside a 25-seed averaged comparison) the two decoders would
  often look indistinguishable under clean conditions — the real,
  decision-relevant asymmetry is regime B's contamination robustness, not
  regime A's small edge.
