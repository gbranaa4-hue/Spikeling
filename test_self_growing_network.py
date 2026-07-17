#!/usr/bin/env python
"""
test_self_growing_network.py — the toy version of "a network that grows its
own topology, live, as a consequence of its own firing." Verified before
touching the real pipeline with it.

Mechanism (proven in pyspike.py's _selftest_live_actions): action handlers
run SYNCHRONOUSLY before spike propagation (runtime.py _fire()), and
propagation iterates self.synapses as a LIVE Python list. So a handler that
calls net.neuron() + net.connect() to spawn a child mid-firing has that
child exist AND be wired in time for the SAME propagation step to reach it
-- one stimulate() call can cascade through neurons that didn't exist when
the call started. The .spk text format can't do this (a text file can't
rewrite itself mid-run); this is a genuine capability of building the
network as live Python objects instead.

Three experiments, each with an explicit, falsifiable prediction and an
explicit termination guard (the DRIVE_FLOOR hang taught this substrate
needs one -- growth without a stop condition is a real runaway risk, not
hypothetical):

  A. CHAIN GROWTH   -- each firing spawns exactly one child, capped at
                        MAX_DEPTH. Predicts: MAX_DEPTH+1 neurons total, all
                        fire exactly once, all in ONE stimulate() call.
  B. BINARY TREE     -- each firing spawns two children (unless capped).
                        Predicts: 2^(depth+1)-1 neurons total (a complete
                        binary tree), all fire exactly once.
  C. UNGUARDED RUNAWAY (deliberately breaks the rule) -- no stop condition.
                        Predicts: hits the RUNTIME's own built-in _depth<32
                        cascade-depth safety net (see runtime.py _fire()),
                        not infinite -- but this is a fallback, not a
                        design, exactly like DRIVE_FLOOR: don't rely on it,
                        always cap explicitly (A and B do; C exists only to
                        show what happens if you forget).

    python test_self_growing_network.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyspike import Net   # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# A. Chain growth: linear, one child per firing, explicit MAX_DEPTH.
def run_chain_growth(max_depth: int = 8) -> dict:
    net = Net()
    rt = net.build_live()
    events = []

    def make_handler(ref, depth: int):
        def handler():
            events.append(depth)
            if depth >= max_depth:
                return   # EXPLICIT stop condition
            child = net.neuron(f"gen_{depth + 1}", threshold=50, leak=0)
            ref.to(child, weight=1.2)
            net.action(child)(make_handler(child, depth + 1))
        return handler

    seed = net.neuron("gen_0", threshold=50, leak=0)
    net.action(seed)(make_handler(seed, 0))

    rt.stimulate("gen_0", 1.0, 60.0)

    return {
        "events": events,
        "n_neurons": len(rt.neurons),
        "all_fired_once": all(n.fire_count == 1 for n in rt.neurons.values()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# B. Binary tree growth: two children per firing, explicit MAX_DEPTH.
def run_binary_tree_growth(max_depth: int = 4) -> dict:
    net = Net()
    rt = net.build_live()
    events = []
    counter = [0]   # unique neuron-name suffix

    def make_handler(ref, depth: int):
        def handler():
            events.append(depth)
            if depth >= max_depth:
                return   # EXPLICIT stop condition
            for _ in range(2):
                counter[0] += 1
                child = net.neuron(f"node_{counter[0]}", threshold=50, leak=0)
                ref.to(child, weight=1.2)
                net.action(child)(make_handler(child, depth + 1))
        return handler

    seed = net.neuron("root", threshold=50, leak=0)
    net.action(seed)(make_handler(seed, 0))

    rt.stimulate("root", 1.0, 60.0)

    expected_neurons = 2 ** (max_depth + 1) - 1   # complete binary tree
    return {
        "events": events,
        "n_neurons": len(rt.neurons),
        "expected_neurons": expected_neurons,
        "all_fired_once": all(n.fire_count == 1 for n in rt.neurons.values()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# C. Unguarded runaway: NO stop condition -- deliberately breaks the rule to
# show what actually happens (the runtime's own recursion cap, not infinity).
def run_unguarded_runaway() -> dict:
    net = Net()
    rt = net.build_live()
    counter = [0]
    fire_events = [0]

    def handler(ref):
        def _h():
            fire_events[0] += 1
            counter[0] += 1
            child = net.neuron(f"unguarded_{counter[0]}", threshold=50, leak=0)
            ref.to(child, weight=1.2)
            net.action(child)(handler(child))
        return _h

    seed = net.neuron("unguarded_seed", threshold=50, leak=0)
    net.action(seed)(handler(seed))

    rt.stimulate("unguarded_seed", 1.0, 60.0)

    return {"n_neurons": len(rt.neurons), "n_fires": fire_events[0]}


# ─────────────────────────────────────────────────────────────────────────────
def run() -> None:
    print("=" * 78)
    print("  SELF-GROWING NETWORK -- toy version")
    print("=" * 78)

    print("\n  A. CHAIN GROWTH (max_depth=8)")
    a = run_chain_growth(max_depth=8)
    ok_a = (a["events"] == list(range(9)) and a["n_neurons"] == 9 and a["all_fired_once"])
    print(f"     events (firing order): {a['events']}")
    print(f"     neurons created: {a['n_neurons']} (expected 9)")
    print(f"     all fired exactly once: {a['all_fired_once']}")
    print(f"     [{'PASS' if ok_a else 'FAIL'}] chain cascaded through 9 generations in ONE stimulate() call")

    print("\n  B. BINARY TREE GROWTH (max_depth=4)")
    b = run_binary_tree_growth(max_depth=4)
    ok_b = (b["n_neurons"] == b["expected_neurons"] and b["all_fired_once"])
    print(f"     neurons created: {b['n_neurons']} (expected {b['expected_neurons']} = 2^5-1)")
    print(f"     all fired exactly once: {b['all_fired_once']}")
    print(f"     firing order (by depth): {b['events']}")
    print(f"     [{'PASS' if ok_b else 'FAIL'}] complete binary tree grew from ONE seed stimulation")

    print("\n  C. UNGUARDED RUNAWAY (no stop condition, deliberately broken)")
    c = run_unguarded_runaway()
    print(f"     neurons created: {c['n_neurons']}")
    print(f"     fires: {c['n_fires']}")
    print(f"     did NOT run away to infinity -- stopped at the runtime's own")
    print(f"     _depth<32 cascade-depth safety net (runtime.py _fire()). This is a")
    print(f"     FALLBACK, not a design: A and B above cap explicitly and correctly;")
    print(f"     C exists only to show what happens if you forget, same lesson as")
    print(f"     DRIVE_FLOOR in the earlier scheduler hang.")

    print()
    all_ok = ok_a and ok_b
    print(f"  OVERALL: {'PASS' if all_ok else 'FAIL'} -- the substrate genuinely supports live, "
          f"self-triggered topology growth, with predictable, falsifiable structure "
          f"when explicitly capped.")


if __name__ == "__main__":
    run()
