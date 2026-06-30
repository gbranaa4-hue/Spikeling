#!/usr/bin/env python3
"""
Third application of the consensus-gate scoping rule found in
012-ternary/paper/{npc_consensus_findings.md, order_acceptance_findings.md}:
"weighted combination wins when evidence is calibrated/continuous;
discretized voting wins when it isn't" -- tested against an independent
field's own published results, not just re-derived internally.

TWO ESTABLISHED RESULTS THIS BRIDGES:
  1. Population-coding theory (e.g. Pouget/Dayan/Zemel-style probabilistic
     population codes): optimal Bayesian/weighted-linear decoding of a
     neuron population beats simple voting WHEN neuron reliability is
     well-characterized (known, Gaussian noise).
  2. Robust statistics: vote/median-style estimators resist outlier
     contamination better than weighted-mean estimators WHEN the noise
     model is unknown/heavy-tailed/uncalibrated at decode time.

Read together, these predict exactly the scoping rule found in the two
tribe.gd tests. This script tests that prediction directly, using
Spikeling's own LIF neuron dynamics (leak/threshold/refractory, same
equations as spikeling.gd), not a toy abstraction.

SETUP: a population of N_NEURONS LIF neurons encodes a binary stimulus
s in {0,1} via spike count over a fixed window. Each neuron has its own
tuning strength and noise level. A CALIBRATION set (clean, regime-A
statistics only) is used to fit both decoders -- mimicking a real
decoder that was tuned once, then deployed blind to whatever regime
shows up at test time.

DECODER 1 -- WEIGHTED LINEAR (inverse-variance weighted sum of each
neuron's response relative to its calibrated midpoint, sign of the sum).
DECODER 2 -- MAJORITY VOTE (each neuron individually votes via its own
calibrated midpoint, majority sign wins).

TEST REGIME A -- clean: same noise model as calibration.
TEST REGIME B -- contaminated: each neuron has a per-trial chance of an
extreme, unmodeled outlier response (an erratic/unreliable spike count),
NOT told to either decoder -- both are deployed exactly as calibrated.

PREDICTION (stated before running): weighted linear wins regime A,
majority vote wins or closes the gap in regime B.

Run it:
    python population_coding_test.py
"""

import numpy as np

N_NEURONS = 15
T_TICKS = 200            # window length, ticks
THRESHOLD = 100.0        # LIF threshold (matches spikeling.gd defaults)
LEAK = 5.0                # LIF leak (matches spikeling.gd defaults)
REFRACTORY = 4             # ticks (matches spikeling.gd default)

N_CALIB_TRIALS = 4000
N_TEST_TRIALS = 6000
N_SEEDS = 25

CONTAMINATION_PROB = 0.10   # per neuron, per trial, in regime B
OUTLIER_CURRENT = 60.0      # extra erratic drive added on a contaminated tick-window


def make_population(rng):
    """Each neuron's per-tick mean drive under s=0 / s=1, and its noise std.
    Tuned so the clean (regime A) task sits well below ceiling (~75-90%
    accuracy), so there's room to actually see whether weighted beats
    vote there, instead of both saturating at 100%."""
    base_drive = rng.uniform(18.0, 26.0, size=N_NEURONS)         # drives spiking regardless of s
    tuning = rng.uniform(0.8, 2.2, size=N_NEURONS)                # extra drive when s=1 (weak signal)
    noise_std = rng.uniform(5.0, 11.0, size=N_NEURONS)            # per-tick current noise (larger)
    return base_drive, tuning, noise_std


def simulate_spike_counts_batch(rng, s_vec, base_drive, tuning, noise_std, contaminated=False):
    """Run N_NEURONS independent LIF neurons for T_TICKS, vectorized across
    BOTH neurons and trials. s_vec: shape (n_trials,) of 0/1.
    Returns spike counts, shape (n_trials, N_NEURONS)."""
    n_trials = len(s_vec)
    p = np.zeros((n_trials, N_NEURONS))
    refr = np.zeros((n_trials, N_NEURONS), dtype=int)
    spikes = np.zeros((n_trials, N_NEURONS), dtype=int)

    drive_mean = base_drive[None, :] + s_vec[:, None] * tuning[None, :]   # (n_trials, N_NEURONS)
    contaminated_mask = np.zeros((n_trials, N_NEURONS), dtype=bool)
    if contaminated:
        contaminated_mask = rng.uniform(size=(n_trials, N_NEURONS)) < CONTAMINATION_PROB

    for _ in range(T_TICKS):
        active = refr == 0
        refr[~active] -= 1

        noise = rng.normal(0, 1, size=(n_trials, N_NEURONS)) * noise_std[None, :]
        input_current = drive_mean + noise
        input_current = np.where(contaminated_mask, input_current + OUTLIER_CURRENT, input_current)

        p = np.where(active, np.maximum(0.0, p - LEAK), p)
        p = np.where(active, p + input_current, p)

        fired = active & (p >= THRESHOLD)
        spikes[fired] += 1
        p = np.where(fired, 0.0, p)
        refr = np.where(fired, REFRACTORY, refr)

    return spikes


