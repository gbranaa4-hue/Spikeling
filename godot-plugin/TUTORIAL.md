# Spikeling Brain — Full Tutorial

A complete, follow-along guide to running a spiking-neuron brain for your NPCs.
No neuroscience background needed. By the end you'll be able to design, wire,
feed, tune, and debug a brain, and know when *not* to use one.

- [0. The one idea](#0-the-one-idea)
- [1. Install](#1-install-2-minutes)
- [2. Your first brain](#2-your-first-brain-5-minutes)
- [3. How a neuron actually works](#3-how-a-neuron-actually-works)
- [4. The `.spk` brain format](#4-the-spk-brain-format)
- [5. Feeding the brain events](#5-feeding-the-brain-events)
- [6. Making it learn](#6-making-it-learn)
- [7. Worked example: fight-or-flee](#7-worked-example-fight-or-flee)
- [8. Tuning cookbook](#8-tuning-cookbook)
- [9. Performance model](#9-performance-model)
- [10. API reference](#10-api-reference)
- [11. Troubleshooting](#11-troubleshooting)
- [12. When NOT to use this](#12-when-not-to-use-this)

---

## 0. The one idea

A **neuron** is a bucket that fills up. Inputs pour in; the bucket slowly leaks.
When it fills past a **threshold**, it **fires** (emits a spike), empties, and
rests for a moment. Wire neurons together with **synapses** — a firing neuron
pours into its targets — and you get a tiny network whose behaviour *emerges*
from the wiring, rather than logic you author line by line.

That's the whole thing. Everything below is detail on those four words:
**fill, leak, fire, wire.**

---

## 1. Install (2 minutes)

1. Copy the folder `addons/spikeling_brain/` into your project's `addons/`.
2. **Project → Project Settings → Plugins → Spikeling Brain → Enable.**
   (Optional — the `SpikelingBrain` node and `Spikeling` engine also register
   themselves via `class_name`, so they work as soon as the folder is present.)

You now have a **SpikelingBrain** node available in the *Create New Node* dialog.

---

## 2. Your first brain (5 minutes)

We'll make an NPC that reacts when the player gets close.

1. In your NPC scene (root is a `Node3D`/`CharacterBody3D`), add a child node:
   **Add Child Node → search "SpikelingBrain"**.
2. In the inspector, set:
   - **Target** → your player node.
   - **Activation Range** → e.g. `20`.
   - **Simple Neurons** → `["sight", "attack"]` (leave **Brain Spk** empty).
3. Attach a script to your NPC and connect the brain's signal:

```gdscript
@onready var brain: SpikelingBrain = $SpikelingBrain

func _ready() -> void:
    brain.neuron_fired.connect(_on_neuron_fired)

func _on_neuron_fired(neuron_name: String) -> void:
    if neuron_name == "attack":
        print("NPC attacks!")   # replace with your real attack
```

Run the game and walk the player into range. The brain wakes up (a `sight`
drive builds as you get closer), and once `attack` charges past threshold it
fires. That's a working spiking NPC — no state machine.

> Prefer to just see it? Open `godot-plugin/` in Godot and press **F5** to run
> the bundled demo (`example/test_scene.tscn`).

---

## 3. How a neuron actually works

Each network **step**, every neuron does this, in order:

1. **Leak:** `potential -= leak` (then clamp to 0 minimum).
2. **Receive:** add everything that arrived this step — external stimulus you
   `feed()`, plus spikes from synapses that fired last step.
3. **Fire?** if `potential >= threshold`: emit the spike, reset `potential` to
   0, and go **refractory** for `refractory` steps (it ignores input and can't
   fire again during that time). A fired neuron delivers its synapse weights to
   its targets on the *next* step.

So the three per-neuron dials mean:

| dial | high value | low value |
|---|---|---|
| **threshold** | hard to fire (needs lots of input, fast) | hair-trigger |
| **leak** | forgets fast — needs *sustained* input | remembers — brief inputs accumulate |
| **refractory** | slow max firing rate | can fire in rapid bursts |

This is why reactions **accumulate** (a brief glimpse won't cross threshold, a
sustained one will) and **habituate** (leak + refractory stop spam). You get
that for free from the dynamics.

---

## 4. The `.spk` brain format

Simple mode (`simple_neurons`) gives you independent neurons. The real power is
a **`.spk` brain** — neurons *wired together*. Three line types:

```
# comments start with #
neuron  sight   threshold=100 leak=8      # define a neuron
synapse sight -> flee   weight=90         # wire one neuron into another
synapse damage -> flee  weight=-120       # NEGATIVE weight = INHIBITORY (suppresses)
refractory=4                              # global refractory period (steps)
```

- **`neuron NAME threshold=T leak=L`** — declare a neuron.
- **`synapse A -> B weight=W`** — when A fires, it adds `W` to B next step.
  **Positive** = excitatory (pushes B toward firing). **Negative** = inhibitory
  (pushes B *away* from firing — this is how you make urges compete).
- **`refractory=N`** — rest period after firing.

**Load a `.spk` two ways:**

- **Inline:** paste the text into the node's **Brain Spk** field in the inspector.
- **From a file** (child `_ready` runs before you can set exports, so load explicitly):

```gdscript
func _ready() -> void:
    brain.load_brain(FileAccess.get_file_as_string("res://brains/wary_animal.spk"))
```

---

## 5. Feeding the brain events

Sensors and game events drive the brain through `feed()`:

```gdscript
func take_damage(amount: float) -> void:
    brain.feed("damage", amount)      # pours `amount` into the "damage" neuron

func heard_noise(loudness: float) -> void:
    brain.feed("hearing", loudness)
```

`feed()` is cheap even while the brain is dormant — the value just waits for the
next active step, exactly like a real synapse doesn't "poll," it receives.

**The proximity gate.** A `SpikelingBrain` only *steps its network* while within
`activation_range` of `target`. Outside that range it costs one distance check
per frame ("dormant"). Watch the `activation_changed(is_active)` signal to spawn
effects only when a brain wakes.

The node also auto-feeds a neuron literally named `sight`, scaled by how close
the target is (tunable via `sight_stimulus`). Name a neuron `sight` and it gets
a built-in "I can see the player" drive; skip the name and it does nothing.

---

## 6. Making it learn

Call `reward()` after a good outcome to strengthen whatever fired *together* just
now (bounded Hebbian learning — "cells that fire together, wire together"):

```gdscript
func _on_neuron_fired(n: String) -> void:
    if n == "attack" and _hit_landed():
        brain.reward(5.0)   # that reflex worked — reinforce it
```

It's **bounded and homeostatic**: a synapse can only thicken to `1.8×` its
innate weight, and unused synapses relax back toward their innate value — so
personalities don't all wash out to the cap over a long session. Inhibitory
synapses are treated as **fixed circuitry** and are *not* changed by learning.

---

## 7. Worked example: fight-or-flee

The bundled `example/wary_animal.spk`, explained:

```
neuron sight   threshold=100 leak=8      # seeing the player
neuron damage  threshold=30  leak=2      # getting hit (low threshold = touchy)
neuron flee    threshold=100 leak=8      # motor: run away
neuron attack  threshold=60  leak=8      # motor: fight

synapse sight  -> flee   weight=90       # seeing you builds toward FLEE
synapse damage -> attack weight=100      # getting hit builds toward ATTACK
synapse damage -> flee   weight=-120     # ...and SUPPRESSES fleeing (inhibition)

refractory=4
```

Behaviour that *emerges*:
- **See the player** → `sight` fires → `flee` fires → the animal runs.
- **Take damage** → `damage` fires → `attack` fires **and** `flee` is inhibited
  → the animal commits to fighting instead of running.

### The lesson baked into this example

Our first version had *no* inhibition — just `sight->flee` and `damage->attack`.
Because sight is constant while the player is visible, `flee` fired *every* step
and drowned out the occasional `attack`: **"flee overwrote attack."** Two ways to
fix competing urges:

1. **Game-side arbitration** — the brain emits urges, your code picks a winner
   (e.g. "if attack fired, ignore flee for 1s"). Fine, but the *game* decides.
2. **Inhibition** (what this `.spk` does) — `damage -> flee weight=-120` lets the
   **brain** decide: a hit shuts fleeing down. That's `winner-take-all` inside
   the network.

You can prove it yourself — run the headless test:
```
godot --headless --path . -s res://example/test_inhibition.gd
```
Output: `SIGHT ONLY -> flee>0 attack=0`, `SIGHT+DAMAGE -> flee=0 attack>0`.

---

## 8. Tuning cookbook

Behaviour is all in the numbers. Common recipes:

| You want… | Do this |
|---|---|
| **Hair-trigger** reaction | low `threshold`, high synapse `weight` |
| **Stubborn / needs convincing** | high `threshold`, low `weight` |
| **Reacts only to *sustained* input** | high `leak` (brief inputs leak away) |
| **Reacts to accumulated / brief input** | low `leak` (inputs pile up) |
| **Can't spam an action** | high `refractory` |
| **One urge beats another** | inhibitory synapse: `A -> B weight=-N` |
| **Two urges compete (winner-take-all)** | mutual inhibition: `A -> B -N` *and* `B -> A -N` |
| **A latching "mode"** | self-excitation `A -> A weight≈threshold` (careful: too high = never stops) |

Rule of thumb: **`threshold` and `weight` set *how easily*; `leak` sets *how
long memory lasts*; `refractory` sets *how fast* it can repeat.**

---

## 9. Performance model

The point of the proximity gate: don't run AI for NPCs nobody's near.

Measured (`benchmarks/BENCHMARKS.md`, entry #3): **up to ~29× faster than
always-on polling AI** — *but only* when (a) per-NPC logic is genuinely
expensive (raycasts, pathfinding) and (b) few NPCs are near the player at once.
The win shrinks as more NPCs are simultaneously active and crosses to a small
loss near 100% active. It is **not** a free speed-up for cheap AI — read the
benchmark before assuming it helps your game.

`steps_per_second` decouples the brain from framerate (default 20). Lower it for
cheaper, coarser brains; raise it for snappier reactions.

---

## 10. API reference

**Node — `SpikelingBrain`**

| member | what |
|---|---|
| `target: Node3D` | drives proximity activation |
| `activation_range: float` | wake distance |
| `brain_spk: String` | inline `.spk` (overrides simple mode) |
| `simple_neurons / simple_threshold / simple_leak` | simple-mode config |
| `steps_per_second: float` | network steps/sec while active |
| `sight_stimulus: float` | auto-drive fed to a `sight` neuron |
| `signal neuron_fired(name)` | a neuron crossed threshold |
| `signal activation_changed(active)` | dormant ↔ active |
| `feed(name, amount)` | inject stimulus |
| `reward(amount)` | reinforce co-firing synapses |
| `load_brain(spk_text)` | load/hot-swap a `.spk` at runtime |
| `is_active()` | is it awake? |
| `engine()` | the underlying `Spikeling` engine (for the below) |

**Engine — `Spikeling`** (via `brain.engine()`, or use directly with `Spikeling.new()`)

`load_from_text(spk)`, `stimulate(name, amount)`, `step() -> Array` (names that
fired), `learn(reward, rate)`, `get_potential(name)`, `did_fire(name)`,
`neuron_states()`, `synapse_states()`, `export_spk()` (serialize the *learned*
brain back to `.spk`).

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Node type not found | Enable the plugin, or reopen the project so Godot rebuilds its class cache. |
| Brain never fires | Nothing drives it. Check `target` is set, you're in `activation_range`, and something `feed()`s or a `sight` neuron exists. |
| Fires constantly | `threshold` too low or `weight`/stimulus too high; raise threshold or `leak`. |
| One urge drowns out another | Add an inhibitory synapse (`A -> B weight=-N`). See §7. |
| Loading a `.spk` file does nothing | You set `brain_spk` in the parent's `_ready`, which runs *after* the child brain loaded. Use `brain.load_brain(...)` instead. |
| Editor shows no icon | The addon must be in `res://addons/spikeling_brain/`; the icon path is absolute. |

---

## 12. When NOT to use this

Be honest with yourself. Spiking brains are for **emergent, cheap, adaptive,
*surprising*** behaviour — swarms, animals, ambient creatures, moods that build
and fade. They are **not** for exact, authored, debuggable decisions. If you need
"open the door only if the player has the red key," that's a **behaviour tree or
state machine**, full stop. Novel isn't automatically better — reach for this
when the *emergence itself* is the feature you want.
