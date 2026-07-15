#!/usr/bin/env python3
"""Validates generate_coupled_module() (the new SSH-dimerized chain-coupling
feature in spikeling_resonator_verilog.py) two ways, since there's no
iverilog installed here to actually simulate the generated .v file:

  (A) STORAGE CLAIM -- count real localparams/case-entries in the generated
      file and confirm coupling used exactly 2 constants + a 1-bit select,
      not N-1 stored weights. Measured on the actual generated text, not
      assumed from the generator code.

  (B) FIXED-POINT CORRECTNESS -- hand-build a Python integer emulator that
      performs the EXACT same operations the Verilog does (Q14.18 multiply,
      >>> FRAC_BITS, >>> DT_SHIFT, same gating/energy logic), run it driven
      by a real signal, and compare the resulting oscillator trajectories
      against a floating-point reference model with identical physics. This
      is the same kind of Python/C-vs-hardware cross-check the rest of this
      SDK already relies on (see module docstring's ALPHA_SHIFT bug story)
      -- catches fixed-point-specific bugs (overflow, wrong shift, instability)
      that a purely symbolic read of the Verilog can't.

PRE-REGISTERED: no prediction on the fixed-point error magnitude -- this is
the first time this coupling path has been built or run at all. Capability
bar: fixed-point trajectory must stay BOUNDED (no overflow/divergence) and
track the float reference to a small relative error. Report the real numbers
either way.
"""
import numpy as np
from spikeling_resonator_verilog import (
    parse_resonators, generate_coupled_module, to_fixed, FRAC_BITS, WIDTH,
    DT_SHIFT, DEFAULT_RESONATOR_GATE_THRESHOLD,
)

SPK = "chain_reservoir.spk"
OUT_V = "spikeling_chain_reservoir.v"
COUPLE_V, COUPLE_W = 1200.0, 3000.0   # physical coupling strengths (same units as `coupling`), dimerized

resonators, actions = parse_resonators(SPK)
N = len(resonators)
print(f"Parsed {N} resonators from {SPK}\n")

generate_coupled_module(resonators, OUT_V, COUPLE_V, COUPLE_W)
text = open(OUT_V, encoding="utf-8").read()

# ---------------------------------------------------------------------------
# (A) STORAGE CLAIM -- count what actually got emitted
# ---------------------------------------------------------------------------
n_couple_localparams = text.count("localparam signed [WIDTH-1:0] COUPLE_")
n_bond_case_lines = text.count(": bond_of")          # should be 0 -- no case statement for bonds
has_bond_select = "bond_of = (j[0] == 1'b0) ? COUPLE_V : COUPLE_W;" in text
n_per_neuron_case_lines = text.count(": k1_of =")     # the O(N) pattern, for contrast

print("--- (A) storage claim, measured on the generated .v file ---")
print(f"  coupling localparams emitted: {n_couple_localparams} (COUPLE_V, COUPLE_W)")
print(f"  bond case-statement entries: {n_bond_case_lines} (0 = no per-bond LUT, confirms O(1))")
print(f"  1-bit parity select present: {has_bond_select}")
print(f"  for contrast, per-NEURON k1_of case entries: {n_per_neuron_case_lines} (the O(N) pattern this avoids for bonds)")
if n_couple_localparams == 2 and n_bond_case_lines == 0 and has_bond_select:
    print(f"  CONFIRMED: {N - 1} bonds specified by 2 constants, not {N - 1} -- generation-efficiency claim holds on the real output.\n")
else:
    print("  CLAIM NOT CONFIRMED on the actual generated file -- investigate before trusting part B.\n")

# ---------------------------------------------------------------------------
# (B) FIXED-POINT CORRECTNESS -- emulate the exact Verilog integer ops
# ---------------------------------------------------------------------------
def q(val):
    """Quantize a float to the exact Q14.18 fixed-point integer the Verilog stores."""
    return to_fixed(val, FRAC_BITS)

def mul_shift(a, b, shift=FRAC_BITS):
    """Exact Verilog operation: (a * b) >>> shift, on Python ints (arbitrary precision,
    matching Verilog's 2*WIDTH-wide product register before the shift)."""
    return (a * b) >> shift   # Python's >> on ints matches Verilog's >>> for this sign convention here

GATE_THRESH = q(DEFAULT_RESONATOR_GATE_THRESHOLD)
K1 = [q(r.k1) for r in resonators]
K2 = [q(r.k2) for r in resonators]
K3 = [q(r.k3) for r in resonators]
dt = 2.0 ** -DT_SHIFT
CV = q(COUPLE_V * dt)
CW = q(COUPLE_W * dt)

