class_name ViceQuestPresentationRig
extends Node3D

# Desktop keeps the original world camera.
# Quest renders the same gameplay world into a dedicated 16:9 SubViewport and
# presents that viewport as a room-anchored tabletop display in OpenXR.
enum PresentationMode {
    DESKTOP_TOPDOWN,
    DIORAMA_PREVIEW,
    VR_DIORAMA,
}

const QUEST_DISPLAY_LAYER: int = 1 << 19
const QUEST_GAME_VIEW_SIZE: Vector2i = Vector2i(1280, 720)
const QUEST_PANEL_SIZE: Vector2 = Vector2(1.72, 0.9675)
const QUEST_PANEL_POSITION: Vector3 = Vector3(0.0, 1.05, -1.55)
const QUEST_PANEL_TILT_DEGREES: float = -18.0
const QUEST_CAMERA_HEIGHT_FACTOR: float = 1.55
const DEATH_CAMERA_HEIGHT_FACTOR: float = 0.58
const DEATH_CAMERA_FOV: float = 34.0
const QUEST_POP_OUT_MIN_Y: float = 0.08
const QUEST_POP_OUT_DEPTH_BOOST: float = 1.35
const QUEST_POP_OUT_OVERSCAN: float = 1.04
# Walkable field roofs live at z>=2 => world Y = 1.2. Ground peds sit at 0.12.
# Hardware 18.13: plazas are good; some ground-to-up stairs still hide under
# popout overhangs before y hits 0.95. Switch a little earlier on the climb.
const ELEVATED_PAWN_MIN_Y: float = 0.36
const ELEVATED_PAWN_Y_BIAS: float = 0.10

var camera: Camera3D
var game_viewport: SubViewport
var ui_viewport: SubViewport
var xr_origin: XROrigin3D
var xr_camera: XRCamera3D
var left_controller: XRController3D
var right_controller: XRController3D
var xr_interface: XRInterface
var xr_active: bool = false
var mode: PresentationMode = PresentationMode.DESKTOP_TOPDOWN
var camera_height: float = 18.0
var camera_fov: float = 42.0
var follow_speed: float = 9.0
var last_target: Vector3 = Vector3.ZERO
var smoothed_target: Vector3 = Vector3.ZERO
var death_focus: bool = false
var quest_height_factor: float = 1.0
var _focus_tween: Tween
var board_root: Node3D
var popout_root: Node3D
var popout_material: ShaderMaterial
var popout_chunks: Dictionary = {}
var popout_pawns: Dictionary = {}
var popout_vehicles: Dictionary = {}
var popout_throws: Dictionary = {}
var popout_one_shots: Array = []
var popout_enabled: bool = false

func configure(start_position: Vector3, height: float, fov: float, speed: float) -> void:
    camera_height = height
    camera_fov = fov
    follow_speed = speed
    last_target = start_position
    smoothed_target = start_position
    global_position = start_position

    if OS.has_feature("android") and _try_enable_openxr():
        mode = PresentationMode.VR_DIORAMA
        _apply_quest_game_camera_pose()
        return

    _build_desktop_camera()
    _apply_camera_pose()

func _build_desktop_camera() -> void:
    camera = Camera3D.new()
    camera.name = "GameplayCamera"
    camera.projection = Camera3D.PROJECTION_PERSPECTIVE
    camera.fov = camera_fov
    camera.near = 0.25
    camera.far = 320.0
    camera.current = true
    add_child(camera)

func _try_enable_openxr() -> bool:
    xr_interface = XRServer.find_interface("OpenXR")
    if xr_interface == null:
        return false
    if not xr_interface.is_initialized() and not xr_interface.initialize():
        push_warning("Vice Quest: OpenXR interface could not initialize; falling back to flat camera.")
        return false

    XRServer.primary_interface = xr_interface
    get_viewport().use_xr = true

    # The headset camera only sees the floating Vice Quest display. The actual
    # game world stays on visual layer 1 and is rendered by game_viewport below.
    xr_origin = XROrigin3D.new()
    xr_origin.name = "QuestXROrigin"
    xr_origin.current = true
    add_child(xr_origin)

    xr_camera = XRCamera3D.new()
    xr_camera.name = "QuestXRCamera"
    xr_camera.near = 0.05
    xr_camera.far = 50.0
    xr_camera.cull_mask = QUEST_DISPLAY_LAYER
    xr_camera.current = true
    xr_origin.add_child(xr_camera)

    left_controller = XRController3D.new()
    left_controller.name = "QuestLeftController"
    left_controller.tracker = &"left_hand"
    left_controller.pose = &"aim"
    xr_origin.add_child(left_controller)

    right_controller = XRController3D.new()
    right_controller.name = "QuestRightController"
    right_controller.tracker = &"right_hand"
    right_controller.pose = &"aim"
    xr_origin.add_child(right_controller)

    _build_quest_game_viewport()
    _build_quest_display()

    xr_active = true
    return true

