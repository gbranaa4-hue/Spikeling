# SSH-Resonator reservoir — bridge from the topological-phononics study

A bridge experiment connecting this project's `Resonator` neuron to the
[topological-phononics study](https://github.com/gbranaa4-hue/topological-phononics)
(doi:[10.5281/zenodo.21305151](https://doi.org/10.5281/zenodo.21305151)).

`ssh_resonator_bridge.py` imports Spikeling's **real** `ResonatorState` and wires `M` of them into
an **SSH-coupled chain** — an *extension*, since the runtime normally drives resonators independently
(a frequency-detector bank, no resonator→resonator coupling). It then runs the same pre-registered
robustness tests as the phononic study.

```bash
python ssh_resonator_bridge.py
```

## What it found (2026-07-10)

| test | result |
|---|---|
| **capability** | recalls `u[t-1..3]` at NMSE ~0.40–0.50 — a weak but non-vacuous fading-memory reservoir (a linear oscillator chain + x² readout) |
| **A) defect / topology** | **inconclusive** — topological vs trivial frozen-readout penalty: win-rate 60%, 95% CI 35–85% (n=15); median 2.3× lower but CI spans 50%. Fragile, matching the phononic firm-up. |
| **B) noise / rank** | **confirmed** — the trained decoder cancels **structured** (low-rank, correlated) noise *exactly* (NMSE = clean) while **random** (full-rank) noise climbs |

## Takeaway

What transfers from the phononic work is the **noise/rank result** — a *substrate-independent* decoder
fact: correlated/structured noise across a population is cancellable by the trained readout; only
per-unit uncorrelated noise sets the floor (margin grows with population size). The **topology-specific**
defect-tolerance does **not** cleanly transfer (fragile in both substrates).

This is the natural next pre-registration for the `sr_*` / `noise_sweet_spot` / `population_coding`
experiments in this folder: split injected noise into **structured vs random**, and over-provision
units for cancellation margin.

*Honest scope:* a weak reservoir, small samples (n=15 for the defect test), and an extension of the
Resonator (not current runtime behavior). A first probe, not a verdict.
