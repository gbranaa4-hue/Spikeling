@icon("res://addons/spikeling_brain/icon.svg")
class_name SpikelingBrain
extends Node

## A cheap, event-driven NPC brain powered by the full Spikeling spiking-neural-
## network engine (leaky integrate-and-fire neurons + synapses + optional
## Hebbian learning).
##
## It only steps the network while the owning NPC is within [member
## activation_range] of [member target]; the rest of the time it costs a single
## distance check per frame ("dormant"). Connect game logic to [signal
## neuron_fired] instead of polling state every frame.
##
## Define the brain two ways:
##   [b]1. Inline .spk[/b] via [member brain_spk] -- full network with synapses:
##       neuron sight  threshold=100 leak=5
##       neuron attack threshold=100 leak=5
##       synapse sight -> attack weight=60
##       refractory=4
##   [b]2. Simple reflex[/b] via [member simple_neurons] -- independent input
##       neurons, no synapses, when brain_spk is empty.
##
## When to use this: emergent / surprising / cheap NPC behaviour where you want
## reactions to *accumulate* and *habituate*. It is NOT a drop-in replacement for
## a behaviour tree when you need exact, authored, debuggable logic.

const SpikelingEngine := preload("spikeling.gd")

## Node whose position drives proximity activation (usually the player).
@export var target: Node3D
## Distance within which the brain wakes up and the network is stepped.
@export var activation_range: float = 20.0
## Full brain as .spk text (neurons + synapses). Overrides [member simple_neurons].
@export_multiline var brain_spk: String = ""
## Simple mode: independent input neurons (no synapses) when brain_spk is empty.
@export var simple_neurons: PackedStringArray = ["sight", "damage", "attack"]
@export var simple_threshold: float = 100.0
@export var simple_leak: float = 5.0
## Network steps per second while active -- decouples the brain from framerate.
@export var steps_per_second: float = 20.0
## Auto-stimulus fed to a neuron named "sight" each step, scaled by closeness.
@export var sight_stimulus: float = 40.0

## Emitted when a neuron crosses threshold. Connect chase/attack/flee logic here.
signal neuron_fired(neuron_name: String)
## Emitted when the brain transitions dormant <-> active.
signal activation_changed(is_active: bool)

var _engine: RefCounted            # Spikeling
var _is_active: bool = false
var _accum: float = 0.0

func _ready() -> void:
	_engine = SpikelingEngine.new()
	var spk := brain_spk.strip_edges()
	_engine.load_from_text(spk if spk != "" else _simple_spk())

func _simple_spk() -> String:
	var t := "# Spikeling Neural Configuration\n"
	for n in simple_neurons:
		t += "neuron %s threshold=%d leak=%d\n" % [n, int(simple_threshold), int(simple_leak)]
	t += "refractory=4\n"
	return t

## Load (or hot-swap) the brain at runtime from .spk text. Useful for loading a
## .spk file, since a child's _ready runs before its parent can set brain_spk.
func load_brain(spk_text: String) -> void:
	if _engine == null:
		_engine = SpikelingEngine.new()
	_engine.load_from_text(spk_text)

## Inject stimulus into a named neuron, e.g. on a damage event:
## [code]brain.feed("damage", 100.0)[/code]. Cheap even while dormant.
func feed(neuron_name: String, amount: float) -> void:
	if _engine:
		_engine.stimulate(neuron_name, amount)

## Reinforce whatever fired together this step (bounded Hebbian learning).
## Call after a "good" outcome so useful reflexes strengthen over time.
func reward(amount: float = 5.0) -> void:
	if _engine:
		_engine.learn(amount)

## True while the NPC is within activation_range and the brain is running.
func is_active() -> bool:
	return _is_active

## Direct access to the underlying Spikeling engine (introspection, export_spk, …).
func engine() -> RefCounted:
	return _engine

func _process(delta: float) -> void:
	if target == null or _engine == null:
		return

	var dist := _owner_position().distance_to(target.global_position)
	var active := dist < activation_range
	if active != _is_active:
		_is_active = active
		activation_changed.emit(_is_active)
	if not _is_active:
		return  # dormant: one distance check, nothing else

	# Fixed-rate stepping so behaviour doesn't change with framerate.
	var interval := 1.0 / maxf(1.0, steps_per_second)
	_accum += delta
	var guard := 0
	while _accum >= interval and guard < 8:   # guard against spiral-of-death
		_accum -= interval
		guard += 1
		var closeness := clampf(1.0 - dist / activation_range, 0.0, 1.0)
		if sight_stimulus > 0.0:
			_engine.stimulate("sight", closeness * sight_stimulus)
		for fired_name in _engine.step():
			neuron_fired.emit(fired_name)

func _owner_position() -> Vector3:
	var p := get_parent()
	return (p as Node3D).global_position if p is Node3D else Vector3.ZERO