func _build_quest_game_viewport() -> void:
    game_viewport = SubViewport.new()
    game_viewport.name = "QuestGameViewport"
    game_viewport.size = QUEST_GAME_VIEW_SIZE
    game_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    game_viewport.transparent_bg = false
    game_viewport.world_3d = get_viewport().world_3d
    add_child(game_viewport)

    camera = Camera3D.new()
    camera.name = "QuestGameplayCamera"
    camera.projection = Camera3D.PROJECTION_PERSPECTIVE
    camera.fov = camera_fov
    camera.near = 0.25
    camera.far = 360.0
    camera.cull_mask = 1
    camera.current = true
    game_viewport.add_child(camera)

    ui_viewport = SubViewport.new()
    ui_viewport.name = "QuestUIViewport"
    ui_viewport.size = QUEST_GAME_VIEW_SIZE
    ui_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    ui_viewport.transparent_bg = true
    ui_viewport.disable_3d = true
    add_child(ui_viewport)

func _build_quest_display() -> void:
    board_root = Node3D.new()
    board_root.name = "QuestTabletopBoard"
    board_root.position = QUEST_PANEL_POSITION
    board_root.rotation_degrees.x = QUEST_PANEL_TILT_DEGREES
    xr_origin.add_child(board_root)

    var backing: MeshInstance3D = MeshInstance3D.new()
    backing.name = "BoardBacking"
    var backing_mesh: BoxMesh = BoxMesh.new()
    backing_mesh.size = Vector3(QUEST_PANEL_SIZE.x + 0.08, QUEST_PANEL_SIZE.y + 0.08, 0.035)
    backing.mesh = backing_mesh
    backing.position.z = -0.025
    backing.layers = QUEST_DISPLAY_LAYER
    var backing_material: StandardMaterial3D = StandardMaterial3D.new()
    backing_material.albedo_color = Color("080b12")
    backing_material.roughness = 0.86
    backing.material_override = backing_material
    board_root.add_child(backing)

    var screen: MeshInstance3D = MeshInstance3D.new()
    screen.name = "ViceQuestScreen"
    var screen_mesh: QuadMesh = QuadMesh.new()
    screen_mesh.size = QUEST_PANEL_SIZE
    screen.mesh = screen_mesh
    screen.layers = QUEST_DISPLAY_LAYER
    screen.position.z = 0.001
    screen.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

    var screen_material: StandardMaterial3D = StandardMaterial3D.new()
    screen_material.albedo_texture = game_viewport.get_texture()
    screen_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    screen_material.cull_mode = BaseMaterial3D.CULL_DISABLED
    screen_material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
    screen.material_override = screen_material
    board_root.add_child(screen)

    var ui_screen: MeshInstance3D = MeshInstance3D.new()
    ui_screen.name = "ViceQuestUIOverlay"
    var ui_mesh: QuadMesh = QuadMesh.new()
    ui_mesh.size = QUEST_PANEL_SIZE
    ui_screen.mesh = ui_mesh
    ui_screen.layers = QUEST_DISPLAY_LAYER
    ui_screen.position.z = 0.004
    ui_screen.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

    var ui_shader: Shader = Shader.new()
    ui_shader.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_test_disabled, depth_draw_never, blend_mix;

uniform sampler2D ui_texture : source_color, filter_linear;

