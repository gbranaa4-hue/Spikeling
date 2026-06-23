# Spikeling Brain — Godot 4 plugin

Cheap, event-driven NPC AI: spiking-neuron brains that only run when an
NPC is near the player (or whatever `target` you assign), instead of
running full decision logic on every NPC every frame.

This isn't a hand-wavy pitch — it's backed by a real, reproducible
benchmark: [`../benchmarks/BENCHMARKS.md`](../benchmarks/BENCHMARKS.md#3-heavy-realistic-polling-baseline-raycast--pathfinding-stand-in)
(entry #3). Measured result: **up to ~29x faster than naive always-on
polling AI** at typical NPC engagement rates (≤20% of NPCs actively near
the player at once) when per-NPC logic is non-trivial (raycasts,
pathfinding-class cost). The win shrinks as more NPCs are simultaneously
active, and crosses to a small loss only once ~100% are active — read the
benchmark before assuming this helps your specific game; it depends on
how expensive your real per-NPC AI logic is and how many NPCs are
typically engaged at once.

## Install

Copy `addons/spikeling_brain/` into your Godot project's `addons/`
folder, then enable it in Project Settings → Plugins.

## Usage

Add a `SpikelingBrain` node as a child of your NPC (it reads its
parent's `global_position`). Set `target` to your player node.

```gdscript
# on your enemy scene
@onready var brain: SpikelingBrain = $SpikelingBrain

func _ready() -> void:
    brain.neuron_fired.connect(_on_neuron_fired)

func _on_neuron_fired(neuron_name: String) -> void:
    match neuron_name:
        "attack": _do_attack()
        "chase": _start_chasing()
        "recoil": _flinch()

func take_damage(amount: float) -> void:
    brain.feed("damage", amount)  # costs nothing while dormant
```

Neurons, thresholds, and leak rates are configurable per-instance in the
inspector (`neuron_names`, `thresholds`, `leaks` — parallel arrays).
Default 5-neuron shape (`sight`, `damage`, `chase`, `recoil`, `attack`)
matches `fps-game/enemy_brain.spk` in the main Spikeling-Project repo.

## What's NOT in this v0.1

- No `.spk` file loading yet — neuron config is set directly on the node,
  not compiled from a `.spk` DSL file. That's the natural next step if
  this gets used for real.
- No accuracy/behavior benchmark yet, only the performance benchmark.
  "Cheap" is proven; "behaves well as game AI" still needs real playtesting.
- Untested inside an actual running Godot project as of this commit —
  this is a structurally-correct scaffold built from the proven
  `fps-game/` brain pattern, not yet verified in-editor. Open the addon
  in a real Godot 4 project and confirm it loads before shipping/selling it.
