from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
main_path = root/'scripts/main.gd'
cop_path = root/'scripts/cop.gd'
vehicle_data_path = root/'scripts/vehicle_data.gd'
vehicle_path = root/'scripts/vehicle.gd'

def rep(text, old, new, label):
    if old not in text:
        raise SystemExit(f'Missing patch anchor: {label}')
    return text.replace(old, new, 1)

vd = vehicle_data_path.read_text()
vd = rep(vd,
'    "cop_car": {"model": 12, "mass": 14.5, "brake": 2.0, "thrust": 0.150, "max_speed": 0.415, "anti_strength": 1.00},',
'''    "cop_car": {"model": 12, "mass": 14.5, "brake": 2.0, "thrust": 0.150, "max_speed": 0.415, "anti_strength": 1.00},
    "agent_car": {"model": 14, "mass": 15.0, "brake": 2.0, "thrust": 0.165, "max_speed": 0.300, "anti_strength": 0.80},
    "armed_land_roamer": {"model": 22, "mass": 12.0, "brake": 1.75, "thrust": 0.130, "max_speed": 0.240, "anti_strength": 1.00},
    "land_roamer": {"model": 30, "mass": 12.0, "brake": 1.75, "thrust": 0.130, "max_speed": 0.240, "anti_strength": 1.00},
    "swat_van": {"model": 52, "mass": 22.0, "brake": 2.0, "thrust": 0.175, "max_speed": 0.225, "anti_strength": 0.50},''',
'enforcement vehicle physics')
vehicle_data_path.write_text(vd)

veh = vehicle_path.read_text()
veh = rep(veh,
'    "cop_car": 2, "gt_a1": 3, "hachura": 3, "hot_dog_van": 8,',
'    "cop_car": 2, "agent_car": 3, "armed_land_roamer": 4, "land_roamer": 4, "swat_van": 8, "gt_a1": 3, "hachura": 3, "hot_dog_van": 8,',
'enforcement wrecks')
veh = veh.replace('"box_truck", "benson", "hot_dog_van", "ice_cream_van", "van", "tow_truck", "truck_cab_sx", "sports_limousine", "pacifier", "dementia"',
                  '"box_truck", "benson", "hot_dog_van", "ice_cream_van", "van", "tow_truck", "truck_cab_sx", "sports_limousine", "pacifier", "dementia", "swat_van", "armed_land_roamer", "land_roamer"')
vehicle_path.write_text(veh)

cop = cop_path.read_text()
cop = rep(cop,
'var _label: Label3D',
'''var _label: Label3D
var enforcement_role: String = "police"
var response_active: bool = true
var move_speed: float = SPEED
var attack_damage: int = 14
var attack_vehicle_damage: int = 8
var attack_range: float = 16.0
var attack_cooldown: float = 0.62
var weapon_id: int = 0
var shoot_on_foot: bool = false
var profile_hp: int = 90''',
'cop profile vars')
cop = rep(cop,
'''    if _visual != null:
        # Keep cops visually distinct while still using the original GTA2 ped sets.
        _visual.setup(posmod(cop_id + 7, 12), 0)
    _refresh_visuals()''',
'''    set_enforcement_profile("police")
    _refresh_visuals()''',
'cop setup')