void fragment() {
    vec4 texel = texture(ui_texture, UV);
    ALBEDO = texel.rgb;
    ALPHA = texel.a;
}
"""
    var ui_material: ShaderMaterial = ShaderMaterial.new()
    ui_material.shader = ui_shader
    ui_material.set_shader_parameter("ui_texture", ui_viewport.get_texture())
    ui_material.render_priority = 127
    ui_screen.material_override = ui_material
    board_root.add_child(ui_screen)

    popout_root = Node3D.new()
    popout_root.name = "QuestBuildingPopOut"
    popout_root.visible = false
    board_root.add_child(popout_root)

func _ensure_popout_material(atlas_texture: Texture2D) -> void:
    if popout_material != null:
        popout_material.set_shader_parameter("atlas_texture", atlas_texture)
        return
    var shader: Shader = Shader.new()
    shader.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;

uniform sampler2D atlas_texture : source_color, filter_nearest;
uniform vec2 focus_xz = vec2(0.0, 0.0);
uniform vec2 half_view_world = vec2(20.0, 12.0);
uniform float min_world_y = 0.08;

varying vec3 source_position;

void vertex() {
    source_position = VERTEX;
}

void fragment() {
    if (source_position.y < min_world_y) {
        discard;
    }
    if (abs(source_position.x - focus_xz.x) > half_view_world.x ||
        abs(source_position.z - focus_xz.y) > half_view_world.y) {
        discard;
    }
    vec4 texel = texture(atlas_texture, UV);
    if (texel.a < 0.5) {
        discard;
    }
    ALBEDO = texel.rgb;
    ALPHA = 1.0;
}
"""
    popout_material = ShaderMaterial.new()
    popout_material.shader = shader
    popout_material.set_shader_parameter("atlas_texture", atlas_texture)
    popout_material.set_shader_parameter("min_world_y", QUEST_POP_OUT_MIN_Y)

func _load_popout_mesh(coord: Vector2i) -> ArrayMesh:
    var path: String = "res://assets/gta2/downtown/downtown_popout_%d_%d.meshbin" % [coord.x, coord.y]
    var file: FileAccess = FileAccess.open(path, FileAccess.READ)
    if file == null:
        return null
    var vertex_count: int = int(file.get_32())
    if vertex_count <= 0:
        return null
    var payload: PackedByteArray = file.get_buffer(file.get_length() - file.get_position())
    var values: PackedFloat32Array = payload.to_float32_array()
    if values.size() < vertex_count * 5:
        return null

    var vertices: PackedVector3Array = PackedVector3Array()
    var uvs: PackedVector2Array = PackedVector2Array()
    vertices.resize(vertex_count)
    uvs.resize(vertex_count)
    for i in range(vertex_count):
        var base: int = i * 5
        vertices[i] = Vector3(values[base], values[base + 1], values[base + 2])
        uvs[i] = Vector2(values[base + 3], values[base + 4])

    var arrays: Array = []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    var mesh: ArrayMesh = ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    return mesh

func sync_popout_chunks(chunks: Dictionary, atlas_texture: Texture2D) -> void:
    if not xr_active or popout_root == null or atlas_texture == null:
        return
    _ensure_popout_material(atlas_texture)
    var desired: Dictionary = {}
    for raw_coord: Variant in chunks.keys():
        var coord: Vector2i = raw_coord
        desired[coord] = true
        if popout_chunks.has(coord) and is_instance_valid(popout_chunks[coord]):
            continue

        var pop_mesh: ArrayMesh = _load_popout_mesh(coord)
        if pop_mesh == null:
            continue

        var duplicate_mesh: MeshInstance3D = MeshInstance3D.new()
        duplicate_mesh.name = "PopOut_%d_%d" % [coord.x, coord.y]
        duplicate_mesh.mesh = pop_mesh
        duplicate_mesh.material_override = popout_material
        duplicate_mesh.layers = QUEST_DISPLAY_LAYER
        duplicate_mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
        popout_root.add_child(duplicate_mesh)
        popout_chunks[coord] = duplicate_mesh

    for raw_coord: Variant in popout_chunks.keys():
        if desired.has(raw_coord):
            continue
        var old_node: Node = popout_chunks[raw_coord]
        if is_instance_valid(old_node):
            old_node.queue_free()
        popout_chunks.erase(raw_coord)

    _update_popout_transform()

func set_popout_enabled(active: bool) -> void:
    popout_enabled = active
    if popout_root != null:
        popout_root.visible = active
    if not active:
        _clear_elevated_pawns()

