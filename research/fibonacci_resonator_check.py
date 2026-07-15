#!/usr/bin/env python3
"""Does the Fibonacci/quasicrystal generation-efficiency finding (topological-phononics,
2026-07-12: a 3-parameter recursive rule vs a stored random matrix, ~1.4-2x cost on linear
recall / ~1-17% on NARMA10) hold on Spikeling's REAL Resonator neuron, not just the abstract
tanh-reservoir stand-in it was measured on? Reuses ssh_resonator_bridge.py's real ResonatorState
dynamics, swaps in a Fibonacci-prefix coupling vs a degree-matched random-order coupling.

Note: this substrate uses Spikeling's real per-step Python ResonatorState.step() calls (not a
vectorized matrix reservoir), so it's much slower per node -- kept to modest M for that reason.
"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
import numpy as np
from runtime.runtime import ResonatorState

def progress(i, total, label, t0):
    filled = int(30 * (i / total)) if total else 0
    bar = "#" * filled + "-" * (30 - filled)
    print(f"[{bar}] {i}/{total}  {label}  ({time.time()-t0:5.1f}s elapsed)", flush=True)

FREQ = 1.0 / (2 * np.pi); DAMPING = 0.3; DT = 0.05; HOLD = 20; T = 800; BURN = 150; RHO = 0.7
V, W = 0.4, 1.0

def fib_word(g):
    w = "A"
    for _ in range(g):
        w = w.replace("B", "0").replace("A", "AB").replace("0", "A")
    return w
LONG_WORD = fib_word(14)   # length 610 -- plenty for the M range tested here

def fib_K(M):
    word = LONG_WORD[: M - 1]
    K = np.zeros((M, M))
    for i, sym in enumerate(word):
        c = V if sym == "A" else W
        K[i, i + 1] = K[i + 1, i] = c
    return RHO * K / (np.max(np.abs(np.linalg.eigvalsh(K))) + 1e-9)

def random_degree2_K(M, seed=0):
    rng = np.random.default_rng(seed)
    perm = rng.permutation(M)
    vals = rng.choice([V, W], size=M - 1)
    K = np.zeros((M, M))
    for i in range(M - 1):
        a, b = perm[i], perm[i + 1]
        K[a, b] = K[b, a] = vals[i]
    return RHO * K / (np.max(np.abs(np.linalg.eigvalsh(K))) + 1e-9)

def run(K, u, win):
    M = K.shape[0]
    res = [ResonatorState(name=f"r{i}", freq_hz=FREQ, damping=DAMPING, coupling=1.0) for i in range(M)]
    X = np.zeros((len(u), 2 * M))
    for t in range(len(u)):
        for _ in range(HOLD):
            x = np.array([r.x for r in res])
            drive = win * u[t] + K @ x
            for i, r in enumerate(res):
                r.step(float(drive[i]), DT)
        xf = np.array([r.x for r in res])
        X[t] = np.concatenate([xf, xf ** 2])
    return X

ridge = lambda X, y, lam=1e-2: np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)
nmse = lambda p, y: float(np.mean((p - y) ** 2) / (np.var(y) + 1e-12))

def recall_nmse(K, seed=0, delay=2):
    rng = np.random.default_rng(seed)
    u = rng.standard_normal(T); win = rng.uniform(-1, 1, K.shape[0])
    y = np.zeros(T); y[delay:] = u[:-delay]; yb = y[BURN:]
    X = run(K, u, win)[BURN:]
    return nmse(X @ ridge(X, yb), yb)

Ms = [24]
N_SEEDS = 12
print(f"VARIANCE CHECK: is the near-parity result (0.97x-1.01x @ 3 seeds) real, or noise? "
      f"M={Ms[0]}, {N_SEEDS} seeds\n")
print(f"{'M':>4} | {'Fibonacci':>10} | {'random-order':>13} | {'ratio':>8}")
print("-" * 46)
t0 = time.time()
M = Ms[0]
fib_scores = []
rnd_scores = []
per_seed_ratio = []
for s in range(N_SEEDS):
    progress(s, N_SEEDS, f"seed {s}", t0)
    f = recall_nmse(fib_K(M), seed=s)
    r = recall_nmse(random_degree2_K(M, seed=s), seed=s)
    fib_scores.append(f); rnd_scores.append(r); per_seed_ratio.append(f / max(r, 1e-9))
    print(f"  seed {s}: fib={f:.4f}  random={r:.4f}  ratio={f/max(r,1e-9):.3f}x", flush=True)
progress(N_SEEDS, N_SEEDS, "done", t0)

fib_scores = np.array(fib_scores); rnd_scores = np.array(rnd_scores); ratios = np.array(per_seed_ratio)
mean_r, std_r = ratios.mean(), ratios.std()
sem = std_r / np.sqrt(N_SEEDS)
print("\n--- verdict ---")
print(f"per-seed ratio: mean={mean_r:.3f}  std={std_r:.3f}  SEM={sem:.3f}  "
      f"95% CI=[{mean_r-1.96*sem:.3f}, {mean_r+1.96*sem:.3f}]")
if mean_r - 1.96 * sem <= 1.0 <= mean_r + 1.96 * sem:
    print("CI includes 1.0 -- genuinely indistinguishable from parity at this size/substrate,")
    print("not just luck from a small 3-seed sample. Confirms the near-parity result.")
else:
    print(f"CI does NOT include 1.0 -- there IS a real {'cost' if mean_r > 1 else 'advantage'}, "
          f"just smaller than on the abstract reservoir. The earlier 3-seed 'near parity' read")
    print("was imprecise, not necessarily wrong in direction.")
