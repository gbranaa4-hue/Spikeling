#!/usr/bin/env python
"""
pyspike_neuron_models.py — REAL Izhikevich and AdEx neuron dynamics.

Checked before building this: core/compiler/compiler.py's grammar accepts
`type=Izhikevich` and `type=AdEx`, and comments in runtime.py reference
"LIF/Izhikevich/AdEx go in self.neurons" -- but the runtime only ever
implements LIF dynamics regardless of the declared type. Anyone specifying
those types today silently gets LIF behavior. This is that gap, actually
closed -- not wired into the DSL parser (a bigger, riskier change), but a
real, tested standalone implementation of both models' actual dynamics.

IZHIKEVICH (2003): two-variable model, v (membrane potential) and u
(recovery variable):
    v' = 0.04v^2 + 5v + 140 - u + I
    u' = a(bv - u)
    if v >= 30: v <- c, u <- u + d      (spike + reset)
Four parameters (a,b,c,d) reproduce different real cortical firing
patterns (regular spiking, chattering/bursting, fast spiking) -- this is
the WHOLE POINT of the model and what distinguishes it from LIF, which can
only ever produce uniform, non-adapting spikes.

ADEX (Brette & Gerstner 2005): adaptive exponential integrate-and-fire,
v (membrane potential) and w (adaptation variable):
    v' = (-(v-EL) + DeltaT*exp((v-VT)/DeltaT) - w + I) / C
    w' = (a(v-EL) - w) / tau_w
    if v >= threshold: v <- Vreset, w <- w + b   (spike + reset + adapt)
The adaptation variable w accumulates with each spike and suppresses
future firing -- spike-frequency adaptation, which LIF (constant leak,
no history-dependent term) cannot produce at all.

Verified below against the qualitative behavior the literature attributes
to each model (not just "produces some numbers") -- Izhikevich's
"chattering" parameters must burst, not fire uniformly; AdEx must show
spike-frequency adaptation (increasing inter-spike interval) under
constant current, which LIF must NOT show under the same constant current.

    python pyspike_neuron_models.py    # self-test
"""
import math


class IzhikevichNeuron:
    """a,b,c,d presets below are the ones from Izhikevich (2003) Table 1 --
    not invented, taken from the paper's own named regimes so "chattering"
    means the same thing here as in the literature."""

    PRESETS = {
        "regular_spiking":  dict(a=0.02, b=0.2, c=-65.0, d=8.0),
        "chattering":       dict(a=0.02, b=0.2, c=-50.0, d=2.0),
        "fast_spiking":     dict(a=0.10, b=0.2, c=-65.0, d=2.0),
        "intrinsically_bursting": dict(a=0.02, b=0.2, c=-55.0, d=4.0),
    }

    def __init__(self, preset: str = "regular_spiking", v0: float = -65.0):
        p = self.PRESETS[preset]
        self.a, self.b, self.c, self.d = p["a"], p["b"], p["c"], p["d"]
        self.v = v0
        self.u = self.b * self.v
        self.spike_log: list = []   # (t) of each spike

    def step(self, I: float, dt: float, t: float) -> bool:
        """Euler integration, sub-stepped (the model's fast nonlinearity
        needs a small dt to stay numerically stable -- 0.5ms substeps
        following the standard practice for this model, not 1ms raw)."""
        substeps = max(1, int(dt / 0.5))
        sub_dt = dt / substeps
        fired = False
        for _ in range(substeps):
            dv = 0.04 * self.v ** 2 + 5 * self.v + 140 - self.u + I
            du = self.a * (self.b * self.v - self.u)
            self.v += dv * sub_dt
            self.u += du * sub_dt
            if self.v >= 30.0:
                self.v = self.c
                self.u += self.d
                fired = True
                self.spike_log.append(t)
        return fired


class AdExNeuron:
    """Standard AdEx parameter set (Brette & Gerstner 2005, regular-spiking
    regime): C=200pF, gL=10nS, EL=-70mV, VT=-50mV, DeltaT=2mV,
    tau_w=30ms, a=2nS, b=0.06nA (60pA), Vreset=-58mV. Units are the
    original paper's; I is in the same pA-scale as b so a modest drive
    (a few hundred pA) produces a few Hz of adapting firing, matching
    published traces."""

    def __init__(self, C=200.0, gL=10.0, EL=-70.0, VT=-50.0, DeltaT=2.0,
                tau_w=30.0, a=2.0, b=60.0, Vreset=-58.0, spike_threshold=0.0):
        self.C, self.gL, self.EL, self.VT, self.DeltaT = C, gL, EL, VT, DeltaT
        self.tau_w, self.a, self.b, self.Vreset = tau_w, a, b, Vreset
        self.spike_threshold = spike_threshold
        self.v = EL
        self.w = 0.0
        self.spike_log: list = []

    def step(self, I: float, dt: float, t: float) -> bool:
        substeps = max(1, int(dt / 0.1))
        sub_dt = dt / substeps
        fired = False
        for _ in range(substeps):
            exp_term = self.DeltaT * math.exp(min(50.0, (self.v - self.VT) / self.DeltaT))
            dv = (-self.gL * (self.v - self.EL) + self.gL * exp_term - self.w + I) / self.C
            dw = (self.a * (self.v - self.EL) - self.w) / self.tau_w
            self.v += dv * sub_dt
            self.w += dw * sub_dt
            if self.v >= self.spike_threshold:
                self.v = self.Vreset
                self.w += self.b
                fired = True
                self.spike_log.append(t)
        return fired


