#!/usr/bin/env python3
"""
The test the project was missing: comparing the Resonator detector
against REAL, established competitors, not a naive amplitude threshold.

Competitors:
  - Goertzel algorithm: the actual industry-standard technique for
    "detect one specific frequency in a signal" (this is what telephone
    systems use for DTMF tone detection). It's the fairest comparison
    there is for this exact task -- if Spikeling doesn't beat or at
    least match Goertzel, the resonator isn't pulling its weight versus
    known DSP technique, regardless of how it does against a strawman.
  - FFT-based detection: full spectrum, look at the magnitude in the
    target frequency's bin. More general-purpose than Goertzel (you get
    every frequency, not just one), included for context.

Same trial design as accuracy_benchmark.py (target tone present/absent,
1-2 random distractor tones, broadband noise) so the comparison is
apples-to-apples with the previously reported 99.2% / 65% numbers.

Measures BOTH accuracy and computational cost -- a method that's only
as accurate as Goertzel but slower isn't a win, and vice versa.

Run it:
    python vs_established_techniques.py
"""

import math
import random
import time

import numpy as np

from resonator_bank import Resonator

TARGET_FREQ = 440
DISTRACTOR_FREQS = [110, 220, 880, 1760]
SAMPLE_RATE = 40000
WINDOW = 2000  # samples per detection window, matches the resonator's evaluation window


def make_signal(steps, dt, target_present, target_amp, distractors, noise_amp):
    samples = np.zeros(steps)
    components = list(distractors)
    if target_present:
        components.append((TARGET_FREQ, target_amp))
    t = np.arange(steps) * dt
    for f, amp in components:
        samples += amp * np.sin(2 * np.pi * f * t)
    samples += np.random.uniform(-noise_amp, noise_amp, steps)
    return samples


def goertzel_magnitude(samples, target_freq, sample_rate):
    """Standard Goertzel algorithm -- O(N) per window, 2 multiplies + 2
    adds per sample, recursive (same computational character as the
    resonator). This is the real competitor."""
    N = len(samples)
    k = int(0.5 + N * target_freq / sample_rate)
    omega = 2 * math.pi * k / N
    coeff = 2 * math.cos(omega)
    s_prev, s_prev2 = 0.0, 0.0
    for sample in samples.tolist():  # see fast_resonator_energy's comment -- same fix, for a fair comparison
        s = sample + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s
    power = s_prev2 ** 2 + s_prev ** 2 - coeff * s_prev * s_prev2
    return math.sqrt(max(power, 0.0)) / N


def fft_magnitude(samples, target_freq, sample_rate):
    N = len(samples)
    spectrum = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(N, d=1.0 / sample_rate)
    idx = np.argmin(np.abs(freqs - target_freq))
    return np.abs(spectrum[idx]) / N


def resonator_energy(samples, dt):
    omega = 2 * math.pi * TARGET_FREQ
    r = Resonator("target", freq_hz=TARGET_FREQ, damping=0.02, coupling=4.0e-4 * (omega ** 2))
    for s in samples:
        r.step(float(s), dt)
    return r.energy()


def fast_resonator_energy(samples, target_freq, damping, dt):
    """Same physics as Resonator.step()/energy() above, rewritten as a
    tight loop with local variables instead of object attribute lookups,
    no growing history list, and omega^2 / 2*damping*omega precomputed
    once instead of recomputed every sample -- the same style of
    optimization Goertzel's loop already has. Whole-window mean-square
    energy (matches what Goertzel/FFT compute over the same window) in
    place of the original's last-200-samples slice, so all three methods
    are looking at an equivalent amount of signal."""
    omega = 2 * math.pi * target_freq
    omega2 = omega * omega
    coupling = 4.0e-4 * omega2
    two_damping_omega = 2.0 * damping * omega
    x = 0.0
    v = 0.0
    sumsq = 0.0
    # .tolist() up front: iterating a numpy array directly yields
    # np.float64 scalars, whose arithmetic goes through numpy's ufunc
    # dispatch -- slower than native Python floats for this kind of
    # tight scalar loop. This single line is what actually closes most
    # of the gap below; the manual-loop rewrite alone didn't.
    for drive in samples.tolist():
        accel = -omega2 * x - two_damping_omega * v + coupling * drive
        v += accel * dt
        x += v * dt
        sumsq += x * x
    return math.sqrt(sumsq / len(samples))


def calibrate(method_fn, dt, steps, noise_amp, n_calib=30):
    vals = []
    for _ in range(n_calib):
        samples = make_signal(steps, dt, False, 0.0, [
            (random.choice(DISTRACTOR_FREQS), random.uniform(0.3, 1.0))
            for _ in range(random.choice([1, 2]))
        ], noise_amp)
        vals.append(method_fn(samples))
    return (sum(vals) / len(vals)) * 2.5


def run_comparison(noise_amp, n_trials=80):
    dt = 1.0 / SAMPLE_RATE
    methods = {
        "Resonator": lambda s: resonator_energy(s, dt),
        "Resonator(fast)": lambda s: fast_resonator_energy(s, TARGET_FREQ, 0.02, dt),
        "Goertzel": lambda s: goertzel_magnitude(s, TARGET_FREQ, SAMPLE_RATE),
        "FFT": lambda s: fft_magnitude(s, TARGET_FREQ, SAMPLE_RATE),
    }

    thresholds = {name: calibrate(fn, dt, WINDOW, noise_amp) for name, fn in methods.items()}

    stats = {name: {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "time": 0.0} for name in methods}

    for _ in range(n_trials):
        present = random.random() < 0.5
        amp = random.uniform(0.5, 1.0) if present else 0.0
        distractors = [
            (random.choice(DISTRACTOR_FREQS), random.uniform(0.3, 1.0))
            for _ in range(random.choice([1, 2]))
        ]
        samples = make_signal(WINDOW, dt, present, amp, distractors, noise_amp)

        for name, fn in methods.items():
            t0 = time.perf_counter()
            value = fn(samples)
            stats[name]["time"] += time.perf_counter() - t0

            detected = value > thresholds[name]
            s = stats[name]
            if present and detected: s["tp"] += 1
            elif present and not detected: s["fn"] += 1
            elif not present and detected: s["fp"] += 1
            else: s["tn"] += 1

    results = {}
    for name, s in stats.items():
        total = s["tp"] + s["fp"] + s["tn"] + s["fn"]
        acc = (s["tp"] + s["tn"]) / total
        fpr = s["fp"] / (s["fp"] + s["tn"]) if (s["fp"] + s["tn"]) else 0.0
        recall = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) else 0.0
        avg_time_us = (s["time"] / n_trials) * 1e6
        results[name] = (acc, fpr, recall, avg_time_us)
    return results


def main():
    print(f"{'Noise':>6}   {'Method':<10} {'Accuracy':>9} {'FalsePos%':>10} {'Recall':>8} {'Time/trial':>11}")
    print("-" * 64)
    for noise_amp in [0.05, 0.2, 0.5]:
        random.seed(7)
        np.random.seed(7)
        results = run_comparison(noise_amp)
        for name in ["Resonator", "Resonator(fast)", "Goertzel", "FFT"]:
            acc, fpr, recall, time_us = results[name]
            print(f"{noise_amp:>6.2f}   {name:<10} {acc*100:>8.1f}% {fpr*100:>9.1f}% {recall*100:>7.1f}% {time_us:>9.2f}us")
        print()


if __name__ == "__main__":
    main()
