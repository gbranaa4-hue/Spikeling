#!/usr/bin/env python3
"""
Benchmark: resonance-based detection vs naive raw-amplitude-threshold
detection, for "is a specific target frequency present in this signal?"

Claim being tested: a resonator tuned to a target frequency can tell
whether THAT frequency is present, even when other (distractor) tones
and noise are also in the signal -- whereas a naive "is the signal loud"
amplitude threshold can't distinguish the target tone from distractor
tones, since it only looks at total energy, not which frequency it's at.

Setup per trial:
  - Coin flip: target frequency (440Hz) present or not, at varying amplitude.
  - Always add 1-2 random distractor tones from a different frequency set,
    at random amplitude (this is what should fool the naive detector).
  - Add broadband noise.
  - Feed the same mixed signal to both detectors; compare to ground truth.

Run it:
    python accuracy_benchmark.py
"""

import math
import random

from resonator_bank import Resonator


TARGET_FREQ = 440
DISTRACTOR_FREQS = [110, 220, 880, 1760]


def make_mixed_signal_fn(target_present, target_amp, distractors, noise_amp):
    components = list(distractors)
    if target_present:
        components.append((TARGET_FREQ, target_amp))

    def signal(t):
        val = sum(amp * math.sin(2 * math.pi * f * t) for f, amp in components)
        val += random.uniform(-noise_amp, noise_amp)
        return val

    return signal


def run_trial(dt, steps, target_present, target_amp, noise_amp):
    n_distractors = random.choice([1, 2])
    distractors = [
        (random.choice(DISTRACTOR_FREQS), random.uniform(0.3, 1.0))
        for _ in range(n_distractors)
    ]
    signal_fn = make_mixed_signal_fn(target_present, target_amp, distractors, noise_amp)

    resonator = Resonator("target", freq_hz=TARGET_FREQ, damping=0.02,
                           coupling=4.0e-4 * (2 * math.pi * TARGET_FREQ) ** 2)

    raw_samples = []
    for i in range(steps):
        t = i * dt
        drive = signal_fn(t)
        raw_samples.append(drive)
        resonator.step(drive, dt)

    resonator_energy = resonator.energy()
    raw_rms = math.sqrt(sum(s * s for s in raw_samples) / len(raw_samples))
    return resonator_energy, raw_rms


def calibrate_thresholds(dt, steps, noise_amp, n_calib=40):
    """Calibrate both detectors' thresholds using negative-only trials
    (target absent), same way you'd set a detection threshold in practice:
    pick a cutoff above the typical 'nothing of interest' noise floor."""
    res_vals, raw_vals = [], []
    for _ in range(n_calib):
        r, raw = run_trial(dt, steps, target_present=False, target_amp=0.0, noise_amp=noise_amp)
        res_vals.append(r)
        raw_vals.append(raw)
    res_thresh = (sum(res_vals) / len(res_vals)) * 2.5
    raw_thresh = (sum(raw_vals) / len(raw_vals)) * 1.3
    return res_thresh, raw_thresh


def run_benchmark(noise_amp, n_trials=120):
    dt = 1.0 / 40000
    steps = 2000  # 50ms windows

    res_thresh, raw_thresh = calibrate_thresholds(dt, steps, noise_amp)

    res_tp = res_fp = res_tn = res_fn = 0
    raw_tp = raw_fp = raw_tn = raw_fn = 0

    for _ in range(n_trials):
        target_present = random.random() < 0.5
        target_amp = random.uniform(0.5, 1.0) if target_present else 0.0
        res_energy, raw_rms = run_trial(dt, steps, target_present, target_amp, noise_amp)

        res_detected = res_energy > res_thresh
        raw_detected = raw_rms > raw_thresh

        if target_present and res_detected: res_tp += 1
        elif target_present and not res_detected: res_fn += 1
        elif not target_present and res_detected: res_fp += 1
        else: res_tn += 1

        if target_present and raw_detected: raw_tp += 1
        elif target_present and not raw_detected: raw_fn += 1
        elif not target_present and raw_detected: raw_fp += 1
        else: raw_tn += 1

    def stats(tp, fp, tn, fn):
        total = tp + fp + tn + fn
        acc = (tp + tn) / total
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        return acc, fpr, recall

    res_stats = stats(res_tp, res_fp, res_tn, res_fn)
    raw_stats = stats(raw_tp, raw_fp, raw_tn, raw_fn)
    return res_stats, raw_stats


def main():
    print(f"{'Noise':>6}   {'Detector':<12} {'Accuracy':>9} {'FalsePos%':>10} {'Recall':>8}")
    print("-" * 52)
    for noise_amp in [0.05, 0.2, 0.5]:
        random.seed(7)  # same trials across detectors/noise levels for fair comparison
        res_stats, raw_stats = run_benchmark(noise_amp)
        print(f"{noise_amp:>6.2f}   {'Resonator':<12} {res_stats[0]*100:>8.1f}% {res_stats[1]*100:>9.1f}% {res_stats[2]*100:>7.1f}%")
        print(f"{'':>6}   {'Raw-amp':<12} {raw_stats[0]*100:>8.1f}% {raw_stats[1]*100:>9.1f}% {raw_stats[2]*100:>7.1f}%")
        print()


if __name__ == "__main__":
    main()
