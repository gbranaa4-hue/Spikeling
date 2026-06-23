#!/usr/bin/env python3
"""
Benchmark: amplitude-gated Resonator energy update vs the original
always-compute version, at scale.

Claim being tested: skipping the expensive `x*x` multiply when a
resonator's amplitude is below the noise floor (see runtime.py's
ResonatorState.step docstring) saves real computation in a bank where
most channels are quiet most of the time -- the same dormancy idea
proven for NPC brains in dormant_vs_polling_heavy.c, applied to
resonator channels instead.

Setup: a bank of M resonator channels (e.g. a multi-band audio/sensor
analyzer), only a small number of which are ever "loud" (driven near
their resonance) at once -- everything else sees pure noise. Both
versions integrate the SAME oscillator mechanics every tick (x, v always
update -- a real signal could arrive on any channel at any time, so that
part can't be skipped). The only difference is whether the energy
update's multiply is gated.

Run it:
    python gated_vs_ungated_resonators.py
"""

import math
import random
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))
from runtime.runtime import ResonatorState, DEFAULT_RESONATOR_BASE_GAIN


def make_bank(channel_freqs):
    bank = []
    for f in channel_freqs:
        omega = 2 * math.pi * f
        coupling = DEFAULT_RESONATOR_BASE_GAIN * (omega ** 2)
        bank.append(ResonatorState(name=f"R{f}", freq_hz=f, damping=0.02, coupling=coupling))
    return bank


def step_ungated(r: ResonatorState, drive: float, dt: float):
    """Same math as ResonatorState.step but with gating forced off --
    i.e. the ORIGINAL always-compute behavior, for comparison."""
    omega = r.omega
    accel = -(omega ** 2) * r.x - 2 * r.damping * omega * r.v
    accel += r.coupling * drive
    r.v += accel * dt
    r.x += r.v * dt
    r.energy_ema += 0.01 * (r.x * r.x - r.energy_ema)  # always pays the multiply


def run_trial(n_channels, loud_fraction, ticks, gated: bool):
    freqs = [110 + i * 30 for i in range(n_channels)]  # spread across a band
    bank = make_bank(freqs)
    n_loud = max(1, int(n_channels * loud_fraction))
    loud_idx = set(random.sample(range(n_channels), n_loud))

    dt = 1.0 / 40000

    start = time.perf_counter()
    for t in range(ticks):
        time_s = t * dt
        for i, r in enumerate(bank):
            if i in loud_idx:
                drive = 1.0 * math.sin(2 * math.pi * r.freq_hz * time_s) + random.uniform(-0.05, 0.05)
            else:
                drive = random.uniform(-0.05, 0.05)  # noise only -- this channel stays quiet
            if gated:
                r.step(drive, dt)
            else:
                step_ungated(r, drive, dt)
    return time.perf_counter() - start


def main():
    ticks = 3000
    channel_counts = [16, 64, 256]
    loud_fractions = [0.02, 0.1, 0.3, 1.0]

    print(f"{'Channels':>9} {'%loud':>7} {'Ungated (s)':>13} {'Gated (s)':>11} {'Speedup':>9}")
    print("-" * 56)
    for n in channel_counts:
        for frac in loud_fractions:
            random.seed(11)
            t_ungated = run_trial(n, frac, ticks, gated=False)
            random.seed(11)
            t_gated = run_trial(n, frac, ticks, gated=True)
            speedup = t_ungated / t_gated if t_gated > 0 else float("inf")
            print(f"{n:>9} {frac*100:>6.0f}% {t_ungated:>13.4f} {t_gated:>11.4f} {speedup:>8.2f}x")
        print()


if __name__ == "__main__":
    main()
