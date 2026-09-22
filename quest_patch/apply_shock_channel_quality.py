from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
audio_path = root / "scripts" / "audio_manager.gd"
main = main_path.read_text(encoding="utf-8")
audio = audio_path.read_text(encoding="utf-8")


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing shock quality anchor: {label}")
    return text.replace(old, new, 1)


# 1) Extra channel state for hysteresis.
main = must_replace(
    main,
    """var shock_channel_active: Dictionary = {}
var shock_channel_visual_clock: Dictionary = {}
var shock_channel_damage_clock: Dictionary = {}
var local_shock_channel_sent: bool = false
const SHOCK_CHANNEL_PRIMARY_RANGE: float = 11.5
const SHOCK_CHANNEL_CHAIN_RANGE: float = 5.8
const SHOCK_CHANNEL_MAX_TARGETS: int = 6
const SHOCK_CHANNEL_VISUAL_INTERVAL: float = 0.075
const SHOCK_CHANNEL_DAMAGE_INTERVAL: float = 0.28
""",
    """var shock_channel_active: Dictionary = {}
var shock_channel_visual_clock: Dictionary = {}
var shock_channel_damage_clock: Dictionary = {}
var shock_channel_locked: Dictionary = {}
var local_shock_channel_sent: bool = false
const SHOCK_CHANNEL_PRIMARY_RANGE: float = 11.5
const SHOCK_CHANNEL_CHAIN_RANGE: float = 5.8
const SHOCK_CHANNEL_MAX_TARGETS: int = 6
const SHOCK_CHANNEL_VISUAL_INTERVAL: float = 0.075
const SHOCK_CHANNEL_DAMAGE_INTERVAL: float = 0.28
const SHOCK_CHANNEL_HYSTERESIS: float = 1.18
""",
    "channel state",
)

# 2) Quest/desktop fire uses input_bridge, not an unmapped "attack" action.
main = must_replace(
    main,
    '    var wants_channel: bool = _shock_channel_should_be_active(local_id) and Input.is_action_pressed("attack")\n',
    "    var wants_channel: bool = _shock_channel_should_be_active(local_id) and local_fire_down()\n",
    "channel input",
)

# 3) Clear hysteresis locks when the channel stops.
main = must_replace(
    main,
    """    else:
        shock_channel_active.erase(player_id)
        shock_channel_visual_clock.erase(player_id)
        shock_channel_damage_clock.erase(player_id)
        _sync_shock_channel_visual.rpc(player_id, PackedVector3Array())
""",
    """    else:
        shock_channel_active.erase(player_id)
        shock_channel_visual_clock.erase(player_id)
        shock_channel_damage_clock.erase(player_id)
        shock_channel_locked.erase(player_id)
        _sync_shock_channel_visual.rpc(player_id, PackedVector3Array())
        if players.has(player_id):
            _sync_shock_loop.rpc(player_id, false, players[player_id].position)
""",
    "channel stop cleanup",
)

# 4) LOS + hysteresis tree. Replace the distance-only builder.
old_tree = """func _build_shock_target_tree(attacker_id: int) -> Dictionary:
    var result: Dictionary = {
        "edges": PackedVector3Array(),
        "targets": [],
    }
    if not players.has(attacker_id):
        return result

    var shooter: ViceQuestPlayer = players[attacker_id]
    var root_pos: Vector3 = shooter.position + Vector3(0.0, 0.62, 0.0) + shooter.facing * 0.46
    var candidates: Array[Dictionary] = _shock_collect_targets(attacker_id)
    if candidates.is_empty():
        return result

    var connected: Array[Dictionary] = [{
        "kind": "root",
        "id": -1,
        "pos": root_pos,
    }]
    var used: Dictionary = {}
    var edges: PackedVector3Array = PackedVector3Array()
    var selected_targets: Array[Dictionary] = []

    while selected_targets.size() < SHOCK_CHANNEL_MAX_TARGETS:
        var best_candidate: int = -1
        var best_parent: int = -1
        var best_distance: float = 1000000.0

        for candidate_index in range(candidates.size()):
            if used.has(candidate_index):
                continue
            var candidate: Dictionary = candidates[candidate_index]
            var candidate_pos: Vector3 = candidate["pos"]
            for parent_index in range(connected.size()):
                var parent: Dictionary = connected[parent_index]
                var parent_pos: Vector3 = parent["pos"]
                var max_range: float = SHOCK_CHANNEL_PRIMARY_RANGE if String(parent["kind"]) == "root" else SHOCK_CHANNEL_CHAIN_RANGE
                var distance: float = parent_pos.distance_to(candidate_pos)
                if distance <= max_range and distance < best_distance:
                    best_distance = distance
                    best_candidate = candidate_index
                    best_parent = parent_index

        if best_candidate < 0 or best_parent < 0:
            break

        var chosen: Dictionary = candidates[best_candidate]
        var parent: Dictionary = connected[best_parent]
        edges.append(parent["pos"])
        edges.append(chosen["pos"])
        selected_targets.append(chosen)
        connected.append(chosen)
        used[best_candidate] = true

    result["edges"] = edges
    result["targets"] = selected_targets
    return result
"""

