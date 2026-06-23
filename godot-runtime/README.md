# GDScript / Godot backend

`spikeling.gd` — the **third backend** for the Spikeling DSL, alongside the
C runtime and the Verilog/hardware backend. It loads a `.spk` brain (neurons +
synapses), steps the leaky integrate-and-fire dynamics, supports bounded,
homeostatic Hebbian learning, and can export the learned network back to `.spk`.

It's a single self-contained `RefCounted` class, so a Godot game can use a
spiking neural network as a live "mind" (one `step()` runs the whole network —
designed to run one brain per group, not one per agent).

## Origin
Extracted from the standalone "tribe" Godot NPC simulation, where it drives
NPC trust/personality dynamics. It's copied here (read-only; the tribe project
itself is untouched) so all three Spikeling backends — C, Verilog, and
GDScript — live together in one place.

## Usage (in Godot)
```gdscript
var brain := Spikeling.new()
brain.load_from_text(spk_text)      # a .spk neural config
brain.stimulate("PlayerNorth", 50)  # inject input
var fired := brain.step()           # advance one tick -> names that fired
brain.learn(reward)                 # optional Hebbian update
```
