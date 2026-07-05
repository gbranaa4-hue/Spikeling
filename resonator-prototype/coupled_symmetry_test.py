#!/usr/bin/env python3
"""
The "fairer follow-up" that SYMMETRY_TEST_FINDINGS.md identified but did
not run: re-test the acoustic-plate quadratic symmetry-selection rule on
a Spikeling resonator bank that actually clears the capability bar first.

WHY THE FIRST TEST FAILED (per its own honest diagnosis): the original
bank (symmetry_selection_test.py) had a single shared scalar input line,
all-positive input couplings, no inter-unit coupling at all, single-step
Euler updates, and a position-only readout. Even-order tasks were at
R^2 ~ 0 for BOTH configs -- there was no capability for symmetry-breaking
to unlock. The acoustic study's own rung-1 control established that the
even-order effect needs a reservoir that is already capable (its generic
Duffing baseline hit R^2=0.71 on the product task) before the selection
rule can matter.

WHAT THIS VERSION CHANGES (all taken from the acoustic study's rung-1
reservoir, reservoir_rung1.py in quasicrystal-mems-reservoir, translated
onto the Spikeling bank; every change is a richness/integration fix
decided BEFORE any symmetric-vs-broken comparison is looked at):
  - genuine inter-unit coupling: sparse (~20%) random diffusive coupling
    sum_j C_ij (x_j - x_i), the software analog of the plate's elastic
    mode-coupling network;
  - sign-diverse input injection w_in in [-1, 1] (the old test's
    all-positive couplings, uniform [0.5, 1.5], gave the readout far less
    to separate);
  - proper sub-stepped integration (input held for TAU_IN, integrated at
    DT with TAU_IN/DT symplectic-Euler sub-steps), instead of dt=1 single
    steps;
  - readout on [x, v, bias], not x alone;
  - cubic hardening -beta3*x^3 on every unit for stability (generic, not
    the manipulated mechanism), instead of a hard clip doing the bounding;
  - drive amplitude strong enough to engage the nonlinearity (mean |x|
    ~ O(1)), which the acoustic study itself had to retune for (disclosed
    there, disclosed here).

The manipulated mechanism is unchanged from the first test: a per-unit
quadratic self-term c2_i * x_i^2, alive in a controlled fraction of units,
dead fractions matching the acoustic plate's measured values
(symmetric/periodic: 88% dead; broken/quasicrystal: 38% dead).

DESIGN -- two rungs, gated:

RUNG 1 (capability gate, run and passed BEFORE rung 2 is ever computed):
  the ALL-ALIVE bank (dead_frac=0) must reach R^2 >= 0.5 on the product
  task u[n-1]*u[n-2] (order of the acoustic baseline's 0.71), AND the
  quadratic-free control (c2=0 everywhere, cubic still on) must fail it
  (R^2 < 0.1) -- proving the quadratic term, not the readout or the cubic,
  makes the products. If the gate fails, the experiment stops and the
  negative is reported; no rung-2 numbers are generated or seen.
  Gate-stage parameter tuning (drive amplitude, coupling scale, c2
  magnitude) is permitted and disclosed, because it never sees a
  symmetric-vs-broken comparison; once the gate passes, all parameters
  freeze.

RUNG 2 (the symmetry test, paired): 20 seeds. Per seed, ONE bank is drawn
  (frequencies, damping, coupling matrix, input weights, c2 magnitudes)
  and only the dead MASK differs between configs: exactly
  round(0.88*N)=21 dead units (symmetric) vs round(0.38*N)=9 dead
  (broken), with the alive sets nested (symmetric's 3 alive units are the
  first 3 of the same per-seed permutation whose first 15 are alive under
  broken). Paired t across seeds per task. This is stricter than the
  first test's fully independent banks and is disclosed as a change.

PREDICTIONS, pre-registered before the first rung-2 run and not edited:
  P1. Gate passes (else stop and report).
  P2. Even-order tasks: broken (38% dead) beats symmetric (88% dead),
      mean gap positive with paired t > 2 (acoustic reference: +0.150).
  P3. Odd-order tasks: approximately tied (acoustic reference: -0.002) --
      in particular NOT the -0.09 odd-order damage the uncoupled test
      showed; with a real coupling network, symmetry-breaking should not
      cost linear memory.

Run it:
    python coupled_symmetry_test.py --gate    # rung 1 only
    python coupled_symmetry_test.py           # rung 1, then rung 2 if gate passes
"""

import sys
import numpy as np

N_UNITS = 24
N_SEEDS = 20
T_STEPS = 3000
WASHOUT = 200
TRAIN_FRAC = 0.7
RIDGE_LAMBDA = 1e-3

