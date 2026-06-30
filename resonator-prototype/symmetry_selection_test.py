#!/usr/bin/env python3
"""
Cross-substrate generality test: does the acoustic-plate quadratic
symmetry-selection rule reproduce on a Spikeling Resonator bank?

Background (see ../../012-ternary/paper/cross_substrate_symmetry_findings.md
and acoustic-vortex-sim/reservoir_computing/FINDINGS.txt rung 5c/6):
a quasicrystal-perforated MEMS plate beats a periodic plate on even-order
("product") reservoir-computing tasks, because the periodic plate's exact
mirror symmetry forces its modes' quadratic self-nonlinearity coefficient
c2 = integral(phi^3) to vanish for ~88% of modes (a selection rule), while
breaking that symmetry (quasicrystal: ~38% dead) keeps c2 alive almost
everywhere. The effect is a clean even/odd dichotomy: present on every
even-order task, absent on every odd-order one.

This script asks: does the SAME mechanism -- a per-unit quadratic
self-nonlinearity, present in a controllable fraction of units -- produce
the same even/odd dichotomy in a *different* substrate built from the same
damped-oscillator equation (Resonator, this project), instead of an
FEM-simulated acoustic plate? It is a generality test of the mechanism,
not a re-run: same equation class (x'' = -omega^2 x - 2*damping*omega*v +
drive + c2*x^2), genuinely different system (software reservoir, discrete
per-symbol updates, no real plate geometry at all -- c2 is set directly
by hand, not derived from any spatial mode-shape integral).

Two reservoir configs, matching the acoustic plate's measured dead
fractions as closely as possible:
    SYMMETRIC  -- 88% of units have c2=0 (mirrors periodic D4 plate)
    BROKEN     -- 38% of units have c2=0 (mirrors the quasicrystal)

Run it:
    python symmetry_selection_test.py
"""

import numpy as np

N_UNITS = 24
N_SEEDS = 20
T_STEPS = 3000
WASHOUT = 200
TRAIN_FRAC = 0.7
RIDGE_LAMBDA = 1e-3

DEAD_FRAC_SYMMETRIC = 0.88   # matches periodic D4 plate (FINDINGS.txt rung 5c)
DEAD_FRAC_BROKEN = 0.38      # matches quasicrystal


def build_bank(rng, dead_frac):
    """Sample one reservoir's fixed parameters (frequencies, damping, c2)."""
    omega = rng.uniform(0.05, 0.55, size=N_UNITS)          # rad/step
    damping = rng.uniform(0.05, 0.2, size=N_UNITS)
    coupling = rng.uniform(0.5, 1.5, size=N_UNITS)         # input weights
    is_dead = rng.uniform(size=N_UNITS) < dead_frac
    c2 = rng.uniform(0.15, 0.45, size=N_UNITS) * rng.choice([-1.0, 1.0], size=N_UNITS)
    c2[is_dead] = 0.0
    return omega, damping, coupling, c2


def run_reservoir(u, omega, damping, coupling, c2):
    """Discrete-time damped-oscillator reservoir, one state update per
    input symbol u[n] (standard reservoir-computing convention -- the
    acoustic study's own rungs likewise treat dt as one step per symbol,
    not real physical time). Symplectic Euler, matching resonator_bank.py.
    x is clipped to keep the quadratic self-term from blowing up -- the
    acoustic FINDINGS note state amplitudes stay ~0.1 with the nonlinear
    term comparable to (not dominating) the linear restoring force; the
    clip enforces the same "engaged but not exploding" regime here.
    """
    dt = 1.0
    T = len(u)
    x = np.zeros(N_UNITS)
    v = np.zeros(N_UNITS)
    states = np.zeros((T, N_UNITS))
    for n in range(T):
        accel = -(omega ** 2) * x - 2 * damping * omega * v
        accel += coupling * u[n]
        accel += c2 * x ** 2
        v = v + accel * dt
        x = x + v * dt
        x = np.clip(x, -3.0, 3.0)
        states[n] = x
    return states


def ridge_fit_r2(X_train, y_train, X_test, y_test, lam=RIDGE_LAMBDA):
    Xb = np.hstack([X_train, np.ones((len(X_train), 1))])
    Xtb = np.hstack([X_test, np.ones((len(X_test), 1))])
    A = Xb.T @ Xb + lam * np.eye(Xb.shape[1])
    w = np.linalg.solve(A, Xb.T @ y_train)
    pred = Xtb @ w
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


def score_config(dead_frac, seed_base=0):
    results = {name: [] for name in list(EVEN_TASKS) + list(ODD_TASKS)}
    for s in range(N_SEEDS):
        rng = np.random.default_rng(seed_base + s)
        omega, damping, coupling, c2 = build_bank(rng, dead_frac)
        u = rng.uniform(-0.5, 0.5, size=T_STEPS)
        states = run_reservoir(u, omega, damping, coupling, c2)

        valid_start = WASHOUT + 4  # leave room for lag-3 targets
        idx = np.arange(valid_start, T_STEPS)
        split = valid_start + int((T_STEPS - valid_start) * TRAIN_FRAC)

        X = states[idx]
        for name, fn in {**EVEN_TASKS, **ODD_TASKS}.items():
            y = np.array([fn(u, n) for n in idx])
            train_mask = idx < split
            test_mask = ~train_mask
            r2 = ridge_fit_r2(X[train_mask], y[train_mask], X[test_mask], y[test_mask])
            results[name].append(r2)
    return {name: (np.mean(v), np.std(v)) for name, v in results.items()}


def main():
    print(f"Resonator-bank symmetry selection-rule test")
    print(f"N_UNITS={N_UNITS}  N_SEEDS={N_SEEDS}  T_STEPS={T_STEPS}\n")

    print("Running SYMMETRIC config (dead_frac=%.2f, mirrors periodic D4 plate)..." % DEAD_FRAC_SYMMETRIC)
    sym = score_config(DEAD_FRAC_SYMMETRIC, seed_base=0)
    print("Running BROKEN config (dead_frac=%.2f, mirrors quasicrystal)..." % DEAD_FRAC_BROKEN)
    brk = score_config(DEAD_FRAC_BROKEN, seed_base=10000)

    print(f"\n{'Task':<22}{'Order':<7}{'Symmetric R^2':<20}{'Broken R^2':<20}{'Gap (brk-sym)':<14}")
    print("-" * 83)
    even_gaps, odd_gaps = [], []
    for name in EVEN_TASKS:
        m_s, sd_s = sym[name]
        m_b, sd_b = brk[name]
        gap = m_b - m_s
        even_gaps.append(gap)
        print(f"{name:<22}{'even':<7}{m_s:>7.3f} +/- {sd_s:<8.3f}{m_b:>7.3f} +/- {sd_b:<8.3f}{gap:>+10.3f}")
    for name in ODD_TASKS:
        m_s, sd_s = sym[name]
        m_b, sd_b = brk[name]
        gap = m_b - m_s
        odd_gaps.append(gap)
        print(f"{name:<22}{'odd':<7}{m_s:>7.3f} +/- {sd_s:<8.3f}{m_b:>7.3f} +/- {sd_b:<8.3f}{gap:>+10.3f}")

    print(f"\nMean gap, even tasks: {np.mean(even_gaps):+.4f}")
    print(f"Mean gap, odd tasks:  {np.mean(odd_gaps):+.4f}")
    print("\n(Acoustic-plate reference, FINDINGS.txt rung 6: mean gap even = +0.150, odd = -0.002)")


if __name__ == "__main__":
    main()
