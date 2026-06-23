@tool
class_name SpikelingBrain
extends Node

## A cheap, event-driven NPC brain: a small bank of LIF (leaky
## integrate-and-fire) neurons that only gets simulated when the owning
## NPC is within [member activation_range] of [member target]. Outside
## that range the brain is "dormant" -- _process does nothing but a
## single distance check.
##
## This is the pattern benchmarked in Spikeling-Project/benchmarks
## (dormant_vs_polling_heavy.c): at typical NPC engagement rates (most
## NPCs not actively near the player at once) and non-trivial per-NPC AI
## cost, this is up to ~29x cheaper than running full AI logic on every
## NPC every frame. See BENCHMARKS.md in that repo for methodology and
## raw numbers -- don't take the multiplier on faith, the boundary
## conditions matter (it only wins when the skipped logic is actually
## expensive and active fraction is low; see the README before assuming
## it helps your specific game).

## Node whose global position drives proximity (usually the player).
@export var target: Node3D
## Distance within which the brain wakes up and neurons are actually stepped.
@export var activation_range: float = 20.0
## Neuron names, in order. Used as keys for [signal neuron_fired].
@export var neuron_names: PackedStringArray = ["sight", "damage", "chase", "recoil", "attack"]
@export var thresholds: PackedFloat32Array = [1.0, 1.0, 1.0, 1.0, 1.0]
@export var leaks: PackedFloat32Array = [0.05, 0.05, 0.05, 0.05, 0.05]

## Emitted whenever a neuron crosses threshold, with its name. Connect
## game logic (chase/attack/flee state changes) here instead of polling.
signal neuron_fired(neuron_name: String)
## Emitted when the brain transitions dormant -> active or back.
signal activation_changed(is_active: bool)

var _potentials: PackedFloat32Array = []
var _is_active: bool = false
var _external_drive: Dictionary = {}  # name -> float, for feed()

func _ready() -> void:
	_potentials.resize(neuron_names.size())
	_potentials.fill(0.0)

## Inject an external stimulus into a named neuron (e.g. on a damage
## event: brain.feed("damage", 1.0)). Costs nothing if the brain is
## currently dormant -- the value is just held until the next active tick,
## same as how a real synapse doesn't "poll," it just receives a spike.
func feed(neuron_name: String, amount: float) -> void:
	_external_drive[neuron_name] = _external_drive.get(neuron_name, 0.0) + amount

func _process(_delta: float) -> void:
	if target == null:
		return

	var dist := global_position_safe().distance_to(target.global_position)
	var should_be_active := dist < activation_range

	if should_be_active != _is_active:
		_is_active = should_be_active
		activation_changed.emit(_is_active)

	if not _is_active:
		return  # dormant: nothing else runs this frame

	var sight_drive := clampf(1.0 - dist / activation_range, 0.0, 1.0)

	for i in neuron_names.size():
		var drive := sight_drive + _external_drive.get(neuron_names[i], 0.0)
		_potentials[i] += drive
		_potentials[i] -= leaks[i]
		if _potentials[i] < 0.0:
			_potentials[i] = 0.0
		if _potentials[i] >= thresholds[i]:
			_potentials[i] = 0.0
			neuron_fired.emit(neuron_names[i])

	_external_drive.clear()

func is_active() -> bool:
	return _is_active

func global_position_safe() -> Vector3:
	var p := get_parent()
	if p is Node3D:
		return (p as Node3D).global_position
	return Vector3.ZERO