func _update_popout_transform() -> void:
    if popout_root == null or camera == null:
        return
    var view_height: float = maxf(0.01, camera_height * QUEST_CAMERA_HEIGHT_FACTOR * quest_height_factor)
    var half_height_world: float = view_height * tan(deg_to_rad(camera.fov * 0.5))
    var aspect: float = float(QUEST_GAME_VIEW_SIZE.x) / float(QUEST_GAME_VIEW_SIZE.y)
    var half_width_world: float = half_height_world * aspect
    var planar_scale: float = QUEST_PANEL_SIZE.x / maxf(0.01, half_width_world * 2.0)
    var depth_scale: float = planar_scale * QUEST_POP_OUT_DEPTH_BOOST
    var focus: Vector2 = Vector2(smoothed_target.x, smoothed_target.z)

    var basis: Basis = Basis(
        Vector3(planar_scale, 0.0, 0.0),
        Vector3(0.0, 0.0, depth_scale),
        Vector3(0.0, -planar_scale, 0.0)
    )
    var origin: Vector3 = Vector3(
        -smoothed_target.x * planar_scale,
        smoothed_target.z * planar_scale,
        0.006
    )
    popout_root.transform = Transform3D(basis, origin)

    if popout_material != null:
        popout_material.set_shader_parameter("focus_xz", focus)
        popout_material.set_shader_parameter(
            "half_view_world",
            Vector2(half_width_world, half_height_world) * QUEST_POP_OUT_OVERSCAN
        )

func _on_building_roof(world_position: Vector3) -> bool:
    if world_position.y < ELEVATED_PAWN_MIN_Y:
        return false
    var host: Node = get_parent()
    if host != null and host.has_method("surface_is_building_roof"):
        return bool(host.call("surface_is_building_roof", world_position))
    return true

func sync_elevated_pawns(player_nodes: Dictionary) -> void:
    if not xr_active or popout_root == null or not popout_enabled:
        _clear_elevated_pawns()
        return

    var desired: Dictionary = {}
    for raw_id: Variant in player_nodes.keys():
        var pawn_key: String = str(raw_id)
        var player: Node = player_nodes[raw_id]
        if player == null or not is_instance_valid(player):
            continue
        if int(player.get("vehicle_id")) != 0:
            _restore_source_sprite(player)
            continue
        if not player.has_method("get_ped_sprite"):
            continue
        var src: SpriteBase3D = player.get_ped_sprite()
        if src == null or not is_instance_valid(src):
            continue
        if not _on_building_roof(player.position):
            src.visible = true
            continue

        desired[pawn_key] = true
        var clone: Sprite3D = popout_pawns.get(pawn_key) as Sprite3D
        if clone == null or not is_instance_valid(clone):
            clone = _make_elevated_pawn_sprite(pawn_key)
            popout_root.add_child(clone)
            popout_pawns[pawn_key] = clone
        _copy_elevated_pawn(clone, src)
        src.visible = false

    for raw_id: Variant in popout_pawns.keys():
        if desired.has(raw_id):
            continue
        _free_elevated_pawn(raw_id, player_nodes)

func _make_elevated_pawn_sprite(pawn_key: String) -> Sprite3D:
    var clone: Sprite3D = Sprite3D.new()
    clone.name = "ElevatedPawn_%s" % pawn_key
    clone.layers = QUEST_DISPLAY_LAYER
    clone.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    clone.billboard = BaseMaterial3D.BILLBOARD_DISABLED
    clone.shaded = false
    clone.centered = true
    clone.double_sided = true
    clone.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
    clone.alpha_scissor_threshold = 0.5
    clone.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    clone.render_priority = 8
    clone.no_depth_test = false
    return clone

func _copy_elevated_pawn(clone: Sprite3D, src: SpriteBase3D) -> void:
    var tex: Texture2D = null
    if src is AnimatedSprite3D:
        var anim_sprite: AnimatedSprite3D = src as AnimatedSprite3D
        var frames: SpriteFrames = anim_sprite.sprite_frames
        if frames != null and frames.has_animation(anim_sprite.animation):
            tex = frames.get_frame_texture(anim_sprite.animation, anim_sprite.frame)
    elif src is Sprite3D:
        tex = (src as Sprite3D).texture
    if tex == null:
        clone.visible = false
        return
    clone.texture = tex
    clone.pixel_size = src.pixel_size
    clone.modulate = src.modulate
    clone.flip_h = src.flip_h
    clone.flip_v = src.flip_v
    var pos: Vector3 = src.global_position
    pos.y += ELEVATED_PAWN_Y_BIAS
    # Local space of popout_root is gameplay-world XYZ, same as popout meshes.
    clone.transform = Transform3D(src.global_transform.basis, pos)
    clone.set_meta("source_sprite", src)
    clone.visible = true

func _restore_source_sprite(player: Node) -> void:
    if player == null or not is_instance_valid(player) or not player.has_method("get_ped_sprite"):
        return
    var src: SpriteBase3D = player.get_ped_sprite()
    if src != null and is_instance_valid(src):
        src.visible = true

