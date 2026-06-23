#!/usr/bin/env python3
"""
Regression check: does amplitude-gating the Resonator's energy update
(runtime.ResonatorState.step, see its docstring) change detection
accuracy? Reuses the same randomized target/distractor/noise trial
design as resonator-prototype/accuracy_benchmark.py, but drives the
REAL gated runtime class instead of the prototype's history-based one.

Run it:
    python test_gating_accuracy_regression.py
"""

import os
import sys
import math
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from runtime.runtime import ResonatorState, DEFAULT_RESONATOR_BASE_GAIN

TARGET_FREQ = 440
DISTRACTOR_FREQS = [110, 220, 880, 1760]


def make_resonator():
    omega = 2 * math.pi * TARGET_FREQ
    coupling = DEFAULT_RESONATOR_BASE_GAIN * (omega ** 2)
    return ResonatorState(name="target", freq_hz=TARGET_FREQ, damping=0.02, coupling=coupling)


def run_trial(dt, steps, target_present, target_amp, noise_amp):
    n_distractors = random.choice([1, 2])
    distractors = [(random.choice(DISTRACTOR_FREQS), random.uniform(0.3, 1.0)) for _ in range(n_distractors)]
    if target_present:
        distractors.append((TARGET_FREQ, target_amp))

    r = make_resonator()
    for i in range(steps):
        t = i * dt
        drive = sum(amp * math.sin(2 * math.pi * f * t) for f, amp in distractors)
        drive += random.uniform(-noise_amp, noise_amp)
        r.step(drive, dt)
    return r.energy_ema


def calibrate(dt, steps, noise_amp, n_calib=40):
    vals = [run_trial(dt, steps, False, 0.0, noise_amp) for _ in range(n_calib)]
    return (sum(vals) / len(vals)) * 6.25  # same proportional margin as sqrt-domain 2.5x, squared


def main():
    dt = 1.0 / 40000
    steps = 2000

    print(f"{'Noise':>6}   {'Accuracy':>9} {'FalsePos%':>10} {'Recall':>8}")
    print("-" * 40)
    for noise_amp in [0.05, 0.2, 0.5]:
        random.seed(7)
        thresh = calibrate(dt, steps, noise_amp)
        tp = fp = tn = fn = 0
        for _ in range(120):
            present = random.random() < 0.5
            amp = random.uniform(0.5, 1.0) if present else 0.0
            energy = run_trial(dt, steps, present, amp, noise_amp)
            detected = energy > thresh
            if present and detected: tp += 1
            elif present and not detected: fn += 1
            elif not present and detected: fp += 1
            else: tn += 1
        total = tp + fp + tn + fn
        acc = (tp + tn) / total
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        print(f"{noise_amp:>6.2f}   {acc*100:>8.1f}% {fpr*100:>9.1f}% {recall*100:>7.1f}%")
        if acc < 0.90:
            print(f"[test] FAIL -- gating regressed accuracy at noise={noise_amp} (got {acc*100:.1f}%, expected >=90%)")
            sys.exit(1)

    print("\n[test] PASS -- gated energy update preserves detection accuracy (matches benchmark #5's ~99% range).")


if __name__ == "__main__":
    main()