new_tree = r'''func _shock_target_key(target: Dictionary) -> String:
    return "%s:%d" % [String(target.get("kind", "")), int(target.get("id", -1))]

func _shock_exclude_moving_rids() -> Array[RID]:
    var exclude: Array[RID] = []
    for raw_id: Variant in players.keys():
        var player_id: int = int(raw_id)
        if players.has(player_id):
            exclude.append(players[player_id].get_rid())
    for raw_id: Variant in cops.keys():
        var cop_id: int = int(raw_id)
        if cops.has(cop_id):
            exclude.append(cops[cop_id].get_rid())
    for raw_id: Variant in civilians.keys():
        var civilian_id: int = int(raw_id)
        if civilians.has(civilian_id):
            exclude.append(civilians[civilian_id].get_rid())
    for raw_id: Variant in vehicles.keys():
        var vehicle_id: int = int(raw_id)
        if vehicles.has(vehicle_id):
            exclude.append(vehicles[vehicle_id].get_rid())
    return exclude

func _shock_has_line_of_sight(from_pos: Vector3, to_pos: Vector3) -> bool:
    if from_pos.distance_to(to_pos) <= 0.08:
        return true
    var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(from_pos, to_pos)
    query.collision_mask = 1
    query.collide_with_areas = false
    query.exclude = _shock_exclude_moving_rids()
    var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
    return hit.is_empty()

func _shock_link_allowed(parent: Dictionary, candidate: Dictionary, range_scale: float) -> bool:
    var parent_pos: Vector3 = parent["pos"]
    var candidate_pos: Vector3 = candidate["pos"]
    var max_range: float = SHOCK_CHANNEL_PRIMARY_RANGE if String(parent["kind"]) == "root" else SHOCK_CHANNEL_CHAIN_RANGE
    if parent_pos.distance_to(candidate_pos) > max_range * range_scale:
        return false
    return _shock_has_line_of_sight(parent_pos, candidate_pos)

func _shock_consume_channel_ammo(attacker_id: int) -> bool:
    var weapon_def: Dictionary = WEAPON_DATA.definition(WEAPON_DATA.STUN_GUN)
    if not bool(weapon_def.get("uses_ammo", true)):
        return true
    if not player_ammo_clip.has(attacker_id) or not player_ammo_reserve.has(attacker_id):
        return false
    if player_ammo_clip[attacker_id] <= 0:
        if player_ammo_reserve[attacker_id] > 0:
            _server_reload(attacker_id)
        return player_ammo_clip.get(attacker_id, 0) > 0
    player_ammo_clip[attacker_id] -= 1
    _sync_ammo_state.rpc(attacker_id, player_ammo_clip[attacker_id], player_ammo_reserve[attacker_id], float(reload_timers.get(attacker_id, 0.0)))
    if player_ammo_clip[attacker_id] <= 0 and player_ammo_reserve[attacker_id] > 0:
        _server_reload(attacker_id)
    return true

func _build_shock_target_tree(attacker_id: int) -> Dictionary:
    var result: Dictionary = {
        "edges": PackedVector3Array(),
        "targets": [],
    }
    if not players.has(attacker_id):
        return result

    var shooter: ViceQuestPlayer = players[attacker_id]
    var root_pos: Vector3 = shooter.position + Vector3(0.0, 0.62, 0.0) + shooter.facing * 0.46
    var candidates: Array[Dictionary] = _shock_collect_targets(attacker_id)
    var connected: Array[Dictionary] = [{
        "kind": "root",
        "id": -1,
        "pos": root_pos,
    }]
    var used: Dictionary = {}
    var edges: PackedVector3Array = PackedVector3Array()
    var selected_targets: Array[Dictionary] = []

    # Keep last tick's targets if they are still barely in range and visible.
    # That stops the tree from flickering between two equally close peds.
    var previous: Array = shock_channel_locked.get(attacker_id, [])
    for raw_prev: Variant in previous:
        if selected_targets.size() >= SHOCK_CHANNEL_MAX_TARGETS:
            break
        var prev: Dictionary = raw_prev
        var prev_key: String = _shock_target_key(prev)
        var match_index: int = -1
        for candidate_index in range(candidates.size()):
            if used.has(candidate_index):
                continue
            if _shock_target_key(candidates[candidate_index]) == prev_key:
                match_index = candidate_index
                break
        if match_index < 0:
            continue
        var kept: Dictionary = candidates[match_index]
        var best_parent: int = -1
        var best_distance: float = 1000000.0
        for parent_index in range(connected.size()):
            var parent: Dictionary = connected[parent_index]
            if not _shock_link_allowed(parent, kept, SHOCK_CHANNEL_HYSTERESIS):
                continue
            var distance: float = Vector3(parent["pos"]).distance_to(Vector3(kept["pos"]))
            if distance < best_distance:
                best_distance = distance
                best_parent = parent_index
        if best_parent < 0:
            continue
        var locked_parent: Dictionary = connected[best_parent]
        edges.append(locked_parent["pos"])
        edges.append(kept["pos"])
        selected_targets.append(kept)
        connected.append(kept)
        used[match_index] = true

    while selected_targets.size() < SHOCK_CHANNEL_MAX_TARGETS:
        var best_candidate: int = -1
        var best_parent: int = -1
        var best_distance: float = 1000000.0

        for candidate_index in range(candidates.size()):
            if used.has(candidate_index):
                continue
            var candidate: Dictionary = candidates[candidate_index]
            for parent_index in range(connected.size()):
                var parent: Dictionary = connected[parent_index]
                if not _shock_link_allowed(parent, candidate, 1.0):
                    continue
                var distance: float = Vector3(parent["pos"]).distance_to(Vector3(candidate["pos"]))
                if distance < best_distance:
                    best_distance = distance
                    best_candidate = candidate_index
                    best_parent = parent_index

        if best_candidate < 0 or best_parent < 0:
            break

        var chosen: Dictionary = candidates[best_candidate]
        var chosen_parent: Dictionary = connected[best_parent]
        edges.append(chosen_parent["pos"])
        edges.append(chosen["pos"])
        selected_targets.append(chosen)
        connected.append(chosen)
        used[best_candidate] = true

    var lock_list: Array = []
    for raw_target: Variant in selected_targets:
        var selected: Dictionary = raw_target
        lock_list.append({
            "kind": String(selected["kind"]),
            "id": int(selected["id"]),
        })
    shock_channel_locked[attacker_id] = lock_list
    result["edges"] = edges
    result["targets"] = selected_targets
    return result
'''