func _free_elevated_pawn(raw_id: Variant, player_nodes: Dictionary) -> void:
    var old_node: Node = popout_pawns[raw_id]
    if is_instance_valid(old_node):
        if old_node.has_meta("source_sprite"):
            var src: Variant = old_node.get_meta("source_sprite")
            if src is SpriteBase3D and is_instance_valid(src):
                (src as SpriteBase3D).visible = true
        old_node.queue_free()
    popout_pawns.erase(raw_id)
    if player_nodes.has(raw_id):
        _restore_source_sprite(player_nodes[raw_id])

func _clear_elevated_pawns() -> void:
    for raw_id: Variant in popout_pawns.keys():
        var old_node: Node = popout_pawns[raw_id]
        if is_instance_valid(old_node):
            if old_node.has_meta("source_sprite"):
                var src: Variant = old_node.get_meta("source_sprite")
                if src is SpriteBase3D and is_instance_valid(src):
                    (src as SpriteBase3D).visible = true
            old_node.queue_free()
    popout_pawns.clear()

func sync_elevated_vehicles(vehicle_nodes: Dictionary) -> void:
    if not xr_active or popout_root == null or not popout_enabled:
        _clear_elevated_vehicles()
        return

    var desired: Dictionary = {}
    for raw_id: Variant in vehicle_nodes.keys():
        var id: int = int(raw_id)
        var vehicle: Node = vehicle_nodes[raw_id]
        if vehicle == null or not is_instance_valid(vehicle):
            continue
        if not vehicle.has_method("get_sprite") or not vehicle.has_method("wants_board_sprite"):
            continue
        var src: SpriteBase3D = vehicle.get_sprite()
        if src == null or not is_instance_valid(src):
            continue
        var on_roof: bool = _on_building_roof(vehicle.position)
        var show_body: bool = bool(vehicle.call("wants_board_sprite"))
        if not on_roof or not show_body:
            src.visible = show_body
            _restore_vehicle_turret(vehicle)
            continue

        desired[id] = true
        var holder: Node3D = popout_vehicles.get(id) as Node3D
        if holder == null or not is_instance_valid(holder):
            holder = _make_elevated_vehicle_holder(id)
            popout_root.add_child(holder)
            popout_vehicles[id] = holder
        var body: Sprite3D = holder.get_node("Body") as Sprite3D
        _copy_flat_sprite(body, src)
        src.visible = false
        _sync_elevated_turret(holder, vehicle)

    for raw_id: Variant in popout_vehicles.keys():
        if desired.has(raw_id):
            continue
        _free_elevated_vehicle(raw_id)

func _make_flat_sprite(sprite_name: String) -> Sprite3D:
    var clone: Sprite3D = Sprite3D.new()
    clone.name = sprite_name
    clone.layers = QUEST_DISPLAY_LAYER
    clone.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    clone.billboard = BaseMaterial3D.BILLBOARD_DISABLED
    clone.shaded = false
    clone.centered = true
    clone.double_sided = true
    clone.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
    clone.alpha_scissor_threshold = 0.5
    clone.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    clone.render_priority = 8
    clone.no_depth_test = false
    return clone

func _make_elevated_vehicle_holder(id: int) -> Node3D:
    var holder: Node3D = Node3D.new()
    holder.name = "ElevatedVehicle_%d" % id
    holder.add_child(_make_flat_sprite("Body"))
    holder.add_child(_make_flat_sprite("Turret"))
    return holder

func _copy_flat_sprite(clone: Sprite3D, src: SpriteBase3D) -> void:
    if not (src is Sprite3D) or (src as Sprite3D).texture == null:
        clone.visible = false
        return
    var flat: Sprite3D = src as Sprite3D
    clone.texture = flat.texture
    clone.pixel_size = flat.pixel_size
    clone.modulate = flat.modulate
    clone.flip_h = flat.flip_h
    clone.flip_v = flat.flip_v
    var pos: Vector3 = src.global_position
    pos.y += ELEVATED_PAWN_Y_BIAS
    clone.transform = Transform3D(src.global_transform.basis, pos)
    clone.set_meta("source_sprite", src)
    clone.visible = true

