class_name ViceQuestPresentationRig
extends Node3D

# Desktop keeps the original world camera.
# Quest uses the v0.6.17.0 tabletop path that already worked on hardware:
# XRCamera sees the real Downtown world, scaled down around the headset.
# The isolated SubViewport + layer-20 board is NOT used as the only view —
# that combination stays black on Quest 3 / GL Compatibility.
enum PresentationMode {
    DESKTOP_TOPDOWN,
    DIORAMA_PREVIEW,
    VR_DIORAMA,
}

const QUEST_WORLD_SCALE: float = 10.0
const QUEST_DEATH_WORLD_SCALE: float = 7.0
const QUEST_ORIGIN_OFFSET: Vector3 = Vector3(0.0, -8.0, 8.0)
const DEATH_CAMERA_HEIGHT_FACTOR: float = 0.58
const DEATH_CAMERA_FOV: float = 34.0

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
var popout_enabled: bool = false
var _headset_marker: MeshInstance3D

func configure(start_position: Vector3, height: float, fov: float, speed: float) -> void:
    camera_height = height
    camera_fov = fov
    follow_speed = speed
    last_target = start_position
    smoothed_target = start_position
    global_position = start_position

    _build_desktop_camera()
    _apply_camera_pose()

    if OS.has_feature("android"):
        _try_enable_openxr()

func _build_desktop_camera() -> void:
    camera = Camera3D.new()
    camera.name = "GameplayCamera"
    camera.projection = Camera3D.PROJECTION_PERSPECTIVE
    camera.fov = camera_fov
    camera.near = 0.25
    camera.far = 320.0
    camera.current = true
    add_child(camera)

func _try_enable_openxr() -> void:
    xr_interface = XRServer.find_interface("OpenXR")
    if xr_interface == null:
        return
    if not xr_interface.is_initialized() and not xr_interface.initialize():
        push_warning("Vice Quest: OpenXR interface could not initialize; falling back to flat camera.")
        return

    XRServer.primary_interface = xr_interface
    get_viewport().use_xr = true

    xr_origin = XROrigin3D.new()
    xr_origin.name = "QuestXROrigin"
    xr_origin.world_scale = QUEST_WORLD_SCALE
    xr_origin.current = true
    xr_origin.position = QUEST_ORIGIN_OFFSET
    add_child(xr_origin)

    xr_camera = XRCamera3D.new()
    xr_camera.name = "QuestXRCamera"
    xr_camera.near = 0.05
    xr_camera.far = 320.0
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

    camera.current = false
    xr_active = true
    mode = PresentationMode.VR_DIORAMA
    _build_headset_boot_marker()

func _build_headset_boot_marker() -> void:
    # Visible the instant OpenXR starts, so a late city load is never a black void.
    _headset_marker = MeshInstance3D.new()
    _headset_marker.name = "HeadsetBootMarker"
    _headset_marker.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    var mesh: QuadMesh = QuadMesh.new()
    mesh.size = Vector2(1.15, 0.22)
    _headset_marker.mesh = mesh
    _headset_marker.position = Vector3(0.0, -0.12, -1.15)
    var material: StandardMaterial3D = StandardMaterial3D.new()
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.albedo_color = Color("3dff9a")
    material.cull_mode = BaseMaterial3D.CULL_DISABLED
    material.no_depth_test = true
    material.render_priority = 16
    _headset_marker.material_override = material
    xr_camera.add_child(_headset_marker)

func sync_popout_chunks(_chunks: Dictionary, _atlas_texture: Texture2D) -> void:
    # Pop-out buildings stay a later hardware pass. Visibility of Downtown itself
    # must not depend on a SubViewport texture.
    return

func set_popout_enabled(active: bool) -> void:
    popout_enabled = active
    if _headset_marker != null:
        _headset_marker.visible = not active

func ui_parent() -> Node:
    # Keep HUD/boot on the main viewport so OpenXR can composite 2D.
    # The isolated UI SubViewport was parented to the black board.
    return get_parent()

func ui_input_viewport() -> Viewport:
    return get_viewport()

func follow_target(target: Vector3, delta: float) -> void:
    last_target = target
    var alpha: float = 1.0 - exp(-follow_speed * delta)
    smoothed_target = smoothed_target.lerp(target, alpha)
    global_position = global_position.lerp(target, alpha)

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

    if xr_active and xr_origin != null:
        var target_scale: float = QUEST_DEATH_WORLD_SCALE if active else QUEST_WORLD_SCALE
        _focus_tween.tween_property(xr_origin, "world_scale", target_scale, 0.62)
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
    return QUEST_WORLD_SCALE
