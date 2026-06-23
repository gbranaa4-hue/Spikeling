# research — Stochastic Resonance

A separate investigation thread, independent of the core DSL/runtime work:
does injecting noise at inference time improve a classifier's accuracy on
borderline/near-threshold examples? (Stochastic resonance is a real
phenomenon in neuroscience where a bit of noise can help a neuron detect a
weak signal — this tests whether the same trick helps ML inference.)

## Files
- `sr_experiment.py` — baseline experiment: fixed noise levels vs no noise.
- `sr_learnable.py` — a meta-network that predicts the optimal noise σ*(x) per input, instead of using a fixed noise level.
- `sr_results.json`, `sr_neural_results.json`, `sr_feature_noise_results.json`, `sr_learnable_results.json` — recorded results from the above experiments.
- `noise_sweet_spot.py` — small visualization/demo of neuromorphic threshold + refractory filtering.

## Status
Exploratory, dated 6/15–6/16 (older than the rest of the project). Results
were inconclusive — the learned noise level σ* tended to collapse toward
zero, suggesting limited benefit on the tested (well-separated) data. Not
integrated into `core/` or any of the apps.
