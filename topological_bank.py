#!/usr/bin/env python3
"""The "self-healing" test: an 8-Resonator Spikeling neuromorphic bank,
parsed from the REAL .spk DSL (topological_bank.spk) via Spikeling's own
SpikelingParser and ResonatorState class -- not reconstructed physics --
with SSH-topological dimerized coupling added between neurons (reusing the
exact v=1-g, w=1+g convention validated all night in topological-phononics/).

QUESTION: does killing one neuron in this bank cause the whole system to
crash, or does a topologically-dimerized (g>0) coupling degrade gracefully
compared to a trivial (g<0) one -- i.e., is "self-healing" (defect
tolerance) real for THIS specific Spikeling bank?

TWO REAL BUGS FOUND AND FIXED before this version:
1. Passing the SSH bond term through ResonatorState.step()'s `drive` arg
   got re-multiplied by the resonator's own large intrinsic coupling gain
   (~764 for 220Hz) -- fixed by pre-dividing by r.coupling so the bond
   enters the acceleration equation at its actual SSH-scale magnitude.
2. Holding each random task sample constant for 100 physical substeps (to
   fix a timescale mismatch) accidentally turned the drive into a series of
   near-DC steps instead of an oscillating signal -- exactly the wrong
   input for a frequency-selective resonator. Fixed here by driving
   CONTINUOUSLY at the real physical rate (dt=1/22050) every step, with
   delay/lag values scaled to ~100 physical steps (~1 natural oscillation
   period at 220Hz) instead of the abstract "5 samples" convention borrowed
   from the tanh-reservoir tests, which never meant anything physical here.

PRE-REGISTERED (gbranaa-hue method): capability bar first -- non-vacuous
NMSE required before any defect-penalty number is trusted. No assumed
outcome on topological vs trivial; report honestly either way.
"""
import sys, time
import numpy as np
sys.path.insert(0, "core")
from compiler.compiler import SpikelingParser
from runtime.runtime import ResonatorState

with open("topological_bank.spk") as f:
    ast = SpikelingParser().parse(f.read())

resonator_defs = [n for n in ast.neurons if n.neuron_type == "Resonator"]
N = len(resonator_defs)
print(f"Parsed {N} real Resonator neurons from topological_bank.spk via SpikelingParser\n")

DT = 1.0 / 22050.0
PERIOD_STEPS = 100   # ~1 natural oscillation period at 220Hz (period ~4.5ms / dt ~4.5e-5s)

def make_bank():
    bank = []
    for n in resonator_defs:
        omega = 2 * np.pi * n.freq_hz
        coupling = n.coupling if n.coupling is not None else 4.0e-4 * (omega ** 2)
        bank.append(ResonatorState(name=n.name, freq_hz=n.freq_hz, damping=n.damping, coupling=coupling))
    return bank

def ssh_bonds(N, g):
    v, w = 1.0 - g, 1.0 + g
    return [(v if i % 2 == 0 else w) for i in range(N - 1)]

def step_bank(bank, bonds, drive, dt, defect_idx=None):
    x_snapshot = [r.x if i != defect_idx else 0.0 for i, r in enumerate(bank)]
    for i, r in enumerate(bank):
        if i == defect_idx:
            r.x, r.v, r.energy_ema = 0.0, 0.0, 0.0
            continue
        coupling_term = 0.0
        if i > 0 and (i - 1) != defect_idx:
            coupling_term += bonds[i - 1] * x_snapshot[i - 1]
        if i < N - 1 and (i + 1) != defect_idx:
            coupling_term += bonds[i] * x_snapshot[i + 1]
        r.step(drive + coupling_term / r.coupling, dt)

def bank_states(g, u, defect_idx=None):
    bank = make_bank()
    bonds = ssh_bonds(N, g)
    X = np.zeros((len(u), N))
    for t, d in enumerate(u):
        step_bank(bank, bonds, d, DT, defect_idx=defect_idx)
        X[t] = [r.x for r in bank]
    return X

ridge = lambda X, y, lam=1e-2: np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)
nmse = lambda p, y: float(np.mean((p - y) ** 2) / (np.var(y) + 1e-12))

def linear_recall_task(seed, T=2000, delay=PERIOD_STEPS):
    rng = np.random.default_rng(seed)
    u = rng.standard_normal(T) * 0.5
    y = np.zeros(T); y[delay:] = u[:-delay]
    return u, y

def narma10_task(seed, T=3000):
    lag_a, lag_b = PERIOD_STEPS, PERIOD_STEPS * 10   # ~1 and ~10 oscillation periods
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 0.5, T) * 0.5
    y = np.zeros(T)
    for t in range(lag_b, T):
        y[t] = (0.3 * y[t-lag_a] + 0.05 * y[t-lag_a] * np.sum(y[t-lag_b:t])
                 + 1.5 * u[t-lag_b] * u[t-lag_a] + 0.1)
    return u, y

DEFECT_SITES = [2, 4, 5]
N_SEEDS = 3

def defect_penalty(g, task_fn, burn, test_len):
    penalties, caps = [], []
    for s in range(N_SEEDS):
        u, y = task_fn(seed=s)
        T = len(u)
        split = T - test_len
        Xh = bank_states(g, u)
        w_h = ridge(Xh[burn:split], y[burn:split])
        caps.append(nmse(Xh[split:] @ w_h, y[split:]))
        site_penalties = []
        for k in DEFECT_SITES:
            Xd = bank_states(g, u, defect_idx=k)
            frozen = nmse(Xd[split:] @ w_h, y[split:])
            w_o = ridge(Xd[burn:split], y[burn:split])
            oracle = nmse(Xd[split:] @ w_o, y[split:])
            site_penalties.append(frozen - oracle)
        penalties.append(np.median(site_penalties))
    return np.mean(caps), np.mean(penalties), np.std(penalties)

t0 = time.time()
print("Testing: topological (g=+0.6) vs trivial (g=-0.6) SSH-dimerized coupling")
print(f"{N} real Resonator neurons, {N_SEEDS} seeds x {len(DEFECT_SITES)} defect sites\n")

tasks = [
    ("linear recall (delay~1 period)", lambda seed: linear_recall_task(seed), 300, 400),
    ("NARMA10 (lags ~1 & ~10 periods)", lambda seed: narma10_task(seed), 1200, 500),
]

for label, task_fn, burn, test_len in tasks:
    print(f"--- {label} ---")
    cap_topo, pen_topo, std_topo = defect_penalty(+0.6, task_fn, burn, test_len)
    cap_triv, pen_triv, std_triv = defect_penalty(-0.6, task_fn, burn, test_len)
    print(f"  capability (undamaged NMSE): topological={cap_topo:.4f}  trivial={cap_triv:.4f}")
    caps_ok = cap_topo < 0.9 and cap_triv < 0.9
    print(f"  capability bar (non-vacuous): {'PASS' if caps_ok else 'FAIL -- penalty numbers below not meaningful'}")
    print(f"  defect penalty: topological={pen_topo:.4f}(+/-{std_topo:.4f})  trivial={pen_triv:.4f}(+/-{std_triv:.4f})")
    if caps_ok:
        ratio = pen_topo / max(pen_triv, 1e-9)
        print(f"  ratio (topological/trivial): {ratio:.3f}x  (<1 = topological more graceful)")
    print(f"  elapsed: {time.time()-t0:.1f}s\n")
