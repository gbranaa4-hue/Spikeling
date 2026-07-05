# Coupled-bank symmetry test — the acoustic dichotomy REPLICATES

**Script:** `coupled_symmetry_test.py` · **Seeds:** 20 (paired) · **Date:** 2026-07-05

## What this is

The "fairer follow-up" that `SYMMETRY_TEST_FINDINGS.md` identified but did
not run. The first resonator-bank test came back negative on the
acoustic-plate quadratic symmetry-selection rule, and its own diagnosis
said why: the bank had a single shared input line, all-positive input
couplings, no inter-unit coupling, single-step integration, and a
position-only readout — so even-order tasks were at R² ≈ 0 for *both*
configs, and there was no capability for symmetry-breaking to unlock. The
acoustic study's rung-1 discipline says the capability bar must be
cleared *first*.

This version gives the same Spikeling resonator bank the richness the
acoustic reservoir had (all changes taken from
`quasicrystal-mems-reservoir/reservoir_computing/reservoir_rung1.py` and
fixed before any symmetry comparison was generated): sparse diffusive
inter-unit coupling, sign-diverse input injection, 50 symplectic-Euler
sub-steps per input symbol, an [x, v, bias] readout, and cubic hardening
for stability instead of a hard clip. The manipulated mechanism is
unchanged: per-unit quadratic self-term `c2·x²`, dead in 88% of units
(symmetric/periodic-plate analog) vs 38% (broken/quasicrystal analog).

## Design — gated and paired

**Rung 1 (capability gate, run before rung 2 existed):** the all-alive
bank (dead=0) had to reach R² ≥ 0.5 on `u[n-1]·u[n-2]` while the
quadratic-free control stayed below 0.1. Two disclosed gate-stage tunes
were needed (drive amplitude 1.5→2.5; cubic hardening 1.0→0.4 — the
nonlinearity was under-engaged at mean |x| ≈ 0.2, the same failure mode
the acoustic study disclosed and fixed at its own rung 1). Gate passed:
**all-alive R² = 0.527, control R² = −0.051.** The quadratic term, not
the readout or the cubic, makes the products. Parameters then froze.

**Rung 2 (paired):** per seed, ONE bank is drawn and only the dead mask
differs (21/24 vs 9/24 dead, alive sets nested). Paired t across 20
seeds. Predictions pre-registered in the script header before the first
run: P2 — even-order gap positive, paired t > 2; P3 — odd-order tasks
approximately tied (not the uncoupled test's −0.09 damage).

## Result — clean replication of the acoustic even/odd dichotomy

| Task | Order | Symmetric R² (88% dead) | Broken R² (38% dead) | Gap | paired t |
|---|---|---|---|---|---|
| u[n-1]·u[n-2] | even | 0.309 ± 0.110 | 0.556 ± 0.048 | **+0.246** | **+9.49** |
| u[n-1]·u[n-3] | even | 0.258 ± 0.120 | 0.436 ± 0.047 | **+0.178** | **+6.55** |
| u[n-1]² | even | 0.315 ± 0.180 | 0.653 ± 0.109 | **+0.339** | **+8.85** |
| u[n-1] | odd | 0.998 ± 0.001 | 0.997 ± 0.002 | −0.001 | −6.47 |
| u[n-1]³ | odd | 0.865 ± 0.013 | 0.858 ± 0.011 | −0.007 | −4.58 |
| u[n-1]−0.5·u[n-2] | odd | 1.000 ± 0.000 | 0.999 ± 0.000 | −0.000 | −4.69 |

Mean even-order gap: **+0.254** (acoustic reference: +0.150; uncoupled
first test: +0.007). Mean odd-order gap: **−0.003** (acoustic reference:
−0.002; uncoupled first test: −0.090).

Both pre-registered predictions held. Every even-order task improves
substantially and significantly under broken symmetry; every odd-order
task is at ceiling-or-near for both configs with differences of a few
*thousandths* of R² — statistically detectable under pairing (the odd
paired t's are negative but the effects are −0.001 to −0.007, i.e.
practically nil, exactly the acoustic plate's "odd ties" signature and
nothing like the −0.09 real damage the uncoupled bank showed).

## What this means

1. **The selection-rule effect is now a two-substrate result.** The same
   mechanism — more units with a live quadratic self-term — produces the
   same even-order-only computational advantage on an FEM acoustic plate
   *and* on a software resonator bank, once the bank has a genuine
   coupling network and adequately engaged nonlinearity.
2. **The capability-bar hypothesis from the cross-substrate synthesis is
   confirmed, not just post-hoc.** The uncoupled bank failed with
   even-order R² at floor; the *only* changes made here were richness/
   integration fixes chosen before any symmetry comparison, and the
   effect appeared at full strength (+0.25, larger than the acoustic
   +0.15). Symmetry-breaking is a second-order lever that pays off
   exactly when the substrate already clears the capability bar — as
   predicted in `cross_substrate_symmetry_findings.md`.
3. **The odd-order damage in the uncoupled test was a poverty artifact.**
   With a real coupling network, giving 12 more units a quadratic term
   costs essentially nothing on linear-memory tasks (−0.003), instead of
   −0.09.

## Honesty notes

- Predictions P1–P3 were written in the script header before the first
  rung-2 run and not edited after. Rung 2 was run once.
- Gate-stage tuning (2 iterations) is disclosed in the script and above;
  it optimized only the all-alive capability run and never saw a
  symmetric-vs-broken number. Parameters froze at gate pass.
- The paired design (same bank, nested alive sets, only the dead mask
  differs) is stricter than the first test's independent banks and is a
  disclosed change; it is why tiny odd-order differences reach
  |t| ≈ 5–6 while remaining practically negligible.
- This is still simulation, still a hand-set `c2` rather than one derived
  from any spatial mode-shape integral. It demonstrates mechanism
  generality across substrates, not anything about fabricated hardware.
- The uncoupled negative result stands as recorded — it correctly
  measured that the bare oscillator equation without spatial richness
  cannot express the effect. This test does not overturn it; it completes
  it.

## Cross-reference

- First (negative) test: `SYMMETRY_TEST_FINDINGS.md`
- Acoustic original: `quasicrystal-mems-reservoir/reservoir_computing/`
  (rungs 1, 5c, 6)
- Cross-substrate synthesis this result updates:
  `012-ternary/paper/cross_substrate_symmetry_findings.md`