TAU_IN = 1.0
DT = 0.02
N_SUB = int(round(TAU_IN / DT))
INPUT_AMP = 2.5   # gate-tune 1: was 1.5 -> mean|x|=0.21 under-engaged, R^2=0.473 just under bar
BETA3 = 0.4                # cubic hardening, all units, not manipulated
                           # gate-tune 2: was 1.0 -> amplitude capped at 0.31, R^2=0.488
C2_LO, C2_HI = 0.3, 0.9    # |c2| range for alive units (acoustic used 0.6)
COUPLING_SCALE = 0.08      # diffusive coupling strength (acoustic value)
CONNECTIVITY = 0.2

DEAD_SYMMETRIC = round(0.88 * N_UNITS)   # 21 of 24 dead (periodic D4 plate)
DEAD_BROKEN = round(0.38 * N_UNITS)      # 9 of 24 dead (quasicrystal)

GATE_R2_MIN = 0.5          # all-alive bank must clear this on the product task
GATE_CONTROL_MAX = 0.1     # quadratic-free control must stay below this


def build_bank(rng):
    omega = rng.uniform(0.5, 2.5, N_UNITS)
    zeta = rng.uniform(0.1, 0.3, N_UNITS)
    w_in = rng.uniform(-1.0, 1.0, N_UNITS)
    C = rng.uniform(-1.0, 1.0, (N_UNITS, N_UNITS))
    C *= rng.random((N_UNITS, N_UNITS)) < CONNECTIVITY
    np.fill_diagonal(C, 0.0)
    C *= COUPLING_SCALE
    c2_mag = rng.uniform(C2_LO, C2_HI, N_UNITS) * rng.choice([-1.0, 1.0], N_UNITS)
    perm = rng.permutation(N_UNITS)   # shared alive-ordering for nested masks
    return dict(omega=omega, zeta=zeta, w_in=w_in, C=C, c2_mag=c2_mag, perm=perm)


def c2_with_dead(bank, n_dead):
    """Alive sets are nested: the first (N_UNITS - n_dead) units of the
    per-seed permutation are alive."""
    c2 = np.zeros(N_UNITS)
    alive = bank["perm"][: N_UNITS - n_dead]
    c2[alive] = bank["c2_mag"][alive]
    return c2


def run_reservoir(bank, u, c2):
    omega, zeta, w_in, C = bank["omega"], bank["zeta"], bank["w_in"], bank["C"]
    rowsum = C.sum(axis=1)
    x = np.zeros(N_UNITS)
    v = np.zeros(N_UNITS)
    feats = np.empty((len(u), 2 * N_UNITS + 1))
    for n in range(len(u)):
        un = u[n]
        for _ in range(N_SUB):
            coupling = C @ x - rowsum * x
            accel = (-(omega ** 2) * x - 2 * zeta * omega * v
                     + c2 * x ** 2 - BETA3 * x ** 3 + w_in * un + coupling)
            v = v + accel * DT
            x = x + v * DT
        if not np.all(np.isfinite(x)):
            raise RuntimeError(f"reservoir blew up at sample {n}")
        feats[n, :N_UNITS] = x
        feats[n, N_UNITS:2 * N_UNITS] = v
        feats[n, -1] = 1.0
    return feats


def ridge_fit_r2(X_train, y_train, X_test, y_test, lam=RIDGE_LAMBDA):
    A = X_train.T @ X_train + lam * np.eye(X_train.shape[1])
    w = np.linalg.solve(A, X_train.T @ y_train)
    pred = X_test @ w
    sse = np.sum((y_test - pred) ** 2)
    sst = np.sum((y_test - np.mean(y_test)) ** 2)
    return 1.0 - sse / sst


EVEN_TASKS = {
    "u[n-1]*u[n-2]": lambda u, n: u[n - 1] * u[n - 2],
    "u[n-1]*u[n-3]": lambda u, n: u[n - 1] * u[n - 3],
    "u[n-1]^2":      lambda u, n: u[n - 1] ** 2,
}
ODD_TASKS = {
    "u[n-1]":            lambda u, n: u[n - 1],
    "u[n-1]^3":          lambda u, n: u[n - 1] ** 3,
    "u[n-1]-0.5*u[n-2]": lambda u, n: u[n - 1] - 0.5 * u[n - 2],
}


def score_tasks(feats, u):
    valid_start = WASHOUT + 4
    idx = np.arange(valid_start, T_STEPS)
    split = valid_start + int((T_STEPS - valid_start) * TRAIN_FRAC)
    train_mask = idx < split
    X = feats[idx]
    out = {}
    for name, fn in {**EVEN_TASKS, **ODD_TASKS}.items():
        y = np.array([fn(u, n) for n in idx])
        out[name] = ridge_fit_r2(X[train_mask], y[train_mask],
                                 X[~train_mask], y[~train_mask])
    return out


