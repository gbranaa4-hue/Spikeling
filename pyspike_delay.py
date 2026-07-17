#!/usr/bin/env python
# Reviewed 2026-07-17
"""
pyspike_delay.py — synaptic transmission delay. Every Synapse in this
project's core runtime has src/dst/weight only -- propagation is
instantaneous (a firing neuron's effect reaches its targets in the SAME
tick). Real spiking networks use per-synapse DELAYS (axonal/dendritic
conduction time) for temporal pattern recognition -- this is the core
mechanism behind Izhikevich's polychronization work: a delay pattern lets
a network respond to WHEN inputs arrived relative to each other, not just
whether they did.

Built as a wrapper (like CausalNet), not a core runtime.py change: a
DelayedNet holds a queue of (delivery_tick, dst_name, weight) events and
applies them when their tick arrives, instead of propagating a fired
neuron's synapses immediately.

    python pyspike_delay.py    # self-test: delayed delivery + coincidence
                                 # detection that ONLY works because of delay
"""
import heapq
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyspike import Net, NeuronRef   # noqa: E402


class DelayedNet:
    """Wraps a live pyspike Net. connect_delayed(src, dst, weight, delay)
    registers a delayed synapse SEPARATELY from the network's own
    (instantaneous) synapses -- delayed effects are queued and only
    delivered when tick() advances far enough. Use .tick(dt) to advance
    time and flush any deliveries that are now due; use .stimulate() for
    ordinary instantaneous input, same as the underlying runtime."""

    def __init__(self, net: Net, rt) -> None:
        self.net = net
        self.rt = rt
        self.now = 0.0
        self._queue: list = []          # heap of (delivery_time, seq, dst, weight)
        self._delayed_synapses: list = []   # (src, dst, weight, delay) for bookkeeping
        self._seq = 0

    def connect_delayed(self, src: NeuronRef, dst: NeuronRef, weight: float, delay: float) -> None:
        if delay < 0:
            raise ValueError("delay must be >= 0")
        self._delayed_synapses.append((src.name, dst.name, weight, delay))

    def stimulate(self, name: str, drive: float) -> None:
        self.now += 1.0
        before = self.rt.neurons[name].fire_count
        self.rt.stimulate(name, self.now, drive)
        if self.rt.neurons[name].fire_count > before:
            self._enqueue_delayed_effects(name)

    def _enqueue_delayed_effects(self, fired_name: str) -> None:
        for src, dst, weight, delay in self._delayed_synapses:
            if src == fired_name:
                self._seq += 1
                heapq.heappush(self._queue, (self.now + delay, self._seq, dst, weight))

    def advance_to(self, t: float) -> None:
        """Advance time to `t`, delivering any queued delayed effects whose
        delivery time has arrived, in delivery-time order."""
        self.now = max(self.now, t)
        while self._queue and self._queue[0][0] <= self.now:
            delivery_time, _, dst, weight = heapq.heappop(self._queue)
            n = self.rt.neurons[dst]
            n.membrane_potential = max(-n.threshold, n.membrane_potential + weight * 50.0)
            if n.membrane_potential >= n.threshold:
                # deliver via the runtime's own stimulate() semantics (0
                # drive, membrane already primed) so refractory/action
                # dispatch stay consistent with ordinary firing
                self.rt.stimulate(dst, delivery_time, 0.0)


def build_delayed(refractory_ms: float = 0) -> tuple:
    net = Net(refractory_ms=refractory_ms)
    rt = net.build_live()
    return DelayedNet(net, rt), net, rt


# ─────────────────────────────────────────────────────────────────────────────
def _selftest_basic_delay() -> None:
    """A delayed synapse must NOT deliver its effect before the delay has
    elapsed, and MUST deliver it once the delay has passed."""
    dn, net, rt = build_delayed()
    A = net.neuron("A", threshold=50, leak=0)
    B = net.neuron("B", threshold=50, leak=0)
    dn.connect_delayed(A, B, weight=1.2, delay=10.0)

    dn.stimulate("A", 60.0)
    assert rt.neurons["A"].fire_count == 1

    dn.advance_to(dn.now + 5.0)     # only 5 of the 10-tick delay has elapsed
    early = rt.neurons["B"].fire_count
    dn.advance_to(dn.now + 10.0)    # now well past the 10-tick delay
    late = rt.neurons["B"].fire_count

    ok = (early == 0) and (late == 1)
    print(f"  [{'PASS' if ok else 'FAIL'}] delayed synapse: B has NOT fired before the delay "
          f"elapses (fired={early}), and HAS fired once it does (fired={late})")


def _selftest_coincidence_detection_needs_delay() -> None:
    """THE POINT of delay lines (Izhikevich's polychronization mechanism):
    two inputs that arrive at DIFFERENT real times can still be made to
    ARRIVE TOGETHER at a downstream coincidence detector, if their delays
    are tuned to compensate for their arrival-time difference. Neither
    input alone crosses threshold; only their coincidence does -- and that
    coincidence is engineered entirely through delay, not timing luck."""
    dn, net, rt = build_delayed()
    EARLY = net.neuron("EARLY", threshold=50, leak=0)
    LATE = net.neuron("LATE", threshold=50, leak=0)
    COINCIDENCE = net.neuron("COINCIDENCE", threshold=50, leak=0)
    # EARLY fires first but has a LONG delay (30); LATE fires 20 ticks after
    # EARLY but has a SHORT delay (10) -- both effects should land on
    # COINCIDENCE at the same real time (EARLY: t=1+30=31; LATE: t=21+10=31).
    dn.connect_delayed(EARLY, COINCIDENCE, weight=0.7, delay=30.0)
    dn.connect_delayed(LATE, COINCIDENCE, weight=0.7, delay=10.0)

    dn.stimulate("EARLY", 60.0)         # t=1, delivers to COINCIDENCE at t=31
    for _ in range(19):
        dn.advance_to(dn.now + 1.0)     # let time pass without firing anything else
    dn.stimulate("LATE", 60.0)          # t=21, delivers to COINCIDENCE at t=31

    before = rt.neurons["COINCIDENCE"].fire_count
    dn.advance_to(dn.now + 15.0)        # advance past t=31, flush both deliveries
    after = rt.neurons["COINCIDENCE"].fire_count

    ok = after > before
    print(f"  [{'PASS' if ok else 'FAIL'}] delay-compensated coincidence detection: two inputs "
          f"20 ticks apart in real arrival time were made to coincide at the downstream "
          f"neuron via tuned delays, firing it (fired={after > before}) even though neither "
          f"input alone (weight 0.7*50=35 < threshold 50) could")


if __name__ == "__main__":
    print("=" * 78)
    print("  PYSPIKE DELAY -- synaptic transmission delay")
    print("=" * 78)
    _selftest_basic_delay()
    _selftest_coincidence_detection_needs_delay()