def calibrate(rng, base_drive, tuning, noise_std):
    """Estimate per-neuron (mean|s=0, mean|s=1, midpoint, inv-variance weight)
    from clean calibration trials."""
    s0 = np.zeros(N_CALIB_TRIALS, dtype=int)
    s1 = np.ones(N_CALIB_TRIALS, dtype=int)
    resp0 = simulate_spike_counts_batch(rng, s0, base_drive, tuning, noise_std)
    resp1 = simulate_spike_counts_batch(rng, s1, base_drive, tuning, noise_std)

    mean0, mean1 = resp0.mean(axis=0), resp1.mean(axis=0)
    midpoint = (mean0 + mean1) / 2.0
    pooled_var = (resp0.var(axis=0) + resp1.var(axis=0)) / 2.0 + 1e-6
    inv_var_weight = 1.0 / pooled_var
    direction = np.sign(mean1 - mean0)
    return midpoint, inv_var_weight, direction


def decode_batch(spikes, midpoint, inv_var_weight, direction):
    """spikes: (n_trials, N_NEURONS). Returns (weighted_preds, vote_preds), each (n_trials,)."""
    centered = (spikes - midpoint[None, :]) * direction[None, :]
    weighted_score = np.sum(centered * inv_var_weight[None, :], axis=1)
    weighted_pred = (weighted_score > 0).astype(int)
    votes = np.sign(centered)
    vote_score = np.sum(votes, axis=1)
    vote_pred = (vote_score > 0).astype(int)
    return weighted_pred, vote_pred


def run_seed(seed):
    rng = np.random.default_rng(seed)
    base_drive, tuning, noise_std = make_population(rng)
    midpoint, inv_var_weight, direction = calibrate(rng, base_drive, tuning, noise_std)

    results = {}
    for regime, contaminated in [("A", False), ("B", True)]:
        s_vec = rng.integers(0, 2, size=N_TEST_TRIALS)
        spikes = simulate_spike_counts_batch(rng, s_vec, base_drive, tuning, noise_std, contaminated=contaminated)
        w_pred, v_pred = decode_batch(spikes, midpoint, inv_var_weight, direction)
        results[f"{regime}_weighted"] = np.mean(w_pred == s_vec)
        results[f"{regime}_vote"] = np.mean(v_pred == s_vec)

    return results


def main():
    print("Population-coding decode test: weighted-linear vs majority-vote, LIF neurons")
    print(f"N_NEURONS={N_NEURONS}  N_SEEDS={N_SEEDS}  N_TEST_TRIALS/regime={N_TEST_TRIALS}")
    print(f"Contamination (regime B): {CONTAMINATION_PROB*100:.0f}% of neurons/trial get an unmodeled outlier drive\n")

    all_results = [run_seed(s) for s in range(N_SEEDS)]
    keys = ["A_weighted", "A_vote", "B_weighted", "B_vote"]
    means = {k: np.mean([r[k] for r in all_results]) for k in keys}
    stds = {k: np.std([r[k] for r in all_results]) for k in keys}

    print(f"{'Regime':<10}{'Weighted-linear':<22}{'Majority-vote':<22}{'Gap (vote-weighted)':<20}")
    print("-" * 74)
    for regime in ["A", "B"]:
        w, v = means[f"{regime}_weighted"], means[f"{regime}_vote"]
        wsd, vsd = stds[f"{regime}_weighted"], stds[f"{regime}_vote"]
        gap = v - w
        label = "A (clean)" if regime == "A" else "B (contaminated)"
        print(f"{label:<10}{w:>7.4f} +/- {wsd:<10.4f}{v:>7.4f} +/- {vsd:<10.4f}{gap:>+12.4f}")

    diffs_A = np.array([r["B_vote"] - r["B_weighted"] for r in all_results]) if False else None
    gap_A = np.array([r["A_vote"] - r["A_weighted"] for r in all_results])
    gap_B = np.array([r["B_vote"] - r["B_weighted"] for r in all_results])
    from math import sqrt
    t_A = gap_A.mean() / (gap_A.std(ddof=1) / sqrt(N_SEEDS))
    t_B = gap_B.mean() / (gap_B.std(ddof=1) / sqrt(N_SEEDS))
    print(f"\nRegime A paired t (vote-weighted): t={t_A:.2f}")
    print(f"Regime B paired t (vote-weighted): t={t_B:.2f}")
    print(f"\nPrediction: weighted should win A (t_A very negative), vote should win or close the gap in B (t_B less negative / positive)")


if __name__ == "__main__":
    main()
