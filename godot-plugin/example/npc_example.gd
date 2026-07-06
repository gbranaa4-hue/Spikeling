extends CharacterBody3D
## Example NPC driven by a SpikelingBrain. Illustrative -- wire it to your own
## movement/combat. Scene setup:
##
##   NpcExample (CharacterBody3D, this script)
##   └─ SpikelingBrain   (set `target` = the player, `activation_range` = 20)
##
## Then either paste a .spk into the brain's `brain_spk` field in the inspector,
## or load one from code as below.

@onready var brain: SpikelingBrain = $SpikelingBrain

func _ready() -> void:
	# Load the example brain from a .spk file (child _ready already ran, so we
	# reload explicitly rather than relying on the inspector's brain_spk):
	brain.load_brain(FileAccess.get_file_as_string(
		"res://example/wary_animal.spk"))

	brain.neuron_fired.connect(_on_neuron_fired)
	brain.activation_changed.connect(func(active: bool):
		print("[NPC] brain ", "woke up" if active else "went dormant"))

## Call this from your combat system when the NPC is hit.
func take_damage(amount: float) -> void:
	brain.feed("damage", amount)   # a damage event drives the "damage" neuron

func _on_neuron_fired(neuron_name: String) -> void:
	match neuron_name:
		"flee":
			print("[NPC] fleeing!")
			# ... your flee movement here ...
		"attack":
			print("[NPC] attacking!")
			# ... your attack here ...
			brain.reward(5.0)   # attacking paid off -> reinforce that reflex
