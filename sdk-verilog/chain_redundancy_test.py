#!/usr/bin/env python3
"""Sharper version of chain_order_detector.py's question, fixing the flaw
the last two attempts exposed: any task where per-resonator FREQUENCY
TUNING lets a single resonator solve it alone (via its own onset timing)
will make coupling look useless regardless of whether it's actually doing
anything -- because independent per-resonator identity was already enough.

FIX: make all 4 resonators IDENTICAL (same freq=880Hz, same damping). Fed
through the one shared drive line, with ZERO coupling these 4 resonators
are DETERMINISTICALLY IDENTICAL at every timestep -- four copies of the
same single-resonator system carry exactly ONE resonator's worth of
information, no matter how many features you extract. The ONLY thing that
can break that redundancy in this hardware is coupling itself (edge
resonators have 1 neighbor, interior ones have 2 -- a real, physical,
position-dependent asymmetry that only exists once bonds are nonzero).
This makes the comparison mechanistically clean rather than confounded by
per-resonator tuning doing the real work.

TASK: "one long burst" vs "two short bursts separated by a SHORT gap"
(gap shorter than the resonator's own energy-decay time, so a single
resonator's own trace barely dips -- deliberately hard for one channel
alone, chosen to actually stress-test whether the extra channels carry
real information once coupling exists).

PRE-REGISTERED: NONE should sit near chance (mechanically forced, not
guessed -- 4 identical redundant channels = ~1 channel's worth of
information, and that channel's own response is designed to barely
differ between the two conditions). If UNIFORM and/or DIMERIZED coupling
score meaningfully above that floor, this is a genuine, non-confounded
demonstration that coupling adds real information the identical
independent bank structurally cannot have. Report whichever way it lands.
"""
import numpy as np
import sys
sys.path.insert(0, ".")
from spikeling_resonator_verilog import to_fixed, FRAC_BITS, DT_SHIFT, ENERGY_FRAC_BITS, compute_alpha_shift, ENERGY_TIME_CONSTANT, DEFAULT_RESONATOR_GATE_THRESHOLD, ResonatorSpec

dt = 2.0 ** -DT_SHIFT
ALPHA_SHIFT = compute_alpha_shift(DT_SHIFT, ENERGY_TIME_CONSTANT)
GATE_THRESH = to_fixed(DEFAULT_RESONATOR_GATE_THRESHOLD)

N = 4
FREQ, DAMPING = 880.0, 0.05
resonators = [ResonatorSpec(f"R{i}", FREQ, DAMPING) for i in range(N)]
K1 = [to_fixed(r.k1) for r in resonators]
K2 = [to_fixed(r.k2) for r in resonators]
K3 = [to_fixed(r.k3) for r in resonators]

def mul_shift(a, b, shift=FRAC_BITS):
    return (a * b) >> shift

def run_chain(drive_q_seq, cv_q, cw_q):
    x = [0]*N; v = [0]*N; energy = [0]*N
    trace = np.zeros((len(drive_q_seq), N))
    for t, dq in enumerate(drive_q_seq):
        xn_, vn_, en_ = [0]*N, [0]*N, [0]*N
        for i in range(N):
            k1x = mul_shift(K1[i], x[i]); k2v = mul_shift(K2[i], v[i]); k3d = mul_shift(K3[i], dq)
            bl = cv_q if (i-1) % 2 == 0 else cw_q
            br = cv_q if i % 2 == 0 else cw_q
            cleft = mul_shift(bl, x[i-1]) if i > 0 else 0
            cright = mul_shift(br, x[i+1]) if i < N-1 else 0
            vn = v[i] - k1x - k2v + k3d + cleft + cright
            xn = x[i] + (vn >> DT_SHIFT)
            gate = 1 if (xn >= GATE_THRESH or xn <= -GATE_THRESH) else 0
            gx = xn if gate else 0
            x2 = gx*gx
            en = energy[i] + ((x2 - energy[i]) >> ALPHA_SHIFT) if gate else energy[i] - (energy[i] >> ALPHA_SHIFT)
            xn_[i], vn_[i], en_[i] = xn, vn, en
        x, v, energy = xn_, vn_, en_
        trace[t] = energy
    return trace

