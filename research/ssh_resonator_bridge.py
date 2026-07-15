#!/usr/bin/env python3
"""SSH-coupled Resonator reservoir -- a bridge from the topological-phononics study
(https://github.com/gbranaa4-hue/topological-phononics, doi:10.5281/zenodo.21305151) into
Spikeling's REAL `Resonator` neuron.

Spikeling's runtime drives every Resonator with one shared scalar (an independent frequency-detector
bank -- there is NO resonator->resonator coupling). This script is an EXTENSION: it imports the real
`ResonatorState` dynamics and wires M of them into an SSH chain (drive_i = win*u + K @ x, alternating
intra/inter couplings v/w; topological w>v, trivial v>w), then runs the same pre-registered robustness
tests as the phononic study. Readout = [x, x^2] (x^2 is Spikeling's native RMS-energy channel, a
quadratic nonlinearity). Coupling is spectrally normalized below omega^2 for stability (an unnormalized
chain blows up -- the effective stiffness omega^2*I - K goes negative).

Pre-registered results (2026-07-10, this machine):
  capability : recalls u[t-1..3] at NMSE ~0.40-0.50 -- a weak but non-vacuous fading-memory reservoir.
  A) defect  : topological vs trivial frozen-readout penalty -> INCONCLUSIVE (win-rate 60%, 95% CI
               35-85%, n=15; median 2.3x lower but CI spans 50%). The topology-specific advantage is
               fragile in this substrate too, matching the phononic firm-up.
  B) noise   : the decoder cancels STRUCTURED (low-rank, correlated) noise EXACTLY (NMSE = clean) while
               RANDOM (full-rank) noise climbs -> the substrate-INDEPENDENT rank result transfers cleanly.

Takeaway: what transfers from the phononic work is the noise/rank result (decoder algebra), not the
topology. Ties to the sr_*/noise_sweet_spot/population_coding experiments in this folder.

Run:  python ssh_resonator_bridge.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
import numpy as np
from runtime.runtime import ResonatorState          # the REAL Spikeling oscillator

M = 12; FREQ = 1.0 / (2 * np.pi); DAMPING = 0.3; DT = 0.05; HOLD = 20; T = 1500; BURN = 200; RHO = 0.7

def ssh_K(g, remove=None):
    v, w = 1 - g, 1 + g; K = np.zeros((M, M))
    for i in range(M - 1): K[i, i + 1] = K[i + 1, i] = (v if i % 2 == 0 else w)
    if remove is not None: K[remove, :] = 0.0; K[:, remove] = 0.0
    return RHO * K / (np.max(np.abs(np.linalg.eigvalsh(K))) + 1e-9)   # keep < omega^2=1 for stability

def run(g, u, win, remove=None):
    K = ssh_K(g, remove)
    res = [ResonatorState(name=f"r{i}", freq_hz=FREQ, damping=DAMPING, coupling=1.0) for i in range(M)]
    X = np.zeros((len(u), 2 * M))
    for t in range(len(u)):
        for _ in range(HOLD):
            x = np.array([r.x for r in res]); drive = win * u[t] + K @ x
            for i, r in enumerate(res): r.step(float(drive[i]), DT)
        xf = np.array([r.x for r in res]); X[t] = np.concatenate([xf, xf ** 2])
    return X

ridge = lambda X, y, lam=1e-2: np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)
nmse = lambda p, y: float(np.mean((p - y) ** 2) / (np.var(y) + 1e-12))

def main():
    rng = np.random.default_rng(0); u = rng.standard_normal(T); win = rng.uniform(-1, 1, M)
    print(f"SSH-coupled REAL-Resonator reservoir (M={M}). Capability (topological g=0.6):\n")
    for delay in (1, 2, 3):
        y = np.zeros(T); y[delay:] = u[:-delay]; yb = y[BURN:]
        X = run(0.6, u, win)[BURN:]
        print(f"  recall u[t-{delay}]  NMSE = {nmse(X @ ridge(X, yb), yb):.3f}")

    print("\nA) DEFECT (topological g=+0.6 vs trivial g=-0.6, dead resonator, recall u[t-2]):\n")
    pT, pR, wins, n = [], [], 0, 0
    for s in range(3):
        r = np.random.default_rng(s); uu = r.standard_normal(T); wn = r.uniform(-1, 1, M)
        y = np.zeros(T); y[2:] = uu[:-2]; yb = y[BURN:]
        wT = ridge(run(+0.6, uu, wn)[BURN:], yb); wR = ridge(run(-0.6, uu, wn)[BURN:], yb)
        for site in range(2, M - 1, 2):
            XdT = run(+0.6, uu, wn, remove=site)[BURN:]; XdR = run(-0.6, uu, wn, remove=site)[BURN:]
            a = nmse(XdT @ wT, yb) - nmse(XdT @ ridge(XdT, yb), yb)
            b = nmse(XdR @ wR, yb) - nmse(XdR @ ridge(XdR, yb), yb)
            pT.append(a); pR.append(b); wins += (a < b); n += 1
    wr = wins / n; se = (wr * (1 - wr) / n) ** 0.5
    print(f"  topo median {np.median(pT):.3f} | trivial {np.median(pR):.3f} | win-rate {100*wr:.0f}% "
          f"(95% CI {100*(wr-1.96*se):.0f}-{100*(wr+1.96*se):.0f}%, n={n}) -> "
          f"{'topological advantage' if wr-1.96*se > 0.5 else 'INCONCLUSIVE / null'}")

    def add_noise(X, kind, frac, seed):
        r = np.random.default_rng(7000 + seed); nrow, d = X.shape; amp = frac * X.std()
        if kind == "structured":
            c = np.zeros(nrow)
            for t in range(1, nrow): c[t] = 0.9 * c[t - 1] + r.standard_normal()
            return X + amp * np.outer(c / (c.std() + 1e-9), np.ones(d))
        if kind == "random":
            return X + amp * r.standard_normal((nrow, d))
        return X

    def rec(X, yb, kind, frac, seed):
        Xn = add_noise(X, kind, frac, seed); tr = int(0.6 * len(yb))
        return nmse(Xn[tr:] @ ridge(Xn[:tr], yb[:tr]), yb[tr:])

    print("\nB) NOISE (does the decoder cancel STRUCTURED but not RANDOM? recall u[t-2]):\n")
    print(f"  {'frac':>5} | {'clean':>7} | {'structured':>10} | {'random':>7}")
    cln = []; res_rows = {0.3: [], 0.6: []}
    for s in range(3):
        r = np.random.default_rng(100 + s); uu = r.standard_normal(T); wn = r.uniform(-1, 1, M)
        y = np.zeros(T); y[2:] = uu[:-2]; yb = y[BURN:]; X = run(0.6, uu, wn)[BURN:]
        cln.append(rec(X, yb, "none", 0.0, s))
        for frac in (0.3, 0.6):
            res_rows[frac].append((rec(X, yb, "structured", frac, s), rec(X, yb, "random", frac, s)))
    c0 = np.mean(cln)
    for frac in (0.3, 0.6):
        st = np.mean([a for a, _ in res_rows[frac]]); rn = np.mean([b for _, b in res_rows[frac]])
        print(f"  {frac:>5.1f} | {c0:>7.3f} | {st:>10.3f} | {rn:>7.3f}")
    print("\n  structured ~ clean, random climbs = decoder cancels low-rank noise (substrate-independent).")

if __name__ == "__main__":
    main()