anchor = 'func set_motion_state(moving: bool, armed: bool = false) -> void:'
profile_code = '''func set_enforcement_profile(role: String) -> void:
    enforcement_role = role
    var skin: int = 8
    profile_hp = 90
    move_speed = SPEED
    attack_damage = 14
    attack_vehicle_damage = 8
    attack_range = 16.0
    attack_cooldown = 0.62
    weapon_id = 0
    shoot_on_foot = false
    match role:
        "police_low":
            skin = 8
            move_speed = 4.35
            attack_damage = 12
            attack_vehicle_damage = 6
            attack_cooldown = 0.72
        "police":
            skin = 8
            move_speed = 5.35
        "armored_police":
            skin = 9
            profile_hp = 125
            move_speed = 5.55
            attack_damage = 16
            attack_vehicle_damage = 10
            attack_cooldown = 0.50
        "swat":
            skin = 10
            profile_hp = 170
            move_speed = 5.65
            attack_damage = 14
            attack_vehicle_damage = 9
            attack_range = 17.5
            attack_cooldown = 0.13
            weapon_id = 1
            shoot_on_foot = true
        "agent_shotgun":
            skin = 6
            profile_hp = 135
            move_speed = 5.85
            attack_damage = 30
            attack_vehicle_damage = 14
            attack_range = 12.5
            attack_cooldown = 0.78
            weapon_id = 6
            shoot_on_foot = true
        "agent_smg":
            skin = 6
            profile_hp = 135
            move_speed = 5.85
            attack_damage = 13
            attack_vehicle_damage = 8
            attack_range = 17.0
            attack_cooldown = 0.11
            weapon_id = 10
            shoot_on_foot = true
        "soldier":
            skin = 11
            profile_hp = 155
            move_speed = 5.75
            attack_damage = 15
            attack_vehicle_damage = 10
            attack_range = 18.0
            attack_cooldown = 0.10
            weapon_id = 1
            shoot_on_foot = true
    if is_alive:
        hp = profile_hp
    if _visual != null:
        _visual.setup(skin, 0)
    _refresh_visuals()

func set_response_active(active: bool) -> void:
    response_active = active
    if not active:
        velocity = Vector3.ZERO
        _moving = false
        _armed = false
    _refresh_visuals()

'''
if anchor not in cop:
    raise SystemExit('Missing cop motion anchor')
cop = cop.replace(anchor, profile_code + anchor, 1)
cop = rep(cop,
'''    # Keep the body visible after death so the death sequence can finish.
    visible = true
    var physically_present: bool = is_alive and not is_incapacitated()''',
'''    visible = response_active
    var physically_present: bool = response_active and is_alive and not is_incapacitated()''',
'cop active visuals')
cop = rep(cop,
'''    if _label != null:
        _label.visible = is_alive''',
'''    if _label != null:
        _label.visible = false''',
'hide cop debug label')
cop = rep(cop,
'''func _process(delta: float) -> void:
    if multiplayer.is_server():
        return''',
'''func _process(delta: float) -> void:
    if multiplayer.is_server() or not response_active:
        return''',
'cop client inactive skip')
cop_path.write_text(cop)

main = main_path.read_text()
main = main.replace('const POLICE_RESERVE_COUNT: int = 12', 'const POLICE_RESERVE_COUNT: int = 24')
main = main.replace('const POLICE_PURSUIT_CAR_COUNT: int = 6', 'const POLICE_PURSUIT_CAR_COUNT: int = 8')
main = main.replace('const MAX_WANTED_LEVEL: int = 5', 'const MAX_WANTED_LEVEL: int = 6')

main = rep(main,
'var wanted_label: Label\\nvar money_digit_rects: Array[TextureRect] = []',
'''var wanted_label: Label
var wanted_head_rects: Array[TextureRect] = []
var gta2_health_hearts: Label
var gta2_ammo_label: Label
var gta2_respect_bars: Dictionary[int, ProgressBar] = {}
var money_digit_rects: Array[TextureRect] = []''',
'HUD vars')