def rung1():
    print("RUNG 1 -- capability gate (all-alive vs quadratic-free control)")
    rng = np.random.default_rng(7)
    bank = build_bank(rng)
    u = rng.uniform(-INPUT_AMP, INPUT_AMP, T_STEPS)

    feats_full = run_reservoir(bank, u, c2_with_dead(bank, 0))
    feats_ctrl = run_reservoir(bank, u, np.zeros(N_UNITS))
    amp = np.mean(np.abs(feats_full[:, :N_UNITS]))
    print(f"  mean |x| (all-alive): {amp:.3f}  (needs ~O(1) for engagement)")

    r2_full = score_tasks(feats_full, u)["u[n-1]*u[n-2]"]
    r2_ctrl = score_tasks(feats_ctrl, u)["u[n-1]*u[n-2]"]
    print(f"  product task u[n-1]*u[n-2]:  all-alive R^2 = {r2_full:.3f}   "
          f"quadratic-free control R^2 = {r2_ctrl:.3f}")
    passed = (r2_full >= GATE_R2_MIN) and (r2_ctrl < GATE_CONTROL_MAX)
    print(f"  GATE {'PASSED' if passed else 'FAILED'} "
          f"(need all-alive >= {GATE_R2_MIN}, control < {GATE_CONTROL_MAX})\n")
    return passed


def rung2():
    print(f"RUNG 2 -- paired symmetry test: {DEAD_SYMMETRIC}/{N_UNITS} dead "
          f"(symmetric) vs {DEAD_BROKEN}/{N_UNITS} dead (broken), "
          f"{N_SEEDS} paired seeds")
    names = list(EVEN_TASKS) + list(ODD_TASKS)
    sym = {n: [] for n in names}
    brk = {n: [] for n in names}
    for s in range(N_SEEDS):
        rng = np.random.default_rng(1000 + s)
        bank = build_bank(rng)
        u = rng.uniform(-INPUT_AMP, INPUT_AMP, T_STEPS)
        r_sym = score_tasks(run_reservoir(bank, u, c2_with_dead(bank, DEAD_SYMMETRIC)), u)
        r_brk = score_tasks(run_reservoir(bank, u, c2_with_dead(bank, DEAD_BROKEN)), u)
        for n in names:
            sym[n].append(r_sym[n])
            brk[n].append(r_brk[n])
        print(f"  seed {s + 1}/{N_SEEDS} done", end="\r")
    print()

    print(f"\n{'Task':<22}{'Order':<7}{'Symmetric R^2':<20}{'Broken R^2':<20}"
          f"{'Gap':<10}{'paired t':<9}")
    print("-" * 88)
    even_gaps, odd_gaps = [], []
    for name in names:
        order = "even" if name in EVEN_TASKS else "odd"
        ms, sds = np.mean(sym[name]), np.std(sym[name])
        mb, sdb = np.mean(brk[name]), np.std(brk[name])
        d = np.array(brk[name]) - np.array(sym[name])
        t = d.mean() / (d.std(ddof=1) / np.sqrt(N_SEEDS))
        (even_gaps if order == "even" else odd_gaps).append(d.mean())
        print(f"{name:<22}{order:<7}{ms:>7.3f} +/- {sds:<8.3f}"
              f"{mb:>7.3f} +/- {sdb:<8.3f}{d.mean():>+8.3f}  {t:>+6.2f}")

    print(f"\nMean gap, even tasks: {np.mean(even_gaps):+.4f}   "
          f"(acoustic reference: +0.150; uncoupled first test: +0.0066)")
    print(f"Mean gap, odd tasks:  {np.mean(odd_gaps):+.4f}   "
          f"(acoustic reference: -0.002; uncoupled first test: -0.0895)")
    print("\nPre-registered predictions: P2 even gap positive (paired t > 2); "
          "P3 odd gap ~0, not the uncoupled test's -0.09 damage.")


def main():
    print("Coupled resonator-bank symmetry test (the fair follow-up)")
    print(f"N_UNITS={N_UNITS}  N_SUB={N_SUB}  INPUT_AMP={INPUT_AMP}  "
          f"coupling={COUPLING_SCALE}x{CONNECTIVITY:.0%}\n")
    passed = rung1()
    if "--gate" in sys.argv:
        return
    if not passed:
        print("Gate failed -- rung 2 not run (per pre-registered design).")
        return
    rung2()


if __name__ == "__main__":
    main()