main = must_replace(main, old_tree, new_tree, "target tree")

# 5) Drain ammo on damage ticks and keep a single looped shocker sample.
main = must_replace(
    main,
    """        if needs_visual:
            shock_channel_visual_clock[player_id] = 0.0
            _sync_shock_channel_visual.rpc(player_id, edges)
        else:
            shock_channel_visual_clock[player_id] = visual_clock

        if needs_damage:
            shock_channel_damage_clock[player_id] = 0.0
            _apply_shock_channel_tick(player_id, targets)
        else:
            shock_channel_damage_clock[player_id] = damage_clock
""",
    """        if needs_visual:
            shock_channel_visual_clock[player_id] = 0.0
            _sync_shock_channel_visual.rpc(player_id, edges)
            if players.has(player_id):
                _sync_shock_loop.rpc(player_id, true, players[player_id].position)
        else:
            shock_channel_visual_clock[player_id] = visual_clock

        if needs_damage:
            if not _shock_consume_channel_ammo(player_id):
                _set_shock_channel_state(player_id, false)
                continue
            shock_channel_damage_clock[player_id] = 0.0
            _apply_shock_channel_tick(player_id, targets)
        else:
            shock_channel_damage_clock[player_id] = damage_clock
""",
    "channel tick ammo/audio",
)