func _sync_elevated_turret(holder: Node3D, vehicle: Node) -> void:
    var turret_clone: Sprite3D = holder.get_node("Turret") as Sprite3D
    var src: SpriteBase3D = null
    if vehicle.has_method("get_turret_sprite"):
        src = vehicle.get_turret_sprite()
    var show: bool = src != null and is_instance_valid(src) and vehicle.has_method("wants_turret_sprite") and bool(vehicle.call("wants_turret_sprite"))
    if not show:
        turret_clone.visible = false
        _restore_vehicle_turret(vehicle)
        return
    _copy_flat_sprite(turret_clone, src)
    src.visible = false

func _restore_vehicle_turret(vehicle: Node) -> void:
    if vehicle == null or not is_instance_valid(vehicle) or not vehicle.has_method("get_turret_sprite"):
        return
    var src: SpriteBase3D = vehicle.get_turret_sprite()
    if src != null and is_instance_valid(src):
        src.visible = vehicle.has_method("wants_turret_sprite") and bool(vehicle.call("wants_turret_sprite"))

func _free_elevated_vehicle(raw_id: Variant) -> void:
    var holder: Node = popout_vehicles[raw_id]
    if is_instance_valid(holder):
        for sprite_name: String in ["Body", "Turret"]:
            var clone: Node = holder.get_node_or_null(sprite_name)
            if clone != null and clone.has_meta("source_sprite"):
                var src: Variant = clone.get_meta("source_sprite")
                if src is SpriteBase3D and is_instance_valid(src):
                    _restore_hidden_vehicle_sprite(src as SpriteBase3D)
        holder.queue_free()
    popout_vehicles.erase(raw_id)

func _restore_hidden_vehicle_sprite(src: SpriteBase3D) -> void:
    var node: Node = src
    while node != null and not node.has_method("wants_board_sprite"):
        node = node.get_parent()
    if node == null:
        src.visible = true
        return
    if src.name == "OriginalGTA2Turret" and node.has_method("wants_turret_sprite"):
        src.visible = bool(node.call("wants_turret_sprite"))
    else:
        src.visible = bool(node.call("wants_board_sprite"))

func _clear_elevated_vehicles() -> void:
    for raw_id: Variant in popout_vehicles.keys():
        _free_elevated_vehicle(raw_id)
    popout_vehicles.clear()

func sync_elevated_throws(projectiles: Dictionary, fires: Dictionary, flames: Dictionary) -> void:
    if not xr_active or popout_root == null or not popout_enabled:
        _clear_elevated_throws()
        _clear_one_shots()
        return
    var desired: Dictionary = {}
    _sync_throw_group(projectiles, "proj", desired)
    _sync_throw_group(fires, "fire", desired)
    _sync_throw_group(flames, "flame", desired)
    var stale: Array = []
    for raw_key: Variant in popout_throws.keys():
        if not desired.has(raw_key):
            stale.append(raw_key)
    for raw_key: Variant in stale:
        _free_throw(raw_key)
    _sync_one_shots()

func track_elevated_fx(source: Node3D, travel_y: float = -1.0) -> void:
    if not xr_active or popout_root == null or not popout_enabled or source == null:
        return
    if not _on_building_roof(source.global_position):
        return
    var holder: Node3D = Node3D.new()
    holder.name = "ElevatedFx"
    popout_root.add_child(holder)
    if source is MeshInstance3D:
        var mesh_clone: MeshInstance3D = MeshInstance3D.new()
        mesh_clone.name = "Streak"
        mesh_clone.mesh = (source as MeshInstance3D).mesh
        mesh_clone.layers = QUEST_DISPLAY_LAYER
        mesh_clone.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
        holder.add_child(mesh_clone)
    else:
        holder.add_child(_make_flat_sprite("Fx"))
    popout_one_shots.append({"source": source, "holder": holder})

func _sync_throw_group(nodes: Dictionary, prefix: String, desired: Dictionary) -> void:
    for raw_id: Variant in nodes.keys():
        var node: Node = nodes[raw_id] as Node
        var key: String = "%s:%s" % [prefix, str(raw_id)]
        if node == null or not is_instance_valid(node):
            continue
        if not _on_building_roof(node.global_position):
            _reveal_sprites(node)
            continue
        desired[key] = true
        var holder: Node3D = popout_throws.get(key) as Node3D
        if holder == null or not is_instance_valid(holder):
            holder = Node3D.new()
            holder.name = "ElevatedThrow_%s" % key.replace(":", "_")
            popout_root.add_child(holder)
            popout_throws[key] = holder
        _mirror_sprites(holder, node)

