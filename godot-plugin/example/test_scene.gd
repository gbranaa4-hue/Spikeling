extends Node3D
## Playable test for the SpikelingBrain plugin. Open godot-plugin/ in Godot 4
## and press Play (F5).
##
##   - Move the BLUE player with WASD / arrows.
##   - Get within range of the grey NPC box -> its brain WAKES ("sight" builds
##     up and it turns blue = FLEE).
##   - Press SPACE while near it -> you "damage" it, and it flips RED = ATTACK.
##
## Everything here is built in code so the scene is a single script + a trivial
## .tscn -- nothing to wire by hand.

var player: Node3D
var npc: Node3D
var brain: SpikelingBrain
var npc_mat: StandardMaterial3D
var hud: Label
var last_fired: String = "-"
var damage_timer: float = 0.0   # keep feeding "damage" for a moment after SPACE

func _ready() -> void:
	# --- camera + light so we can see something ---
	var cam := Camera3D.new()
	cam.position = Vector3(0, 13, 11)
	cam.rotation_degrees = Vector3(-50, 0, 0)
	add_child(cam)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55, -35, 0)
	add_child(light)

	# --- NPC: a box that owns a SpikelingBrain ---
	npc = Node3D.new()
	add_child(npc)
	var npc_mesh := MeshInstance3D.new()
	npc_mesh.mesh = BoxMesh.new()
	npc_mat = StandardMaterial3D.new()
	npc_mat.albedo_color = Color(0.55, 0.55, 0.55)
	npc_mesh.material_override = npc_mat
	npc.add_child(npc_mesh)

	# --- Player: a blue sphere you move around ---
	player = Node3D.new()
	player.position = Vector3(0, 0, 12)
	add_child(player)
	var pmesh := MeshInstance3D.new()
	var sph := SphereMesh.new()
	sph.radius = 0.5
	sph.height = 1.0
	pmesh.mesh = sph
	var pmat := StandardMaterial3D.new()
	pmat.albedo_color = Color(0.2, 0.45, 1.0)
	pmesh.material_override = pmat
	player.add_child(pmesh)

	# --- the brain ---
	brain = SpikelingBrain.new()
	brain.target = player
	brain.activation_range = 8.0
	npc.add_child(brain)                       # its _ready loads a default brain...
	brain.load_brain(FileAccess.get_file_as_string(
		"res://example/wary_animal.spk"))      # ...then we load the real one
	brain.neuron_fired.connect(_on_fired)
	brain.activation_changed.connect(func(_active: bool) -> void: _refresh())

	# --- HUD ---
	var cl := CanvasLayer.new()
	add_child(cl)
	hud = Label.new()
	hud.position = Vector2(16, 16)
	hud.add_theme_font_size_override("font_size", 18)
	cl.add_child(hud)
	_refresh()

func _process(delta: float) -> void:
	if player == null:
		return
	var move := Vector3.ZERO
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):    move.z -= 1.0
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):  move.z += 1.0
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):  move.x -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT): move.x += 1.0
	if move != Vector3.ZERO:
		player.position += move.normalized() * 6.0 * delta
	if Input.is_action_just_pressed("ui_accept"):   # SPACE / ENTER
		damage_timer = 0.6                          # "being hit" lasts a moment
	if damage_timer > 0.0:
		damage_timer -= delta
		brain.feed("damage", 20.0)                  # sustained damage: fires attack AND inhibits flee
	# Ease the box back toward grey between spikes. Because damage now INHIBITS
	# flee inside the brain, attack's red is no longer overwritten by flee.
	npc_mat.albedo_color = npc_mat.albedo_color.lerp(Color(0.55, 0.55, 0.55), delta * 1.5)
	_refresh()

func _on_fired(neuron_name: String) -> void:
	last_fired = neuron_name
	match neuron_name:
		"flee":   npc_mat.albedo_color = Color(0.2, 0.5, 1.0)
		"attack": npc_mat.albedo_color = Color(1.0, 0.2, 0.2)
		_:        npc_mat.albedo_color = Color(1.0, 0.9, 0.2)

func _refresh() -> void:
	if hud == null:
		return
	var d := npc.global_position.distance_to(player.global_position)
	hud.text = "WASD / arrows = move blue player    SPACE = damage the NPC\n"
	hud.text += "distance %.1f   (wake range %.0f)\n" % [d, brain.activation_range]
	hud.text += "brain: %s\n" % ("AWAKE" if brain.is_active() else "dormant")
	hud.text += "last fired: %s" % last_fired