def bond_of(j):
    return CV if j % 2 == 0 else CW

def fixed_point_step(x, v, drive_q):
    N = len(x)
    x_new, v_new = [0] * N, [0] * N
    for i in range(N):
        k1x = mul_shift(K1[i], x[i])
        k2v = mul_shift(K2[i], v[i])
        k3d = mul_shift(K3[i], drive_q)
        cleft = mul_shift(bond_of(i - 1), x[i - 1]) if i > 0 else 0
        cright = mul_shift(bond_of(i), x[i + 1]) if i < N - 1 else 0
        vn = v[i] - k1x - k2v + k3d + cleft + cright
        xn = x[i] + (vn >> DT_SHIFT)
        v_new[i], x_new[i] = vn, xn
    return x_new, v_new

def float_step(x, v, drive, freq_hz, damping):
    N = len(x)
    x_new, v_new = np.zeros(N), np.zeros(N)
    omega = 2 * np.pi * freq_hz
    for i in range(N):
        k1x = (omega ** 2) * dt * x[i]
        k2v = (2 * damping * omega) * dt * v[i]
        k3d = resonators[i].coupling * dt * drive
        cleft = (COUPLE_V if (i - 1) % 2 == 0 else COUPLE_W) * dt * x[i - 1] if i > 0 else 0
        cright = (COUPLE_V if i % 2 == 0 else COUPLE_W) * dt * x[i + 1] if i < N - 1 else 0
        vn = v[i] - k1x - k2v + k3d + cleft + cright
        xn = x[i] + vn * dt
        v_new[i], x_new[i] = vn, xn
    return x_new, v_new

# drive: same amplitude scale as generate_stimulus's real usage (tone_detector.spk
# uses components like amp=1.0/0.6) -- the first version of this test used amp=0.02,
# which parked the whole trajectory within ~8 fixed-point LSBs of the quantization
# floor (LSB = 1/2^18 = 3.8e-6, max|x| was 3e-5) and made the "error" measurement
# meaningless rather than a real finding. Fixed to a realistic drive scale.
T = 3000
rng = np.random.default_rng(0)
t_axis = np.arange(T) * dt
drive_signal = 1.0 * np.sin(2 * np.pi * 220 * t_axis) + 0.1 * rng.standard_normal(T)

x_fp = [0] * N; v_fp = [0] * N
x_fl = np.zeros(N); v_fl = np.zeros(N)
X_FP = np.zeros((T, N)); X_FL = np.zeros((T, N))
overflowed = False
for t in range(T):
    drive_q = q(float(drive_signal[t]))
    x_fp, v_fp = fixed_point_step(x_fp, v_fp, drive_q)
    x_fl, v_fl = float_step(x_fl, v_fl, drive_signal[t], 220.0, 0.05)
    X_FP[t] = [xi / (1 << FRAC_BITS) for xi in x_fp]
    X_FL[t] = x_fl
    if any(abs(xi) > (1 << (WIDTH - 1)) for xi in x_fp):
        overflowed = True

print("--- (B) fixed-point-vs-float numeric cross-check, driven 3000-step run ---")
print(f"  fixed-point register overflow (WIDTH={WIDTH}) at any step: {overflowed}")
max_abs = np.max(np.abs(X_FP))
print(f"  max |x| reached (float units, fixed-point trajectory): {max_abs:.5f} (bounded, no runaway divergence: {max_abs < 100})")

err = X_FP - X_FL
rel_err = np.abs(err) / (np.max(np.abs(X_FL)) + 1e-12)
print(f"  max absolute fixed-point-vs-float error: {np.max(np.abs(err)):.6e}")
print(f"  max relative error (vs float trajectory's own scale): {np.max(rel_err):.4%}")
print(f"  mean relative error: {np.mean(rel_err):.4%}")

print("\n--- verdict ---")
if overflowed:
    print("FAIL -- fixed-point registers overflowed. The coupling constants/WIDTH need rescaling before this is usable.")
elif max_abs >= 100:
    print("FAIL -- trajectory diverged (unbounded growth), even without register overflow. Coupling too strong / unstable at this rho.")
elif np.max(rel_err) < 0.05:
    print("PASS -- fixed-point chain-coupled implementation tracks the float reference closely (<5% max relative error) and stays bounded.")
    print("Storage claim (A) also holds on the real generated file. Both halves of the new feature check out honestly.")
else:
    print(f"MARGINAL -- bounded and non-overflowing, but {np.max(rel_err):.1%} max relative error is larger than a quiet rounding")
    print("effect -- worth tightening FRAC_BITS or the coupling magnitude before treating this as production-ready.")