func _mirror_sprites(holder: Node3D, source: Node) -> void:
    var sprites: Array[SpriteBase3D] = []
    _gather_sprites(source, sprites)
    while holder.get_child_count() < sprites.size():
        holder.add_child(_make_flat_sprite("Throw%d" % holder.get_child_count()))
    for index in range(holder.get_child_count()):
        var clone: Sprite3D = holder.get_child(index) as Sprite3D
        if clone == null:
            continue
        if index >= sprites.size():
            clone.visible = false
            continue
        _copy_throw_sprite(clone, sprites[index])
        sprites[index].visible = false

func _gather_sprites(node: Node, into: Array[SpriteBase3D]) -> void:
    if node is SpriteBase3D:
        into.append(node as SpriteBase3D)
    for child: Node in node.get_children():
        _gather_sprites(child, into)

func _copy_throw_sprite(clone: Sprite3D, src: SpriteBase3D) -> void:
    var tex: Texture2D = null
    if src is AnimatedSprite3D:
        var anim_sprite: AnimatedSprite3D = src as AnimatedSprite3D
        var frames: SpriteFrames = anim_sprite.sprite_frames
        if frames != null and frames.has_animation(anim_sprite.animation):
            var frame_count: int = frames.get_frame_count(anim_sprite.animation)
            if frame_count > 0:
                tex = frames.get_frame_texture(anim_sprite.animation, clampi(anim_sprite.frame, 0, frame_count - 1))
    elif src is Sprite3D:
        tex = (src as Sprite3D).texture
    if tex == null:
        clone.visible = false
        return
    clone.texture = tex
    clone.pixel_size = src.pixel_size
    clone.modulate = src.modulate
    clone.flip_h = src.flip_h
    clone.flip_v = src.flip_v
    var pos: Vector3 = src.global_position
    pos.y += ELEVATED_PAWN_Y_BIAS
    var basis: Basis = src.global_transform.basis
    if src.billboard != BaseMaterial3D.BILLBOARD_DISABLED:
        basis = Basis(Vector3.UP, src.global_rotation.y) * Basis(Vector3.RIGHT, deg_to_rad(-90.0))
    clone.transform = Transform3D(basis, pos)
    if src.billboard != BaseMaterial3D.BILLBOARD_DISABLED:
        clone.scale = src.scale
    clone.set_meta("source_sprite", src)
    clone.visible = true

func _reveal_sprites(node: Node) -> void:
    if node is SpriteBase3D:
        (node as SpriteBase3D).visible = true
    for child: Node in node.get_children():
        _reveal_sprites(child)

func _free_throw(raw_key: Variant) -> void:
    var holder: Node = popout_throws[raw_key]
    if is_instance_valid(holder):
        for child: Node in holder.get_children():
            if child.has_meta("source_sprite"):
                var src: Variant = child.get_meta("source_sprite")
                if src is SpriteBase3D and is_instance_valid(src):
                    (src as SpriteBase3D).visible = true
        holder.queue_free()
    popout_throws.erase(raw_key)

func _clear_elevated_throws() -> void:
    for raw_key: Variant in popout_throws.keys():
        _free_throw(raw_key)
    popout_throws.clear()

func _sync_one_shots() -> void:
    var keep: Array = []
    for entry: Variant in popout_one_shots:
        var row: Dictionary = entry as Dictionary
        var source: Node = row.get("source") as Node
        var holder: Node3D = row.get("holder") as Node3D
        if source == null or holder == null or not is_instance_valid(source) or not is_instance_valid(holder):
            if holder != null and is_instance_valid(holder):
                holder.queue_free()
            continue
        if not _on_building_roof(source.global_position):
            holder.visible = false
            if source is SpriteBase3D:
                (source as SpriteBase3D).visible = true
            keep.append(row)
            continue
        holder.visible = true
        if source is MeshInstance3D:
            var mesh_clone: MeshInstance3D = holder.get_node_or_null("Streak") as MeshInstance3D
            if mesh_clone != null:
                var pos: Vector3 = source.global_position
                pos.y += ELEVATED_PAWN_Y_BIAS
                mesh_clone.transform = Transform3D(source.global_transform.basis, pos)
        elif source is SpriteBase3D:
            var fx: Sprite3D = holder.get_node_or_null("Fx") as Sprite3D
            if fx != null:
                _copy_throw_sprite(fx, source as SpriteBase3D)
                (source as SpriteBase3D).visible = false
        keep.append(row)
    popout_one_shots = keep