old_build_cops = '''func _build_cops() -> void:
    _create_cop(1, DOWNTOWN_DATA.COP1)
    _create_cop(2, DOWNTOWN_DATA.COP2)
    _create_cop(3, DOWNTOWN_DATA.COP3)
    _create_cop(4, DOWNTOWN_DATA.COP4)
    for reserve_index in range(POLICE_RESERVE_COUNT):
        var reserve_id: int = 20 + reserve_index
        _create_cop(reserve_id, Vector3(-80.0 - float(reserve_index) * 2.0, 0.12, -80.0))
        police_response_cop_ids.append(reserve_id)
'''
new_build_cops = '''func _build_cops() -> void:
    for reserve_index in range(POLICE_RESERVE_COUNT):
        var reserve_id: int = 20 + reserve_index
        _create_cop(reserve_id, Vector3(-80.0 - float(reserve_index) * 2.0, 0.12, -80.0))
        if cops.has(reserve_id):
            cops[reserve_id].set_response_active(false)
        police_response_cop_ids.append(reserve_id)
'''
main = rep(main, old_build_cops, new_build_cops, 'remove static cops')
main = main.replace('''    # Dedicated, non-traffic test tank within interaction range of HOST. It is
    # offset to the west so it neither overlaps the player nor the weapon row.
    _create_vehicle(18, Vector3(320.00, 0.10, 323.75), PI * 0.5, "tank")
''', '')

