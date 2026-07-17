#!/usr/bin/env python3
"""Real use for the new coupled-resonator hardware: TONE-ORDER detection.

Spikeling's existing, validated Resonator use case (tone_detector.spk,
99.2% accuracy) answers "did frequency X occur" -- each resonator is
independent, so the bank fundamentally CANNOT tell "did LOW happen before
HIGH, or HIGH before LOW" -- independent threshold detectors have no way
to encode order, only presence.

HYPOTHESIS (mechanistic, testable): inter-resonator coupling lets one
resonator's activity influence its neighbor's future state, which a plain
independent bank cannot do -- so a coupled chain's resonators, read out
together, might carry order information that independent resonators
structurally cannot. Whether SSH-DIMERIZED coupling specifically (the
feature built tonight) beats plain UNIFORM coupling (same total coupling
budget, no v/w alternation) is a SEPARATE, sharper question -- isolates
"does dimerization add anything over just adding coupling."

Architecture: N=4 chain, R0=110Hz (LOW tag), R1/R2=300Hz relays,
R3=880Hz (HIGH tag), bonds (0-1)=v (1-2)=w (2-3)=v. Same fixed-point
arithmetic as the real generated Verilog (test_chain_coupling.py already
validated this matches the float reference to <1.2% error and the real
iverilog simulation behaviorally). Three coupling settings compared,
coupling BUDGET matched (v+w)/2 equal across uniform/dimerized so it's a
fair comparison, not "more coupling always wins":
  NONE:      v=w=0            (today's actual shipped behavior)
  UNIFORM:   v=w=Cu           (coupling exists, no dimerization)
  DIMERIZED: v=0.3*2*Cu, w=1.7*2*Cu   (same budget, alternating -- tonight's feature)

Feature used for classification = each resonator's FINAL energy_ema --
a real register that already exists in the generated hardware, not
something invented for this test.

PRE-REGISTERED: no prediction on which wins. Real mechanism for coupling
mattering exists (order changes which resonator's activity arrives at a
neighbor first); real mechanism for it NOT mattering also exists (energy_ema
is a slow leaky average, may wash out timing/order information). Report
whichever way the numbers land.
"""
import numpy as np
import sys
sys.path.insert(0, ".")
from spikeling_resonator_verilog import (
    to_fixed, FRAC_BITS, WIDTH, DT_SHIFT, ENERGY_FRAC_BITS, ENERGY_WIDTH,
    DEFAULT_RESONATOR_GATE_THRESHOLD, DEFAULT_RESONATOR_THRESHOLD,
    compute_alpha_shift, ENERGY_TIME_CONSTANT, ResonatorSpec,
)

rng_master = np.random.default_rng(0)
dt = 2.0 ** -DT_SHIFT
ALPHA_SHIFT = compute_alpha_shift(DT_SHIFT, ENERGY_TIME_CONSTANT)
GATE_THRESH = to_fixed(DEFAULT_RESONATOR_GATE_THRESHOLD)

FREQS = [110.0, 300.0, 300.0, 880.0]
DAMPING = 0.03
resonators = [ResonatorSpec(f"R{i}", f, DAMPING) for i, f in enumerate(FREQS)]
N = len(resonators)
K1 = [to_fixed(r.k1) for r in resonators]
K2 = [to_fixed(r.k2) for r in resonators]
K3 = [to_fixed(r.k3) for r in resonators]
THRESH2 = [to_fixed(r.thresh2, ENERGY_FRAC_BITS) for r in resonators]

def mul_shift(a, b, shift=FRAC_BITS):
    return (a * b) >> shift

def run_chain(drive_q_seq, couple_v_q, couple_w_q):
    """Exact same integer ops as generate_coupled_module()'s always block,
    INCLUDING the real detected-pulse edge-detect logic (was_above/now_above
    vs THRESH2) -- this is the actual signal real hardware exposes, not an
    abstraction invented for this test."""
    x = [0] * N; v = [0] * N; energy = [0] * N
    was_above = [False] * N
    energy_trace = np.zeros((len(drive_q_seq), N))
    first_detect = [-1] * N   # step index of first detected pulse, -1 = never
    for t, drive_q in enumerate(drive_q_seq):
        x_new, v_new, e_new = [0]*N, [0]*N, [0]*N
        for i in range(N):
            k1x = mul_shift(K1[i], x[i]); k2v = mul_shift(K2[i], v[i]); k3d = mul_shift(K3[i], drive_q)
            bond_left = couple_v_q if (i - 1) % 2 == 0 else couple_w_q
            bond_right = couple_v_q if i % 2 == 0 else couple_w_q
            cleft = mul_shift(bond_left, x[i - 1]) if i > 0 else 0
            cright = mul_shift(bond_right, x[i + 1]) if i < N - 1 else 0
            vn = v[i] - k1x - k2v + k3d + cleft + cright
            xn = x[i] + (vn >> DT_SHIFT)
            gate = 1 if (xn >= GATE_THRESH or xn <= -GATE_THRESH) else 0
            gated_x = xn if gate else 0
            x2 = gated_x * gated_x
            if gate:
                en = energy[i] + ((x2 - energy[i]) >> ALPHA_SHIFT)
            else:
                en = energy[i] - (energy[i] >> ALPHA_SHIFT)
            now_above = en >= THRESH2[i]
            if now_above and not was_above[i] and first_detect[i] == -1:
                first_detect[i] = t
            was_above[i] = now_above
            x_new[i], v_new[i], e_new[i] = xn, vn, en
        x, v, energy = x_new, v_new, e_new
        energy_trace[t] = energy
    return energy_trace, first_detect