def make_trial(pattern, seed, steps=1600):
    rng = np.random.default_rng(seed)
    jitter = rng.integers(-40, 40)
    t = np.arange(steps) * dt
    sig = np.zeros(steps)
    start = 150 + jitter
    if pattern == "long":
        sig[start:start+700] += 1.0 * np.sin(2*np.pi*FREQ*t[start:start+700])
    else:  # "gapped" -- short gap, chosen shorter than the decay time at damping=0.05
        gap = 45
        half = (700 - gap) // 2
        s1, e1 = start, start+half
        s2, e2 = e1+gap, e1+gap+half
        sig[s1:e1] += 1.0 * np.sin(2*np.pi*FREQ*t[s1:e1])
        sig[s2:e2] += 1.0 * np.sin(2*np.pi*FREQ*t[s2:e2])
    sig += 0.15 * rng.standard_normal(steps)
    return [to_fixed(float(vv)) for vv in sig]

def dataset(n_per_class, seed0=5000):
    trials, labels = [], []
    for k in range(n_per_class):
        trials.append(make_trial("long", seed0+2*k)); labels.append(+1)
        trials.append(make_trial("gapped", seed0+2*k+1)); labels.append(-1)
    return trials, np.array(labels)

ridge = lambda X, y, lam=1.0: np.linalg.solve(X.T @ X + lam*np.eye(X.shape[1]), X.T @ y)

def evaluate(cv_real, cw_real, trials, labels, split, n_samples=20):
    cv_q, cw_q = to_fixed(cv_real*dt), to_fixed(cw_real*dt)
    feats = []
    for dq in trials:
        trace = run_chain(dq, cv_q, cw_q) / float(1 << ENERGY_FRAC_BITS)
        idx = np.linspace(0, len(dq)-1, n_samples).astype(int)
        feats.append(trace[idx].flatten())
    X = np.array(feats)
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    X = np.hstack([X, np.ones((len(X), 1))])
    w = ridge(X[:split], labels[:split])
    pred = np.sign(X[split:] @ w)
    return np.mean(pred == labels[split:])

print("Task: 'one long burst' vs 'two short bursts, short gap' -- 4 IDENTICAL 880Hz resonators")
print("(zero coupling => 4 bit-identical channels => ~1 channel's worth of information, by construction)\n")

trials, labels = dataset(n_per_class=100)
perm = np.random.default_rng(7).permutation(len(trials))
trials = [trials[i] for i in perm]; labels = labels[perm]
split = 140

# sanity: confirm the NONE-coupling redundancy claim directly on real trajectories
t0 = run_chain(trials[0], 0, 0)
print(f"[sanity] with zero coupling, are all 4 channels bit-identical? {np.array_equal(t0[:,0], t0[:,1]) and np.array_equal(t0[:,0], t0[:,3])}\n")

Cu = 2500.0
settings = {
    "NONE (zero coupling, forced-redundant)": (0.0, 0.0),
    "UNIFORM": (Cu, Cu),
    "DIMERIZED": (0.3*2*Cu, 1.7*2*Cu),
}
results = {}
for name, (cv, cw) in settings.items():
    acc = evaluate(cv, cw, trials, labels, split)
    results[name] = acc
    print(f"  {name:<42} test accuracy = {acc:.3f}  ({int(round(acc*(len(labels)-split)))}/{len(labels)-split})")

print("\n--- verdict ---")
none_acc, uni_acc, dim_acc = results["NONE (zero coupling, forced-redundant)"], results["UNIFORM"], results["DIMERIZED"]
print(f"uniform vs none: {uni_acc-none_acc:+.3f}   dimerized vs none: {dim_acc-none_acc:+.3f}   dimerized vs uniform: {dim_acc-uni_acc:+.3f}")
if none_acc <= 0.65 and max(uni_acc, dim_acc) >= none_acc + 0.15:
    print("POSITIVE: with the redundancy confound removed, coupling measurably adds information a genuinely")
    print("independent identical bank cannot have -- the clean win this feature needed to earn.")
elif none_acc >= 0.85:
    print("Even the forced-redundant zero-coupling case solved the task well -- the gap/damping choice")
    print("didn't stress a single channel hard enough; task design issue, not evidence against coupling.")
else:
    print("No clean separation -- coupling did not measurably help even with the redundancy confound removed.")
    print("Honest conclusion: two well-motivated task designs now, neither shows a real computational")
    print("edge for this coupling feature. The verified, standing result remains the HARDWARE one:")
    print("real, working, generation-efficient coupling exists and simulates correctly -- a genuine task")
    print("benefit has not been found tonight despite two honest, non-trivial attempts.")