start = main.index('func _server_update_pursuit_forces(delta: float) -> void:')
marker = '    # Gang cars reuse the same lightweight pursuit steering.'
mid = main.index(marker, start)
new_pursuit = '''func _law_roles_for_level(level: int) -> Array[String]:
    match level:
        1:
            return ["police_low", "police_low"]
        2:
            return ["police", "police", "police", "police"]
        3:
            return ["armored_police", "armored_police", "police", "police", "police", "police"]
        4:
            return ["swat", "swat", "swat", "swat", "swat", "swat", "swat", "swat"]
        5:
            return ["agent_shotgun", "agent_smg", "agent_shotgun", "agent_smg", "agent_shotgun", "agent_smg"]
        6:
            return ["soldier", "soldier", "soldier", "soldier", "soldier", "soldier", "soldier", "soldier", "soldier", "soldier"]
        _:
            return []

func _law_vehicle_variants_for_level(level: int) -> Array[String]:
    match level:
        1:
            return ["cop_car"]
        2:
            return ["cop_car", "cop_car"]
        3:
            return ["cop_car", "cop_car", "cop_car"]
        4:
            return ["cop_car", "cop_car", "swat_van", "swat_van"]
        5:
            return ["agent_car", "agent_car", "agent_car"]
        6:
            return ["armed_land_roamer", "land_roamer", "pacifier", "tank"]
        _:
            return []

func _server_update_pursuit_forces(delta: float) -> void:
    police_response_accumulator += delta
    if police_response_accumulator < POLICE_RESPONSE_INTERVAL:
        return
    police_response_accumulator = 0.0
    var wanted_target_id: int = 0
    var highest_wanted: int = 0
    for raw_player_id in players.keys():
        var player_id: int = int(raw_player_id)
        var level: int = int(wanted_levels.get(player_id, 0))
        if alive_states.get(player_id, false) and level > highest_wanted:
            highest_wanted = level
            wanted_target_id = player_id

    if wanted_target_id == 0:
        for reserve_id: int in police_response_cop_ids:
            if not cops.has(reserve_id):
                continue
            var idle_cop: ViceQuestCop = cops[reserve_id]
            if idle_cop.response_active:
                idle_cop.set_response_active(false)
                _sync_cop_profile.rpc(reserve_id, idle_cop.enforcement_role, false)
        for police_vehicle_id: int in police_pursuit_vehicle_ids:
            if vehicles.has(police_vehicle_id):
                vehicles[police_vehicle_id].clear_pursuit()
                vehicles[police_vehicle_id].set_stream_active(false)
                vehicle_stream_states[police_vehicle_id] = false
                _sync_vehicle_stream_state.rpc(police_vehicle_id, false)
        return

    var target: Vector3 = players[wanted_target_id].position
    if player_vehicle.has(wanted_target_id) and vehicles.has(player_vehicle[wanted_target_id]):
        target = vehicles[player_vehicle[wanted_target_id]].position

    var desired_roles: Array[String] = _law_roles_for_level(highest_wanted)
    for pool_index in range(police_response_cop_ids.size()):
        var reserve_id: int = police_response_cop_ids[pool_index]
        if not cops.has(reserve_id):
            continue
        var reserve_cop: ViceQuestCop = cops[reserve_id]
        if pool_index >= desired_roles.size():
            if reserve_cop.response_active:
                reserve_cop.set_response_active(false)
                _sync_cop_profile.rpc(reserve_id, reserve_cop.enforcement_role, false)
            continue
        var desired_role: String = desired_roles[pool_index]
        var was_active: bool = reserve_cop.response_active
        if reserve_cop.enforcement_role != desired_role:
            reserve_cop.set_enforcement_profile(desired_role)
        reserve_cop.set_response_active(true)
        _sync_cop_profile.rpc(reserve_id, desired_role, true)
        if not reserve_cop.is_alive:
            continue
        if not was_active or _planar_distance(reserve_cop.position, target) > 72.0:
            var cop_spawn: Vector3 = _response_spawn_point(target, false, reserve_id + highest_wanted * 31)
            reserve_cop.position = cop_spawn
            reserve_cop.target_position = cop_spawn
            reserve_cop.facing = (target - cop_spawn).normalized()
        _sync_cop_state.rpc(reserve_id, reserve_cop.position, reserve_cop.facing, true, reserve_cop.hp)

    var desired_variants: Array[String] = _law_vehicle_variants_for_level(highest_wanted)
    for pool_index in range(police_pursuit_vehicle_ids.size()):
        var police_vehicle_id: int = police_pursuit_vehicle_ids[pool_index]
        if not vehicles.has(police_vehicle_id):
            continue
        var police_vehicle: ViceQuestVehicle = vehicles[police_vehicle_id]
        if pool_index >= desired_variants.size():
            police_vehicle.clear_pursuit()
            police_vehicle.set_stream_active(false)
            vehicle_stream_states[police_vehicle_id] = false
            _sync_vehicle_stream_state.rpc(police_vehicle_id, false)
            continue
        var desired_variant: String = desired_variants[pool_index]
        if not police_vehicle.stream_active or police_vehicle.variant_id != desired_variant or _planar_distance(police_vehicle.position, target) > 165.0:
            var vehicle_spawn: Vector3 = _response_spawn_point(target, true, police_vehicle_id + highest_wanted * 43)
            var direction: Vector3 = target - vehicle_spawn
            direction.y = 0.0
            var heading: float = atan2(direction.z, direction.x)
            var response_route: Array[Vector3] = [vehicle_spawn, target]
            police_vehicle.recycle_ambient(vehicle_spawn, heading, response_route, police_vehicle.max_forward_speed * 0.94, desired_variant)
            police_vehicle.ai_cruise_speed = police_vehicle.max_forward_speed * 0.94
            police_vehicle.set_meta("response_role", "law")
            vehicle_stream_states[police_vehicle_id] = true
            _sync_ambient_vehicle_activation.rpc(police_vehicle_id, police_vehicle.position, police_vehicle.heading, police_vehicle.current_speed, desired_variant, 0)
        police_vehicle.set_pursuit_target(target, "police")
'''
main = main[:start] + new_pursuit + main[mid:]
main = main.replace('String(gang_vehicle.get_meta("response_role", "")) == "police"',
                    'String(gang_vehicle.get_meta("response_role", "")) in ["police", "law"]')

insert_anchor = '@rpc("authority", "call_local", "unreliable")\\nfunc _sync_cop_state('
sync_profile = '''@rpc("authority", "call_local", "reliable")
func _sync_cop_profile(cop_id: int, role: String, active: bool) -> void:
    if cops.has(cop_id):
        cops[cop_id].set_enforcement_profile(role)
        cops[cop_id].set_response_active(active)

'''
if insert_anchor not in main:
    raise SystemExit('Missing sync cop anchor')
main = main.replace(insert_anchor, sync_profile + insert_anchor, 1)

