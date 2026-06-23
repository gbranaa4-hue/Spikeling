# fps-game — "Spikeling Dungeon"

A complete OpenGL/Pygame first-person shooter where enemy AI is driven by
real Spikeling spiking-neuron brains instead of scripted behavior trees.

## Key files
- `engine.py` — the game engine: rendering (occlusion culling, LOD), and a
  `SpikelingBrain` class that runs LIF neuron simulation per enemy. Enemies'
  brains are "dormant" (not simulated) until the player is nearby, an
  optimization tying back to Spikeling's event-driven/low-power design goal.
- `example_game.py` — usage example defining enemy personality profiles
  (e.g. "Aggressive", "Coward") built from different `.spk` brain configs.
- `enemy_brain.spk` — a 5-neuron enemy brain: SIGHT→CHASE, DAMAGE→RECOIL, etc.

## Status
Complete, working integration — not a stub. Depends conceptually on the
Spikeling runtime model in `../core/runtime/`, though it has its own
brain-execution code inline in `engine.py` rather than importing `core/`.

## Related
The Godot game at `C:\Users\gbran\OneDrive\Documents\tribe` uses the same
"brain per character" concept (see `Tribemanager.gd` and
`brain_visualizer.gd`) but is a separate project, not part of this folder.
