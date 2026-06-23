#!/usr/bin/env python3
"""
Benchmark: Spikeling's event-driven "dormant brain" model vs a naive
always-polling FSM, at varying NPC counts and varying %-active-near-player.

This tests the one specific architectural claim that underlies the
"practical/profitable game AI" pitch for Spikeling: that only simulating
NPC brains when they're near the player (event-driven / dormant) is
cheaper than the common naive approach of running every NPC's full
decision logic every tick regardless of relevance.

Both sides do REAL work per NPC, not stubs:
  - Polling FSM: every NPC, every tick, runs a small decision-tree style
    check (distance compare, health compare, line-of-sight stand-in,
    state transition) -- representative of typical naive game AI.
  - Spikeling brain: a 5-neuron LIF network (same shape as
    fps-game/enemy_brain.spk) is only INTEGRATED (the actual neuron math)
    for NPCs within activation range. NPCs outside range still need a
    cheap distance check to know they're dormant -- that part is NOT
    free, and is included in both models' cost for a fair comparison.

Run it:
    python dormant_vs_polling.py
"""

import math
import random
import time


# ---------- shared cheap distance check (paid by both models) ----------

def distance_check(npc_pos, player_pos):
    dx = npc_pos[0] - player_pos[0]
    dy = npc_pos[1] - player_pos[1]
    return math.sqrt(dx * dx + dy * dy)


# ---------- naive polling FSM: full logic every NPC, every tick ----------

class PollingNPC:
    __slots__ = ("pos", "health", "state")

    def __init__(self, pos):
        self.pos = pos
        self.health = 100.0
        self.state = "idle"

    def tick(self, player_pos, activation_range):
        dist = distance_check(self.pos, player_pos)
        # naive FSM: always runs the full check regardless of distance
        if dist < activation_range:
            if self.health < 30:
                self.state = "flee"
            elif dist < activation_range * 0.3:
                self.state = "attack"
            else:
                self.state = "chase"
        else:
            self.state = "idle"
        # small fixed per-tick cost representing "is doing something" logic
        self.health -= 0.0001
        return self.state


# ---------- Spikeling-style dormant LIF brain ----------

class LIFNeuron:
    __slots__ = ("threshold", "leak", "potential")

    def __init__(self, threshold, leak):
        self.threshold = threshold
        self.leak = leak
        self.potential = 0.0

    def step(self, drive):
        self.potential += drive
        self.potential -= self.leak
        if self.potential < 0:
            self.potential = 0.0
        fired = self.potential >= self.threshold
        if fired:
            self.potential = 0.0
        return fired


class SpikelingNPC:
    __slots__ = ("pos", "health", "brain", "state")

    def __init__(self, pos):
        self.pos = pos
        self.health = 100.0
        self.state = "dormant"
        # 5-neuron brain, same shape as fps-game/enemy_brain.spk
        # (SIGHT, DAMAGE, CHASE, RECOIL, ATTACK)
        self.brain = [
            LIFNeuron(threshold=1.0, leak=0.05),
            LIFNeuron(threshold=1.0, leak=0.05),
            LIFNeuron(threshold=1.0, leak=0.05),
            LIFNeuron(threshold=1.0, leak=0.05),
            LIFNeuron(threshold=1.0, leak=0.05),
        ]

    def tick(self, player_pos, activation_range):
        dist = distance_check(self.pos, player_pos)  # paid regardless, same as polling model
        if dist >= activation_range:
            self.state = "dormant"
            return self.state  # brain NOT simulated -- this is the whole optimization

        # only active NPCs actually integrate their neurons
        sight_drive = max(0.0, 1.0 - dist / activation_range)
        fired = [n.step(sight_drive) for n in self.brain]
        if fired[1]:
            self.state = "flee"
        elif fired[4]:
            self.state = "attack"
        elif fired[2]:
            self.state = "chase"
        else:
            self.state = "alert"
        self.health -= 0.0001
        return self.state


# ---------- benchmark harness ----------

def run_trial(npc_count, active_fraction, ticks, model):
    activation_range = 50.0
    player_pos = (0.0, 0.0)

    npcs = []
    n_active = int(npc_count * active_fraction)
    for i in range(npc_count):
        if i < n_active:
            r = random.uniform(0, activation_range * 0.8)
        else:
            r = random.uniform(activation_range * 1.5, activation_range * 5)
        angle = random.uniform(0, 2 * math.pi)
        pos = (r * math.cos(angle), r * math.sin(angle))
        npcs.append(model(pos))

    start = time.perf_counter()
    for _ in range(ticks):
        for npc in npcs:
            npc.tick(player_pos, activation_range)
    elapsed = time.perf_counter() - start
    return elapsed


def main():
    ticks = 200
    npc_counts = [50, 200, 1000]
    active_fractions = [0.05, 0.20, 0.50, 1.00]

    print(f"{'NPCs':>6} {'%active':>8} {'Polling FSM (s)':>17} {'Spikeling LIF (s)':>19} {'Speedup':>9}")
    print("-" * 64)
    for npc_count in npc_counts:
        for frac in active_fractions:
            t_poll = run_trial(npc_count, frac, ticks, PollingNPC)
            t_spike = run_trial(npc_count, frac, ticks, SpikelingNPC)
            speedup = t_poll / t_spike if t_spike > 0 else float("inf")
            print(f"{npc_count:>6} {frac*100:>7.0f}% {t_poll:>17.4f} {t_spike:>19.4f} {speedup:>8.2f}x")
        print()


if __name__ == "__main__":
    main()