main = rep(main,
'''        if wanted_level <= 0:
            continue
        var wanted_timer: float = wanted_decay_timers[wanted_id] if wanted_decay_timers.has(wanted_id) else WANTED_DECAY_FIRST''',
'''        if wanted_level <= 0:
            continue
        if wanted_level > 1:
            continue
        var wanted_timer: float = wanted_decay_timers[wanted_id] if wanted_decay_timers.has(wanted_id) else WANTED_DECAY_FIRST''',
'wanted decay')

main = rep(main,
'''        var cop: ViceQuestCop = cops[cop_id]
        cop_fire_cooldowns[cop_id] = maxf(0.0, cop_fire_cooldowns[cop_id] - delta)
        if not cop.is_alive:''',
'''        var cop: ViceQuestCop = cops[cop_id]
        if not cop.response_active:
            continue
        cop_fire_cooldowns[cop_id] = maxf(0.0, cop_fire_cooldowns[cop_id] - delta)
        if not cop.is_alive:''',
'cop inactive server skip')

old_engage = '''            if best_distance > 4.2:
                cop.set_motion_state(true, false)
                cop.velocity = cop.facing * ViceQuestCop.SPEED
                cop.move_and_slide()
                cop.position.y = sample_surface_height(cop.position, cop.position.y - PLAYER_Y) + PLAYER_Y
            else:
                cop.set_motion_state(false, true)
                cop.velocity = Vector3.ZERO
                if cop_fire_cooldowns[cop_id] <= 0.0:
                    cop_fire_cooldowns[cop_id] = COP_FIRE_COOLDOWN
                    var start: Vector3 = cop.position + Vector3(0.0, 0.72, 0.0) + cop.facing * 0.36
                    var end: Vector3 = start + cop.facing * COP_RANGE
                    var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(start, end)
                    query.exclude = [cop.get_rid()]
                    query.collision_mask = 1
                    var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
                    var visual_end: Vector3 = end
                    if not hit.is_empty():
                        visual_end = hit["position"]
                        var collider: Object = hit["collider"]
                        if collider is ViceQuestPlayer:
                            var target_player: ViceQuestPlayer = collider as ViceQuestPlayer
                            if alive_states.has(target_player.peer_id) and alive_states[target_player.peer_id]:
                                _damage_player(target_player.peer_id, COP_DAMAGE, -1)
                        elif collider is ViceQuestVehicle:
                            var target_vehicle: ViceQuestVehicle = collider as ViceQuestVehicle
                            if target_vehicle.driver_id == best_player_id and not target_vehicle.is_destroyed:
                                _damage_vehicle(target_vehicle.vehicle_id, 8, -1)
                    _play_shot_effect.rpc(0, start, visual_end)'''
new_engage = '''            var target_is_in_vehicle: bool = player_vehicle.has(best_player_id) and vehicles.has(player_vehicle[best_player_id])
            var lethal_response: bool = cop.shoot_on_foot or target_is_in_vehicle
            var stop_distance: float = 4.2 if lethal_response else 1.20
            if best_distance > stop_distance:
                cop.set_motion_state(true, lethal_response)
                cop.velocity = cop.facing * cop.move_speed
                cop.move_and_slide()
                cop.position.y = sample_surface_height(cop.position, cop.position.y - PLAYER_Y) + PLAYER_Y
            else:
                cop.set_motion_state(false, lethal_response)
                cop.velocity = Vector3.ZERO
                if lethal_response and cop_fire_cooldowns[cop_id] <= 0.0:
                    cop_fire_cooldowns[cop_id] = cop.attack_cooldown
                    var start: Vector3 = cop.position + Vector3(0.0, 0.72, 0.0) + cop.facing * 0.36
                    var end: Vector3 = start + cop.facing * cop.attack_range
                    var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(start, end)
                    query.exclude = [cop.get_rid()]
                    query.collision_mask = 1
                    var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
                    var visual_end: Vector3 = end
                    if not hit.is_empty():
                        visual_end = hit["position"]
                        var collider: Object = hit["collider"]
                        if collider is ViceQuestPlayer:
                            var target_player: ViceQuestPlayer = collider as ViceQuestPlayer
                            if alive_states.has(target_player.peer_id) and alive_states[target_player.peer_id]:
                                _damage_player(target_player.peer_id, cop.attack_damage, -1)
                        elif collider is ViceQuestVehicle:
                            var target_vehicle: ViceQuestVehicle = collider as ViceQuestVehicle
                            if target_vehicle.driver_id == best_player_id and not target_vehicle.is_destroyed:
                                _damage_vehicle(target_vehicle.vehicle_id, cop.attack_vehicle_damage, -1)
                    _play_shot_effect.rpc(0, start, visual_end, cop.weapon_id)'''
