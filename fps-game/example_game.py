"""
example_game.py
===============
Shows how to use the Spikeling FPS Engine API directly —
spawn enemies from DSL files, customise the arena, etc.

Run:   python example_game.py
"""

from engine import SpikelingFPSEngine, vec3

# ── Custom DSL inline (no file needed) ────────────────────────────────────────
AGGRESSIVE_BRAIN = """
# Spikeling Neural Configuration - Aggressive enemy variant
neuron SightThreat    threshold=20  leak=3
neuron ProximityAlert threshold=30  leak=2
neuron DamageTaken    threshold=60  leak=20
neuron LowHealth      threshold=95  leak=1
neuron PatrolIdle     threshold=50  leak=30

action SightThreat    -> [CHASE]
action ProximityAlert -> [ATTACK]
action DamageTaken    -> [RECOIL]
action LowHealth      -> [FLEE]
action PatrolIdle     -> [PATROL]

refractory=150ms

weight SightThreat    stimulus=SIGHT    value=100
weight SightThreat    stimulus=SOUND    value=80
weight ProximityAlert stimulus=DISTANCE value=100
weight DamageTaken    stimulus=HIT      value=100
weight LowHealth      stimulus=HEALTH   value=100
weight PatrolIdle     stimulus=IDLE     value=100
"""

COWARD_BRAIN = """
# Spikeling Neural Configuration - Coward enemy
neuron SightThreat    threshold=100 leak=30
neuron ProximityAlert threshold=100 leak=25
neuron DamageTaken    threshold=10  leak=5
neuron LowHealth      threshold=20  leak=1
neuron PatrolIdle     threshold=20  leak=10

action SightThreat    -> [FLEE]
action ProximityAlert -> [FLEE]
action DamageTaken    -> [FLEE]
action LowHealth      -> [FLEE]
action PatrolIdle     -> [PATROL]

refractory=100ms

weight SightThreat    stimulus=SIGHT    value=100
weight DamageTaken    stimulus=HIT      value=100
weight LowHealth      stimulus=HEALTH   value=100
weight PatrolIdle     stimulus=IDLE     value=100
"""

if __name__ == '__main__':
    engine = SpikelingFPSEngine(
        width=1280, height=720,
        title='Spikeling FPS — Custom Arena'
    )

    # Load level geometry
    from engine import LevelGeometry
    level = LevelGeometry()
    engine.scene.add_child(level)

    # Spawn enemies with different brains
    engine.add_enemy(position=( 8, 0,  8), name='Grunt',   dsl_source=None)           # default
    engine.add_enemy(position=(-8, 0,  8), name='Berserker', dsl_source=AGGRESSIVE_BRAIN)
    engine.add_enemy(position=( 8, 0, -8), name='Coward',  dsl_source=COWARD_BRAIN)
    engine.add_enemy(position=( 0, 0, 12), name='Custom',  dsl_file='enemy_brain.spk') # from file

    engine.run()
