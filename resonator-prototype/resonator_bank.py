#!/usr/bin/env python3
"""
Resonator bank prototype for Spikeling.

Instead of LIF neurons (charge-and-fire), each "neuron" here is a damped
harmonic oscillator tuned to its own natural frequency. A mixed input
signal drives all of them at once, in parallel, on one timeline -- each
resonator only builds up amplitude when the input contains energy near its
own frequency. That's the "resonant cavity coupling" idea: many channels
sharing one medium, separated by frequency rather than by time-slicing.

Practical framing: this is a software analog filterbank built out of
neuron-like primitives, so it slots into Spikeling as a new neuron type
(`type=Resonator`) usable anywhere LIF is today -- e.g. signal_detector.spk,
sound_localizer.spk, or the FPS enemy "hearing" sense.

Run it:
    python resonator_bank.py
"""

import math
import random


class Resonator:
    """A single damped harmonic oscillator neuron.

    State: position (x) and velocity (v). Driven by an external input
    force each tick. Natural frequency + damping determine which inputs
    it resonates with.
    """

    def __init__(self, name, freq_hz, damping=0.05, coupling=0.0):
        self.name = name
        self.omega = 2 * math.pi * freq_hz   # natural angular frequency
        self.damping = damping
        self.coupling = coupling             # how strongly it reacts to drive signal
        self.x = 0.0
        self.v = 0.0
        self.history = []

    def step(self, drive, dt):
        # damped harmonic oscillator: x'' = -omega^2 * x - 2*damping*omega*v + coupling*drive
        # semi-implicit (symplectic) Euler: update v first, then use the NEW v
        # to update x. Far more numerically stable than plain Euler for
        # oscillators, especially at higher frequencies relative to dt.
        accel = -(self.omega ** 2) * self.x - 2 * self.damping * self.omega * self.v
        accel += self.coupling * drive
        self.v += accel * dt
        self.x += self.v * dt
        self.history.append(self.x)

    def energy(self):
        # amplitude-ish measure: RMS of recent history (last ~1 period worth)
        n = min(len(self.history), 200)
        if n == 0:
            return 0.0
        recent = self.history[-n:]
        return math.sqrt(sum(v * v for v in recent) / n)


def make_test_signal(t, components, noise=0.05):
    """A mixed signal = sum of sine waves at given frequencies + noise."""
    val = sum(amp * math.sin(2 * math.pi * f * t) for f, amp in components)
    val += random.uniform(-noise, noise)
    return val


def run_demo():
    # Stability of the symplectic-Euler integrator requires omega*dt <~ 2.
    # Highest bank frequency is 1760Hz -> omega ~= 11058 rad/s, so dt must be
    # well under ~1.8e-4s. 40kHz sim rate keeps a comfortable margin.
    dt = 1.0 / 40000
    duration = 0.5         # seconds
    steps = int(duration / dt)

    # Practical use case: a "signal detector" bank, like signal_detector.spk,
    # but each channel is a literal resonator instead of a thresholded LIF unit.
    #
    # GAIN NORMALIZATION: a driven damped oscillator's steady-state amplitude
    # at resonance is ~= coupling / (2*damping*omega^2). Left uncorrected,
    # high-frequency channels respond far weaker than low-frequency ones for
    # the same coupling constant (that's what the first prototype run showed
    # -- 1760Hz was invisible next to 440Hz). Scaling coupling by omega^2
    # cancels that out so every channel in the bank has comparable gain at
    # its own resonance peak, regardless of frequency.
    damping = 0.02
    base_gain = 4.0e-4          # tuned so resulting coupling values stay numerically sane
    bank_freqs = [110, 220, 440, 880, 1760]   # Hz -- one octave apart
    bank = []
    for f in bank_freqs:
        omega = 2 * math.pi * f
        coupling = base_gain * (omega ** 2)
        bank.append(Resonator(f"R{f}Hz", freq_hz=f, damping=damping, coupling=coupling))

    # The actual signal hitting the bank only contains energy at 440Hz and 1760Hz,
    # plus noise -- like two of five possible "events" actually occurring.
    active_freqs = [(440, 1.0), (1760, 0.6)]

    for i in range(steps):
        t = i * dt
        drive = make_test_signal(t, active_freqs, noise=0.1)
        for r in bank:
            r.step(drive, dt)

    print(f"Signal contains energy at: {[f for f, _ in active_freqs]} Hz\n")
    print(f"{'Resonator':<10} {'Energy':>14}   Detected?")
    print("-" * 40)
    energies = [(r.name, r.energy()) for r in bank]
    threshold = sum(e for _, e in energies) / len(energies) * 1.5  # adaptive-ish
    for name, e in energies:
        detected = "YES" if e > threshold else "  -"
        print(f"{name:<10} {e:>14.8f}   {detected}")

    print(f"\n(threshold = {threshold:.8f}, set relative to mean energy across the bank)")
    print("This is the parallel part: all 5 resonators integrate the SAME input")
    print("stream simultaneously, on one timeline, and separate out frequency")
    print("content without any FFT or sequential filtering pass.")


if __name__ == "__main__":
    run_demo()