main = rep(main, old_engage, new_engage, 'role-aware cop combat')

main = main.replace('func _play_shot_effect(shooter_id: int, start: Vector3, end: Vector3) -> void:',
                    'func _play_shot_effect(shooter_id: int, start: Vector3, end: Vector3, weapon_override: int = -1) -> void:')
main = rep(main,
'''        var shot_weapon: int = WEAPON_DATA.PISTOL
        var tank_cannon: bool = false
        if shooter_id > 0:''',
'''        var shot_weapon: int = weapon_override if weapon_override >= 0 else WEAPON_DATA.PISTOL
        var tank_cannon: bool = false
        if shooter_id > 0 and weapon_override < 0:''',
'law shot audio')

main = rep(main,
'''    quest_label.text = "MISSIONS // Answer a ringing gang phone for work."
    _build_wasted_overlay(canvas)''',
'''    quest_label.text = "MISSIONS // Answer a ringing gang phone for work."
    _apply_gta2_hud_style()
    _build_wasted_overlay(canvas)''',
'apply original HUD')

hud_code = r'''func _transparent_panel(control: Control) -> void:
    if control == null or not (control is Panel):
        return
    var style: StyleBoxFlat = StyleBoxFlat.new()
    style.bg_color = Color(0.0, 0.0, 0.0, 0.0)
    (control as Panel).add_theme_stylebox_override("panel", style)

func _apply_gta2_hud_style() -> void:
    if game_hud_root == null:
        return
    if network_status_label != null:
        network_status_label.get_parent().visible = false
    if population_status_label != null:
        population_status_label.visible = false
    if hint_label != null:
        hint_label.visible = false
    if vehicle_status_label != null:
        vehicle_status_label.get_parent().visible = false
    if not weapon_icon_rects.is_empty():
        var any_icon: TextureRect = weapon_icon_rects.values()[0]
        if any_icon != null:
            any_icon.get_parent().visible = false

    gta2_respect_bars.clear()
    var respect_root: VBoxContainer = VBoxContainer.new()
    respect_root.name = "GTA2RespectOMeter"
    respect_root.position = Vector2(14, 18)
    respect_root.size = Vector2(180, 112)
    respect_root.add_theme_constant_override("separation", 5)
    game_hud_root.add_child(respect_root)
    for gang_id: int in [GANG_DATA.YAKUZA, GANG_DATA.ZAIBATSU, GANG_DATA.LOONIES]:
        var row: HBoxContainer = HBoxContainer.new()
        row.custom_minimum_size = Vector2(174, 30)
        respect_root.add_child(row)
        var badge: Label = Label.new()
        var definition: Dictionary = GANG_DATA.definition(gang_id)
        badge.text = String(definition["name"]).substr(0, 1)
        badge.custom_minimum_size = Vector2(28, 28)
        badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
        badge.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
        badge.add_theme_font_size_override("font_size", 22)
        badge.add_theme_color_override("font_color", Color(definition["color"]))
        row.add_child(badge)
        var bar: ProgressBar = ProgressBar.new()
        bar.min_value = 0.0
        bar.max_value = 20.0
        bar.value = 10.0
        bar.show_percentage = false
        bar.custom_minimum_size = Vector2(136, 18)
        var bg: StyleBoxFlat = StyleBoxFlat.new()
        bg.bg_color = Color(0.03, 0.03, 0.035, 0.82)
        bg.border_color = Color(0.75, 0.75, 0.70, 0.9)
        bg.set_border_width_all(2)
        bar.add_theme_stylebox_override("background", bg)
        var fill: StyleBoxFlat = StyleBoxFlat.new()
        fill.bg_color = Color(definition["color"])
        bar.add_theme_stylebox_override("fill", fill)
        row.add_child(bar)
        gta2_respect_bars[gang_id] = bar

    if wanted_label != null:
        var wanted_panel: Control = wanted_label.get_parent()
        _transparent_panel(wanted_panel)
        wanted_panel.position = Vector2(792, 16)
        wanted_panel.size = Vector2(204, 40)
        wanted_label.visible = false
        wanted_head_rects.clear()
        var head_texture: Texture2D = load("res://assets/ui/gta2/wanted_head_alert.png") as Texture2D
        for i in range(MAX_WANTED_LEVEL):
            var head: TextureRect = TextureRect.new()
            head.texture = head_texture
            head.position = Vector2(i * 32, 2)
            head.size = Vector2(30, 30)
            head.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
            head.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
            head.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
            head.visible = false
            wanted_panel.add_child(head)
            wanted_head_rects.append(head)

    if not money_digit_rects.is_empty():
        var money_panel: Control = money_digit_rects[0].get_parent()
        _transparent_panel(money_panel)
        money_panel.position = Vector2(990, 14)
        money_panel.size = Vector2(276, 44)
        for child in money_panel.get_children():
            if child is Label:
                child.visible = false
        for i in range(money_digit_rects.size()):
            money_digit_rects[i].position = Vector2(12 + i * 27, 4)
            money_digit_rects[i].size = Vector2(26, 36)

    if weapon_current_icon != null:
        var combat_panel: Control = weapon_current_icon.get_parent()
        _transparent_panel(combat_panel)
        combat_panel.position = Vector2(1088, 66)
        combat_panel.size = Vector2(176, 118)
        weapon_current_icon.position = Vector2(82, 2)
        weapon_current_icon.size = Vector2(86, 74)
        if weapon_label != null:
            weapon_label.visible = false
        if health_label != null:
            health_label.visible = false
        if health_bar != null:
            health_bar.visible = false
        gta2_ammo_label = Label.new()
        gta2_ammo_label.position = Vector2(8, 52)
        gta2_ammo_label.size = Vector2(72, 34)
        gta2_ammo_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
        gta2_ammo_label.add_theme_font_size_override("font_size", 24)
        gta2_ammo_label.add_theme_color_override("font_color", Color("e8e5bd"))
        combat_panel.add_child(gta2_ammo_label)
        gta2_health_hearts = Label.new()
        gta2_health_hearts.position = Vector2(4, 3)
        gta2_health_hearts.size = Vector2(170, 36)
        gta2_health_hearts.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
        gta2_health_hearts.add_theme_font_size_override("font_size", 25)
        gta2_health_hearts.add_theme_color_override("font_color", Color("e43b44"))
        combat_panel.add_child(gta2_health_hearts)
        if combat_message_label != null:
            combat_message_label.reparent(game_hud_root)
            combat_message_label.position = Vector2(330, 660)
            combat_message_label.size = Vector2(620, 34)
            combat_message_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
            combat_message_label.add_theme_font_size_override("font_size", 20)

    if quest_label != null:
        var quest_panel: Control = quest_label.get_parent()
        _transparent_panel(quest_panel)
        quest_panel.position = Vector2(310, 596)
        quest_panel.size = Vector2(660, 60)
        quest_label.position = Vector2.ZERO
        quest_label.size = quest_panel.size
        quest_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
        quest_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
        quest_label.add_theme_font_size_override("font_size", 18)
    _update_gta2_respect_ui()
    _update_gta2_health_ammo_ui()

func _update_gta2_respect_ui() -> void:
    if gta2_respect_bars.is_empty():
        return
    var local_id: int = multiplayer.get_unique_id()
    var respect: Dictionary = player_gang_respect.get(local_id, {})
    for raw_gang_id: Variant in gta2_respect_bars.keys():
        var gang_id: int = int(raw_gang_id)
        var bar: ProgressBar = gta2_respect_bars[gang_id]
        bar.value = float(clampi(int(respect.get(gang_id, 0)), -10, 10) + 10)

func _update_gta2_health_ammo_ui() -> void:
    var local_id: int = multiplayer.get_unique_id()
    var current_hp: int = int(healths.get(local_id, MAX_HP))
    if gta2_health_hearts != null:
        var hearts: int = clampi(ceili(float(current_hp) / (float(MAX_HP) / 5.0)), 0, 5)
        gta2_health_hearts.text = "♥".repeat(hearts)
    if gta2_ammo_label != null:
        var weapon_id: int = int(player_current_weapon.get(local_id, WEAPON_DATA.PISTOL))
        var definition: Dictionary = WEAPON_DATA.definition(weapon_id)
        if bool(definition.get("uses_ammo", true)):
            gta2_ammo_label.text = str(int(player_ammo_clip.get(local_id, int(definition["clip_size"]))))
        else:
            gta2_ammo_label.text = "∞"

'''
insert_at = main.index('func _build_wasted_overlay(canvas: CanvasLayer) -> void:')
main = main[:insert_at] + hud_code + main[insert_at:]

