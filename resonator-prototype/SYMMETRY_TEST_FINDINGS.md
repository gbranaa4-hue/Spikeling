# Symmetry selection-rule generality test — result: does NOT replicate

Ran `symmetry_selection_test.py`: a bank of 24 Resonator units, each given
a per-unit quadratic self-nonlinearity term (`c2 * x^2`) with a controlled
fraction "dead" (c2=0), matching the acoustic MEMS plate's measured dead
fractions exactly (88% for the symmetric/periodic-mirroring config, 38%
for the broken-symmetry/quasicrystal-mirroring config). 20 seeds per
config, 3000-step input sequences, ridge-regression readout, even-order
tasks (`u[n-1]*u[n-2]`, `u[n-1]*u[n-3]`, `u[n-1]^2`) vs odd-order control
tasks (`u[n-1]`, `u[n-1]^3`, `u[n-1]-0.5*u[n-2]`).

## Result

| Task | Order | Symmetric R² | Broken R² | Gap |
|---|---|---|---|---|
| u[n-1]*u[n-2] | even | -0.013 ± 0.010 | -0.007 ± 0.006 | +0.006 |
| u[n-1]*u[n-3] | even | -0.017 ± 0.009 | -0.010 ± 0.006 | +0.007 |
| u[n-1]^2 | even | -0.014 ± 0.012 | -0.007 ± 0.007 | +0.007 |
| u[n-1] | odd | 0.303 ± 0.036 | 0.182 ± 0.059 | **-0.121** |
| u[n-1]^3 | odd | 0.249 ± 0.031 | 0.147 ± 0.048 | **-0.102** |
| u[n-1]-0.5·u[n-2] | odd | 0.075 ± 0.017 | 0.030 ± 0.013 | -0.045 |

Mean gap: even = **+0.0066** (acoustic plate reference: +0.150), odd =
**-0.0895** (acoustic plate reference: -0.002).

**This does not replicate the acoustic plate's even/odd dichotomy.** Two
things went wrong relative to the prediction:

1. **Even-order tasks are at floor for both configs.** R² is ~0 (slightly
   negative — worse than predicting the mean) regardless of symmetry. The
   reservoir cannot do the product task *at all* here, so there is no
   capability for symmetry-breaking to unlock — the predicted mechanism
   needs a reservoir that's at least borderline-capable of the task before
   "more c2-alive units" can help it, and this one isn't.
2. **Odd-order tasks, where the reservoir does show real memory (R²
   0.03-0.30), get *worse* under the broken-symmetry config** — the
   opposite of the acoustic plate's clean "odd ties" result. Breaking
   symmetry here costs basic linear memory capacity instead of leaving it
   untouched.

## Why, honestly

The acoustic plate's reservoir wasn't just "oscillators with a quadratic
self-term" — its rung-1 baseline (generic Duffing oscillators, no
selection-rule mechanism at all) already solved the same product task at
R²=0.71, because the plate's reservoir had **spatial diversity**: multiple
physical drive locations exciting the same mode network differently,
giving the readout many distinct nonlinear combinations to work from. This
resonator bank has a **single shared scalar input line** (`coupling_i · u[n]`)
driving every unit from the same source, with no inter-unit coupling
network at all — diversity here comes only from each unit's own
frequency/damping, which is a much weaker source of representational
richness. Adding a large fraction of unstable-feeling quadratic
self-terms (the broken-symmetry config) on top of that thin baseline
apparently degrades the modest linear memory that was there, rather than
adding a new capability on top of a working baseline.

**Conclusion: this is a real, recorded negative result, not a refutation
of the acoustic finding.** The acoustic plate's selection rule was never
claimed to be substrate-independent magic — it's a specific consequence of
modes living on a 2D plate with point-group symmetry and a rich spatial
coupling/drive structure. This experiment shows that *just the bare
oscillator equation plus a per-unit quadratic term*, without that spatial
richness, is not sufficient to reproduce the effect. No parameter-tuning
was done after seeing this result (no fishing for a positive number) — the
result is reported as run.

## What would be needed to test this more fairly

Per the acoustic plate's own rung-1 finding, an even-order task needs a
reservoir that's *already* reasonably capable before symmetry-breaking can
help it. A fairer follow-up would give the resonator bank either (a)
multiple independent input channels (mimicking multiple drive locations),
or (b) genuine inter-unit coupling (mimicking the plate's elastic coupling
network) — and confirm the *baseline* (symmetric, no c2 at all) can
already do the even task at R² roughly comparable to the acoustic
baseline before re-testing whether symmetry-breaking adds anything on top.
That's a different, larger experiment, not run here.

## Cross-reference

See `../../012-ternary/paper/cross_substrate_symmetry_findings.md` for the
full three(+one)-substrate comparison this result has been folded into.
