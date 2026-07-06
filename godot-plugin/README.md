# Spikeling Brain — Godot 4 plugin

Cheap, event-driven NPC AI: a **spiking neural network** brain that only runs
while an NPC is near the player (or any `target`), instead of running full
decision logic on every NPC every frame. Reactions **accumulate** (a brief
glimpse won't trigger flee; sustained sight will) and **habituate** (leak +
refractory periods stop spam), and the brain can **learn** — useful reflexes
strengthen over time.

Powered by the full Spikeling engine: leaky integrate-and-fire neurons **with
synapses**, `.spk` brain files, and bounded Hebbian learning.

> **📖 New here? Read [TUTORIAL.md](TUTORIAL.md)** — a complete, follow-along
> guide (install → first brain → the `.spk` format → feeding events → learning →
> a worked fight-or-flee example → a tuning cookbook). This README is the quick
> reference; the tutorial teaches you to operate it from scratch.

## Performance — measured, with the boundary conditions stated

Backed by a reproducible benchmark ([`../benchmarks/BENCHMARKS.md`](../benchmarks/BENCHMARKS.md), entry #3):
**up to ~29× faster than naive always-on polling AI** at typical engagement
rates (≤20% of NPCs actively near the player) *when per-NPC logic is non-trivial*
(raycasts, pathfinding-class cost). The win shrinks as more NPCs are active at
once and crosses to a small loss near 100% active. Read the benchmark before
assuming it helps *your* game — it depends on how expensive your real per-NPC
logic is and how many NPCs are typically engaged.

## Install

1. Copy `addons/spikeling_brain/` into your project's `addons/` folder.
2. Enable it: **Project Settings → Plugins → Spikeling Brain**.
3. Add a **SpikelingBrain** node as a child of your NPC. It reads its parent's
   `global_position`, so parent it under a `Node3D`/`CharacterBody3D`.

## Quickstart

```gdscript
@onready var brain: SpikelingBrain = $SpikelingBrain

func _ready() -> void:
    brain.target = get_node("/root/World/Player")   # or set in the inspector
    brain.neuron_fired.connect(_on_neuron_fired)

func _on_neuron_fired(neuron_name: String) -> void:
    match neuron_name:
        "flee":   _start_fleeing()
        "attack": _start_attacking()

func take_damage(amount: float) -> void:
    brain.feed("damage", amount)   # cheap even while the brain is dormant
```

A complete, runnable example is in [`example/`](example/): `wary_animal.spk`
(a fight-or-flee brain with synapses) and `npc_example.gd`.

## Defining a brain — two ways

**1. Full brain (`.spk`) — neurons + synapses.** Paste into the node's
`brain_spk` field in the inspector, or load a file with `brain.load_brain(...)`:

```
neuron sight   threshold=100 leak=8
neuron damage  threshold=60  leak=3
neuron flee    threshold=100 leak=6
neuron attack  threshold=70  leak=6
synapse sight  -> flee   weight=80
synapse damage -> attack weight=100
refractory=4
```

**2. Simple reflex — no synapses.** Leave `brain_spk` empty and set
`simple_neurons` (e.g. `["sight","damage","attack"]`) in the inspector. Each is
an independent input neuron.

## API

| | |
|---|---|
| `@export target: Node3D` | node that drives proximity activation |
| `@export activation_range` | wake-up distance |
| `@export brain_spk` | inline `.spk` (overrides simple mode) |
| `@export simple_neurons / simple_threshold / simple_leak` | simple-mode config |
| `@export steps_per_second` | network steps/sec while active (framerate-independent) |
| `@export sight_stimulus` | auto-drive fed to a `sight` neuron, scaled by closeness |
| `signal neuron_fired(name)` | a neuron crossed threshold — react here |
| `signal activation_changed(active)` | dormant ↔ active transition |
| `feed(name, amount)` | inject stimulus (e.g. a damage event) |
| `reward(amount)` | reinforce whatever just fired together (learning) |
| `load_brain(spk_text)` | hot-swap the brain at runtime |
| `is_active()` / `engine()` | state + direct engine access (introspection, `export_spk`) |

## When to use this (and when not to)

**Good fit:** emergent, surprising, *cheap* reactive behaviour where you want
reactions to build up, fade, and adapt — swarms, animals, ambient creatures.

**Bad fit:** exact, authored, debuggable decision logic. For that, a
**behaviour tree or state machine is the right tool** — this is not a drop-in
replacement, and it trades predictability for emergence. Novel isn't
automatically better; pick this when the *emergence* is the point.

## Status / honesty

- `.spk` loading, synapses, and learning are **in** as of this version.
- **Performance** is benchmarked; **behaviour quality as game AI is not** — that
  still needs real playtesting in your game.
- The code is structurally complete and parses, but **has not yet been run
  inside a live Godot 4 project** in this form. Open it in a real project and
  confirm it loads before shipping or selling it.