old_wanted_ui = '''func _update_wanted_ui() -> void:
    if wanted_label == null:
        return
    var local_id: int = multiplayer.get_unique_id()
    var level: int = wanted_levels[local_id] if wanted_levels.has(local_id) else 0
    var stars: String = ""
    for i in range(MAX_WANTED_LEVEL):
        stars += "★" if i < level else "☆"
    wanted_label.text = "WANTED  %s" % stars
'''
new_wanted_ui = '''func _update_wanted_ui() -> void:
    var local_id: int = multiplayer.get_unique_id()
    var level: int = wanted_levels[local_id] if wanted_levels.has(local_id) else 0
    if wanted_label != null:
        wanted_label.text = "WANTED %d" % level
    for i in range(wanted_head_rects.size()):
        wanted_head_rects[i].visible = i < level
'''
main = rep(main, old_wanted_ui, new_wanted_ui, 'wanted heads')

main = rep(main,
'''    respect[gang_id] = clampi(value, -10, 10)
    player_gang_respect[player_id] = respect
''',
'''    respect[gang_id] = clampi(value, -10, 10)
    player_gang_respect[player_id] = respect
    if player_id == multiplayer.get_unique_id():
        _update_gta2_respect_ui()
''',
'respect refresh')
main = rep(main,
'''    if not alive:
        health_label.text = "WASTED // respawning..."
    _update_weapon_ui()
''',
'''    if not alive:
        health_label.text = "WASTED // respawning..."
    _update_weapon_ui()
    _update_gta2_health_ammo_ui()
''',
'health HUD refresh')
main = rep(main,
'''    if weapon_current_icon != null:
        weapon_current_icon.texture = load(String(weapon_def["icon"])) as Texture2D
    var owned: Dictionary''',
'''    if weapon_current_icon != null:
        weapon_current_icon.texture = load(String(weapon_def["icon"])) as Texture2D
    _update_gta2_health_ammo_ui()
    var owned: Dictionary''',
'ammo HUD refresh')

main_path.write_text(main)
print('Applied v0.6.18 GTA2 roof/law/HUD upgrade.')