# ─────────────────────────────────────────────────────────────────────────────
class LIFReference:
    """A minimal LIF, for direct qualitative contrast -- constant leak, no
    adaptation, no history-dependent slowdown. Independent of
    runtime.NeuronState so this file has no import dependency on the rest
    of the project; it's just the textbook LIF equation for comparison."""

    def __init__(self, threshold=1.0, leak=0.02, reset=0.0):
        self.threshold, self.leak, self.reset = threshold, leak, reset
        self.v = reset
        self.spike_log: list = []

    def step(self, I: float, dt: float, t: float) -> bool:
        self.v += (I - self.leak * self.v) * dt
        if self.v >= self.threshold:
            self.v = self.reset
            self.spike_log.append(t)
            return True
        return False


def _isis(spike_log: list) -> list:
    return [spike_log[i + 1] - spike_log[i] for i in range(len(spike_log) - 1)]


# ─────────────────────────────────────────────────────────────────────────────
def _selftest_izhikevich_chattering_bursts() -> None:
    """The 'chattering' preset must produce BURSTS (several spikes in
    rapid succession, separated by longer quiet gaps) -- not the uniform
    inter-spike intervals a regular_spiking preset (or LIF) produces under
    the same constant current. Bursting = high variance in ISI; uniform
    firing = low variance."""
    dt, T, I = 0.5, 300.0, 10.0
    t = 0.0
    chatter = IzhikevichNeuron("chattering")
    regular = IzhikevichNeuron("regular_spiking")
    while t < T:
        chatter.step(I, dt, t)
        regular.step(I, dt, t)
        t += dt

    isi_chatter = _isis(chatter.spike_log)
    isi_regular = _isis(regular.spike_log)
    cv_chatter = (max(isi_chatter) / min(isi_chatter)) if len(isi_chatter) > 2 else 0
    cv_regular = (max(isi_regular) / min(isi_regular)) if len(isi_regular) > 2 else 0

    ok = len(chatter.spike_log) > 5 and cv_chatter > cv_regular * 1.5
    print(f"    chattering: {len(chatter.spike_log)} spikes, ISI range "
          f"[{min(isi_chatter):.1f},{max(isi_chatter):.1f}], ratio={cv_chatter:.2f}")
    print(f"    regular_spiking: {len(regular.spike_log)} spikes, ISI range "
          f"[{min(isi_regular):.1f},{max(isi_regular):.1f}], ratio={cv_regular:.2f}")
    print(f"  [{'PASS' if ok else 'FAIL'}] Izhikevich 'chattering' preset shows real burst "
          f"structure (uneven ISI) that 'regular_spiking' does not -- genuinely different "
          f"dynamics from a uniform spike train, which LIF cannot produce at all")


def _selftest_adex_shows_spike_frequency_adaptation() -> None:
    """AdEx's inter-spike interval must INCREASE over the course of constant
    current injection (spike-frequency adaptation) -- LIF's must NOT (LIF
    has no adaptation variable, so under truly constant current its ISI is
    flat)."""
    dt, T, I = 0.1, 500.0, 400.0
    t = 0.0
    adex = AdExNeuron()
    lif = LIFReference(threshold=1.0, leak=0.005, reset=0.0)
    while t < T:
        adex.step(I, dt, t)
        lif.step(I * 0.0025, dt, t)   # scaled into LIF's own unit range
        t += dt

    isi_adex = _isis(adex.spike_log)
    isi_lif = _isis(lif.spike_log)
    adex_adapts = len(isi_adex) >= 3 and isi_adex[-1] > isi_adex[0] * 1.2
    lif_flat = len(isi_lif) >= 3 and abs(isi_lif[-1] - isi_lif[0]) < isi_lif[0] * 0.15

    print(f"    AdEx ISIs (first->last): {isi_adex[0]:.1f} -> {isi_adex[-1]:.1f} "
          f"({len(adex.spike_log)} spikes)")
    print(f"    LIF  ISIs (first->last): {isi_lif[0]:.1f} -> {isi_lif[-1]:.1f} "
          f"({len(lif.spike_log)} spikes)")
    ok = adex_adapts and lif_flat
    print(f"  [{'PASS' if ok else 'FAIL'}] AdEx shows real spike-frequency adaptation "
          f"(ISI grows under constant current) while LIF's ISI stays flat under the "
          f"same constant-current condition -- a real dynamical difference, not just "
          f"a relabeled LIF")


if __name__ == "__main__":
    print("=" * 78)
    print("  PYSPIKE NEURON MODELS -- real Izhikevich and AdEx dynamics")
    print("=" * 78)
    _selftest_izhikevich_chattering_bursts()
    print()
    _selftest_adex_shows_spike_frequency_adaptation()