# 6) Looped audio RPC lives next to the visual sync.
main = must_replace(
    main,
    '''@rpc("authority", "call_local", "unreliable")
func _sync_shock_channel_visual(shooter_id: int, edges: PackedVector3Array) -> void:
''',
    '''@rpc("authority", "call_local", "unreliable")
func _sync_shock_loop(shooter_id: int, active: bool, world_position: Vector3) -> void:
    if audio_manager == null:
        return
    var source: Vector3 = world_position
    if players.has(shooter_id):
        source = players[shooter_id].position + Vector3(0.0, 0.62, 0.0)
    audio_manager.set_shock_channel(active, source)

@rpc("authority", "call_local", "unreliable")
func _sync_shock_channel_visual(shooter_id: int, edges: PackedVector3Array) -> void:
''',
    "shock loop rpc",
)

# 7) Held channel owns firing. Stop the older automatic submit_fire path
#    from consuming ammo and running a second shock graph.
main = must_replace(
    main,
    """    if player_vehicle.has(id):
        _server_fire_vehicle_weapon(id)
        return
    var cooldown: float = shot_cooldowns[id] if shot_cooldowns.has(id) else 0.0
""",
    """    if player_vehicle.has(id):
        _server_fire_vehicle_weapon(id)
        return
    if int(player_current_weapon.get(id, WEAPON_DATA.PISTOL)) == WEAPON_DATA.STUN_GUN:
        return
    var cooldown: float = shot_cooldowns[id] if shot_cooldowns.has(id) else 0.0
""",
    "skip duplicate stun fire",
)

main = must_replace(
    main,
    """func is_weapon_automatic_for(id: int) -> bool:
    var weapon_id: int = int(player_current_weapon.get(id, WEAPON_DATA.PISTOL))
    if weapon_id == WEAPON_DATA.STUN_GUN:
        return true
    return bool(_weapon_definition_for_player(id)["automatic"])
""",
    """func is_weapon_automatic_for(id: int) -> bool:
    var weapon_id: int = int(player_current_weapon.get(id, WEAPON_DATA.PISTOL))
    if weapon_id == WEAPON_DATA.STUN_GUN:
        return false
    return bool(_weapon_definition_for_player(id)["automatic"])
""",
    "stun not automatic submit_fire",
)

main_path.write_text(main, encoding="utf-8")

# 8) One looped shocker voice instead of one-shot spam.
audio = must_replace(
    audio,
    """var engine_player: AudioStreamPlayer3D
var wasted_player: AudioStreamPlayer
""",
    """var engine_player: AudioStreamPlayer3D
var wasted_player: AudioStreamPlayer
var shock_player: AudioStreamPlayer3D
var shock_loop_active: bool = false
""",
    "audio vars",
)

audio = must_replace(
    audio,
    """    wasted_player.volume_db = -3.0
    if ResourceLoader.exists(WASTED_PATH):
        wasted_player.stream = load(WASTED_PATH)
    add_child(wasted_player)
""",
    """    wasted_player.volume_db = -3.0
    if ResourceLoader.exists(WASTED_PATH):
        wasted_player.stream = load(WASTED_PATH)
    add_child(wasted_player)

    shock_player = AudioStreamPlayer3D.new()
    shock_player.name = "ShockChannel"
    shock_player.max_distance = 22.0
    shock_player.unit_size = 5.0
    shock_player.attenuation_filter_cutoff_hz = 11500.0
    shock_player.volume_db = -6.5
    add_child(shock_player)
""",
    "audio configure",
)

audio = must_replace(
    audio,
    """func stop_engine() -> void:
    _engine_key = ""
    if engine_player != null and engine_player.playing:
        engine_player.stop()
""",
    """func stop_engine() -> void:
    _engine_key = ""
    if engine_player != null and engine_player.playing:
        engine_player.stop()

func set_shock_channel(active: bool, world_position: Vector3) -> void:
    if shock_player == null:
        return
    if not active:
        shock_loop_active = false
        if shock_player.playing:
            shock_player.stop()
        return
    shock_player.global_position = world_position
    if shock_player.stream == null:
        shock_player.stream = _looped_stream("shocker")
    if not shock_loop_active or not shock_player.playing:
        shock_loop_active = true
        if shock_player.stream != null:
            shock_player.play()
""",
    "audio shock loop",
)

audio_path.write_text(audio, encoding="utf-8")
print("Applied Shock Gun LOS, hysteresis, Quest trigger, looped audio and channel ammo drain.")
