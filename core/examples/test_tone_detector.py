#!/usr/bin/env python3
"""
End-to-end test of the Resonator neuron type through the REAL DSL
pipeline: tone_detector.spk -> compiler.compile_file -> SpikelingRuntime
-> step_resonators(). This is the integration the standalone prototype
(resonator-prototype/) never had -- proving the resonator model works
when driven through the actual compiler/runtime, not just a one-off
script.

Scenario: mirrors resonator-prototype/accuracy_benchmark.py -- a mixed
signal containing the 440Hz and 1760Hz tones (plus noise), fed through
a 5-channel resonator bank compiled from tone_detector.spk. Only the
440Hz and 1760Hz channels should fire their actions.

Run it:
    python test_tone_detector.py
"""

import os
import sys
import math
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from compiler.compiler import compile_file
from runtime.runtime import SpikelingRuntime


def main():
    spk_path = os.path.join(os.path.dirname(__file__), "tone_detector.spk")
    ast = compile_file(spk_path, output_dir=os.path.dirname(spk_path))
    rt = SpikelingRuntime(ast)

    fired_log = []
    for action in ast.actions:
        cmd = action.command
        rt.register_handler(cmd, lambda c=cmd: fired_log.append(c))

    print(f"[test] loaded {len(rt.resonators)} resonator neurons from {spk_path}")
    assert len(rt.resonators) == 5, "expected 5 resonator neurons from tone_detector.spk"

    # Mixed signal: 440Hz (strong) + 1760Hz (weaker) + noise -- same
    # scenario as the standalone accuracy benchmark.
    dt = 1.0 / 40000
    steps = 2000
    active_freqs = [(440, 1.0), (1760, 0.6)]

    for i in range(steps):
        t = i * dt
        drive = sum(amp * math.sin(2 * math.pi * f * t) for f, amp in active_freqs)
        drive += random.uniform(-0.1, 0.1)
        rt.step_resonators(drive, dt, current_time_ms=t * 1000.0)

    detected = sorted(set(fired_log))
    print(f"[test] actions fired: {detected}")
    print(rt.state_report())

    expected = {"TONE_440HZ", "TONE_1760HZ"}
    unexpected = set(detected) - expected
    missing = expected - set(detected)

    if missing:
        print(f"[test] FAIL — missing expected detections: {missing}")
        sys.exit(1)
    if unexpected:
        print(f"[test] FAIL — unexpected false-positive detections: {unexpected}")
        sys.exit(1)

    print("[test] PASS — Resonator neuron type correctly detected 440Hz and 1760Hz "
          "through the real compiler/runtime pipeline, with no false positives "
          "on the 110/220/880Hz channels.")


if __name__ == "__main__":
    main()
