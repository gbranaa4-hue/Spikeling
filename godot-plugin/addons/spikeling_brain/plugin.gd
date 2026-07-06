@tool
extends EditorPlugin

# SpikelingBrain (and the Spikeling engine) register themselves via `class_name`
# + `@icon`, so they're available as soon as this addon folder is in your
# project -- enabling the plugin is optional. This entry just lists it in
# Project Settings -> Plugins. (Registering the type again here via
# add_custom_type would collide with the class_name and error in Godot 4.)
func _enter_tree() -> void:
	pass

func _exit_tree() -> void:
	pass
