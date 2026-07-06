extends SceneTree
## Headless proof that inhibition works (no graphics needed). Run with:
##   godot --headless --path . -s res://example/test_inhibition.gd
## Exit code 0 = inhibition confirmed.

func _init() -> void:
	var Spk = load("res://addons/spikeling_brain/spikeling.gd")
	var spk_text = FileAccess.get_file_as_string("res://example/wary_animal.spk")

	# Case 1: sight only -> flee fires, attack never fires
	var b1 = Spk.new()
	b1.load_from_text(spk_text)
	var flee1 := 0
	var atk1 := 0
	for i in 80:
		b1.stimulate("sight", 30.0)
		for fired_name in b1.step():
			if fired_name == "flee": flee1 += 1
			elif fired_name == "attack": atk1 += 1

	# Case 2: sight + damage -> attack fires, flee suppressed by inhibition
	var b2 = Spk.new()
	b2.load_from_text(spk_text)
	var flee2 := 0
	var atk2 := 0
	for i in 80:
		b2.stimulate("sight", 30.0)
		b2.stimulate("damage", 30.0)
		for fired_name in b2.step():
			if fired_name == "flee": flee2 += 1
			elif fired_name == "attack": atk2 += 1

	print("SIGHT ONLY   -> flee=%d attack=%d   (expect flee>0, attack=0)" % [flee1, atk1])
	print("SIGHT+DAMAGE -> flee=%d attack=%d   (expect attack>0, flee suppressed)" % [flee2, atk2])

	var ok := flee1 > 0 and atk1 == 0 and atk2 > 0 and flee2 < flee1
	print("INHIBITION CONFIRMED: %s" % ("YES" if ok else "NO"))
	quit(0 if ok else 1)