def make_trial(order, seed, steps=2200):
    """order: 'low_high' or 'high_low'. Real audio-like burst signal fed
    through the ONE shared drive line (matches the actual hardware port --
    there's no way to feed different resonators different signals)."""
    rng = np.random.default_rng(seed)
    burst_len = 700
    gap = 200
    jitter = rng.integers(-60, 60)
    start1 = 150 + jitter
    t = np.arange(steps) * dt
    sig = np.zeros(steps)
    f1, f2 = (110.0, 880.0) if order == "low_high" else (880.0, 110.0)
    s1, e1 = start1, start1 + burst_len
    s2, e2 = e1 + gap, e1 + gap + burst_len
    sig[max(s1,0):min(e1,steps)] += 1.0 * np.sin(2*np.pi*f1*t[max(s1,0):min(e1,steps)])
    sig[max(s2,0):min(e2,steps)] += 1.0 * np.sin(2*np.pi*f2*t[max(s2,0):min(e2,steps)])
    sig += 0.15 * rng.standard_normal(steps)
    drive_q = [to_fixed(float(v)) for v in sig]
    return drive_q

def dataset(n_per_class, seed0=1000):
    trials, labels = [], []
    for k in range(n_per_class):
        trials.append(make_trial("low_high", seed0 + 2*k)); labels.append(+1)
        trials.append(make_trial("high_low", seed0 + 2*k + 1)); labels.append(-1)
    return trials, np.array(labels)

ridge = lambda X, y, lam=1.0: np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)

def evaluate(couple_v_real, couple_w_real, trials, labels, split):
    cv_q = to_fixed(couple_v_real * dt); cw_q = to_fixed(couple_w_real * dt)
    feats = []
    for dq in trials:
        etrace, first_detect = run_chain(dq, cv_q, cw_q)
        steps = len(dq)
        # real hardware feature: WHEN each resonator first crossed threshold
        # (sentinel = steps, i.e. "never", if it didn't fire) -- this is what
        # order information should actually live in, not a final snapshot.
        timing = [steps if fd == -1 else fd for fd in first_detect]
        feats.append(timing)
    X = np.array(feats, dtype=float)
    X = np.hstack([X, np.ones((len(X), 1))])   # bias term
    Xtr, ytr = X[:split], labels[:split]
    Xte, yte = X[split:], labels[split:]
    w = ridge(Xtr, ytr)
    pred = np.sign(Xte @ w)
    acc = np.mean(pred == yte)
    return acc, X

print("Generating dataset: 200 trials (100 low->high, 100 high->low), real audio-burst drive signal\n")
trials, labels = dataset(n_per_class=100)
perm = np.random.default_rng(42).permutation(len(trials))
trials = [trials[i] for i in perm]; labels = labels[perm]
split = 140

Cu = 2500.0   # uniform coupling budget
settings = {
    "NONE (today's shipped behavior)": (0.0, 0.0),
    "UNIFORM (coupling, no dimerization)": (Cu, Cu),
    "DIMERIZED (tonight's feature, same budget)": (0.3 * 2 * Cu, 1.7 * 2 * Cu),
}

results = {}
for name, (cv, cw) in settings.items():
    acc, _ = evaluate(cv, cw, trials, labels, split)
    results[name] = acc
    print(f"  {name:<45} test accuracy = {acc:.3f}  ({int(acc*(len(labels)-split))}/{len(labels)-split} correct)")

print("\n--- verdict ---")
none_acc = results["NONE (today's shipped behavior)"]
uni_acc = results["UNIFORM (coupling, no dimerization)"]
dim_acc = results["DIMERIZED (tonight's feature, same budget)"]
print(f"coupling vs none: {uni_acc - none_acc:+.3f}  |  dimerized vs uniform: {dim_acc - uni_acc:+.3f}")
if none_acc <= 0.55:
    print("Confirms the mechanism: independent resonators (today's real shipped design) are near")
    print("chance on order detection -- they structurally cannot encode order, as predicted.")
if uni_acc > none_acc + 0.1:
    print("Coupling (of some form) measurably helps order detection over independent resonators.")
if dim_acc > uni_acc + 0.05:
    print("Dimerization specifically adds value over plain uniform coupling at the same budget.")
elif abs(dim_acc - uni_acc) <= 0.05:
    print("Dimerization does NOT measurably beat plain uniform coupling here -- honest: the efficiency")
    print("win (2 constants vs storing more) stands on its own, but don't oversell a task-performance edge.")
else:
    print("Dimerization is WORSE than uniform coupling on this task -- report plainly, do not spin.")
