@tool
extends EditorPlugin

func _enter_tree() -> void:
	add_custom_type(
		"SpikelingBrain",
		"Node",
		preload("spikeling_brain.gd"),
		preload("icon.svg") if ResourceLoader.exists("res://addons/spikeling_brain/icon.svg") else null
	)

func _exit_tree() -> void:
	remove_custom_type("SpikelingBrain")