func _clear_one_shots() -> void:
    for entry: Variant in popout_one_shots:
        var row: Dictionary = entry as Dictionary
        var holder: Node = row.get("holder") as Node
        if holder != null and is_instance_valid(holder):
            holder.queue_free()
    popout_one_shots.clear()

func ui_parent() -> Node:
    if xr_active and ui_viewport != null:
        return ui_viewport
    return get_parent()

func ui_input_viewport() -> Viewport:
    if xr_active and ui_viewport != null:
        return ui_viewport
    return get_viewport()

func follow_target(target: Vector3, delta: float) -> void:
    last_target = target
    var alpha: float = 1.0 - exp(-follow_speed * delta)
    smoothed_target = smoothed_target.lerp(target, alpha)

    if xr_active:
        _apply_quest_game_camera_pose()
        return

    global_position = smoothed_target

func _apply_quest_game_camera_pose() -> void:
    if camera == null:
        return
    var height: float = camera_height * QUEST_CAMERA_HEIGHT_FACTOR * quest_height_factor
    camera.global_position = smoothed_target + Vector3(0.0, height, 0.0)
    camera.global_rotation_degrees = Vector3(-90.0, 0.0, 0.0)
    camera.fov = DEATH_CAMERA_FOV if death_focus else camera_fov
    _update_popout_transform()

func set_death_focus(active: bool) -> void:
    if death_focus == active:
        return
    death_focus = active

    if _focus_tween != null and _focus_tween.is_valid():
        _focus_tween.kill()

    _focus_tween = create_tween()
    _focus_tween.set_parallel(true)
    _focus_tween.set_trans(Tween.TRANS_QUAD)
    _focus_tween.set_ease(Tween.EASE_OUT)

    if xr_active:
        _focus_tween.tween_property(
            self,
            "quest_height_factor",
            DEATH_CAMERA_HEIGHT_FACTOR if active else 1.0,
            0.62
        )
        _focus_tween.tween_property(
            camera,
            "fov",
            DEATH_CAMERA_FOV if active else camera_fov,
            0.62
        )
        return

    if camera == null:
        return
    var effective_height: float = camera_height * (DEATH_CAMERA_HEIGHT_FACTOR if active else 1.0)
    var target_fov: float = DEATH_CAMERA_FOV if active else camera_fov
    _focus_tween.tween_property(camera, "fov", target_fov, 0.62)
    match mode:
        PresentationMode.DESKTOP_TOPDOWN:
            _focus_tween.tween_property(camera, "position", Vector3(0.0, effective_height, 0.0), 0.62)
        PresentationMode.DIORAMA_PREVIEW, PresentationMode.VR_DIORAMA:
            _focus_tween.tween_property(camera, "position", Vector3(0.0, effective_height * 1.30, effective_height * 1.05), 0.62)

func toggle_diorama_preview() -> void:
    if xr_active:
        return
    if mode == PresentationMode.DESKTOP_TOPDOWN:
        set_mode(PresentationMode.DIORAMA_PREVIEW)
    else:
        set_mode(PresentationMode.DESKTOP_TOPDOWN)

func set_mode(new_mode: PresentationMode) -> void:
    if xr_active and new_mode != PresentationMode.VR_DIORAMA:
        return
    mode = new_mode
    _apply_camera_pose()

func _apply_camera_pose() -> void:
    if camera == null or xr_active:
        return
    var effective_height: float = camera_height * (DEATH_CAMERA_HEIGHT_FACTOR if death_focus else 1.0)
    camera.fov = DEATH_CAMERA_FOV if death_focus else camera_fov
    match mode:
        PresentationMode.DESKTOP_TOPDOWN:
            camera.position = Vector3(0.0, effective_height, 0.0)
            camera.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
        PresentationMode.DIORAMA_PREVIEW, PresentationMode.VR_DIORAMA:
            camera.position = Vector3(0.0, effective_height * 1.30, effective_height * 1.05)
            camera.look_at(global_position + Vector3(0.0, 0.60, 0.0), Vector3.UP)

func mode_label() -> String:
    match mode:
        PresentationMode.DIORAMA_PREVIEW:
            return "DIORAMA"
        PresentationMode.VR_DIORAMA:
            return "VR TABLETOP"
        _:
            return "TOPDOWN"

func openxr_available() -> bool:
    return XRServer.find_interface("OpenXR") != null

func quest_diorama_world_scale_hint() -> float:
    return QUEST_PANEL_SIZE.x
