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

var camera: Camera3D
var game_viewport: SubViewport
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

func _build_quest_display() -> void:
    var board: Node3D = Node3D.new()
    board.name = "QuestTabletopBoard"
    board.position = QUEST_PANEL_POSITION
    board.rotation_degrees.x = QUEST_PANEL_TILT_DEGREES
    xr_origin.add_child(board)

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
    board.add_child(backing)

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
    board.add_child(screen)

func ui_parent() -> Node:
    if xr_active and game_viewport != null:
        return game_viewport
    return get_parent()

func ui_input_viewport() -> Viewport:
    if xr_active and game_viewport != null:
        return game_viewport
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
