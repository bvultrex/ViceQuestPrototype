from pathlib import Path
import re, sys

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
main = main_path.read_text(encoding="utf-8")

# Extra runtime state.
anchor = "var shock_arc_core_material_cache: StandardMaterial3D"
if anchor not in main:
    raise SystemExit("Missing sustained shock anchor: material cache")
main = main.replace(anchor, anchor + r'''
var shock_channel_active: Dictionary = {}
var shock_channel_visual_clock: Dictionary = {}
var shock_channel_damage_clock: Dictionary = {}
var local_shock_channel_sent: bool = false
const SHOCK_CHANNEL_PRIMARY_RANGE: float = 11.5
const SHOCK_CHANNEL_CHAIN_RANGE: float = 5.8
const SHOCK_CHANNEL_MAX_TARGETS: int = 6
const SHOCK_CHANNEL_VISUAL_INTERVAL: float = 0.075
const SHOCK_CHANNEL_DAMAGE_INTERVAL: float = 0.28
''', 1)

# The old one-shot shock ray must no longer apply damage.
stun = re.search(r'func _weapon_stun_hit\(.*?\n(?=func _melee_candidate_score)', main, re.S)
if not stun:
    raise SystemExit("Missing sustained shock anchor: _weapon_stun_hit")
main = main[:stun.start()] + r'''func _weapon_stun_hit(shooter: ViceQuestPlayer, attacker_id: int, start: Vector3, direction: Vector3, weapon_range: float, damage: int) -> Vector3:
    # Shock Gun damage is handled by the sustained tracking/channel framework.
    return start + direction * weapon_range

''' + main[stun.end():]

# The legacy shot effect may still be called on initial trigger press. Keep its
# audio/fire-pose, but do not spawn a competing single bolt.
old = '''    if shot_weapon == WEAPON_DATA.STUN_GUN:
        _spawn_shock_arc(start, end)
        return'''
new = '''    if shot_weapon == WEAPON_DATA.STUN_GUN:
        return'''
if old not in main:
    raise SystemExit("Missing sustained shock anchor: legacy shock visual")
main = main.replace(old, new, 1)

# Insert the channel framework before the projectile-visual RPC section.
marker = '@rpc("authority", "call_local", "reliable")\nfunc _spawn_projectile_visual'
if marker not in main:
    raise SystemExit("Missing sustained shock anchor: projectile visual marker")

channel_code = r'''
func _shock_channel_should_be_active(player_id: int) -> bool:
    if not game_started or not players.has(player_id):
        return false
    if not bool(alive_states.get(player_id, false)):
        return false
    if player_vehicle.has(player_id):
        return false
    return int(player_current_weapon.get(player_id, WEAPON_DATA.PISTOL)) == WEAPON_DATA.STUN_GUN

func _update_local_shock_channel_input() -> void:
    var local_id: int = multiplayer.get_unique_id()
    var wants_channel: bool = _shock_channel_should_be_active(local_id) and Input.is_action_pressed("attack")
    if wants_channel == local_shock_channel_sent:
        return
    local_shock_channel_sent = wants_channel
    if multiplayer.is_server():
        _set_shock_channel_state(local_id, wants_channel)
    else:
        _request_shock_channel.rpc_id(1, wants_channel)

@rpc("any_peer", "reliable")
func _request_shock_channel(active: bool) -> void:
    if not multiplayer.is_server():
        return
    var sender_id: int = multiplayer.get_remote_sender_id()
    if sender_id <= 0:
        return
    _set_shock_channel_state(sender_id, active)

func _set_shock_channel_state(player_id: int, active: bool) -> void:
    if not multiplayer.is_server():
        return
    var valid_active: bool = active and _shock_channel_should_be_active(player_id)
    if valid_active:
        shock_channel_active[player_id] = true
        shock_channel_visual_clock[player_id] = SHOCK_CHANNEL_VISUAL_INTERVAL
        shock_channel_damage_clock[player_id] = SHOCK_CHANNEL_DAMAGE_INTERVAL
    else:
        shock_channel_active.erase(player_id)
        shock_channel_visual_clock.erase(player_id)
        shock_channel_damage_clock.erase(player_id)
        _sync_shock_channel_visual.rpc(player_id, PackedVector3Array())

func _shock_target_position(kind: String, entity_id: int) -> Vector3:
    match kind:
        "player":
            if players.has(entity_id):
                return players[entity_id].position + Vector3(0.0, 0.58, 0.0)
        "cop":
            if cops.has(entity_id):
                return cops[entity_id].position + Vector3(0.0, 0.58, 0.0)
        "civilian":
            if civilians.has(entity_id):
                return civilians[entity_id].position + Vector3(0.0, 0.58, 0.0)
    return Vector3.ZERO

func _shock_collect_targets(attacker_id: int) -> Array[Dictionary]:
    var result: Array[Dictionary] = []
    for raw_id: Variant in players.keys():
        var target_id: int = int(raw_id)
        if target_id == attacker_id or not bool(alive_states.get(target_id, false)):
            continue
        if player_vehicle.has(target_id):
            continue
        result.append({
            "kind": "player",
            "id": target_id,
            "pos": _shock_target_position("player", target_id),
        })

    for raw_id: Variant in cops.keys():
        var cop_id: int = int(raw_id)
        var cop: ViceQuestCop = cops[cop_id]
        if cop == null or not cop.is_alive or not cop.response_active:
            continue
        result.append({
            "kind": "cop",
            "id": cop_id,
            "pos": _shock_target_position("cop", cop_id),
        })

    for raw_id: Variant in civilians.keys():
        var civilian_id: int = int(raw_id)
        var civilian: ViceQuestCivilian = civilians[civilian_id]
        if civilian == null or not civilian.is_alive or civilian.in_vehicle:
            continue
        result.append({
            "kind": "civilian",
            "id": civilian_id,
            "pos": _shock_target_position("civilian", civilian_id),
        })
    return result

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

func _apply_shock_channel_tick(attacker_id: int, targets: Array) -> void:
    for raw_target: Variant in targets:
        var target: Dictionary = raw_target
        var kind: String = String(target["kind"])
        var entity_id: int = int(target["id"])
        match kind:
            "player":
                if entity_id == attacker_id or not bool(alive_states.get(entity_id, false)):
                    continue
                player_stun_timers[entity_id] = maxf(float(player_stun_timers.get(entity_id, 0.0)), 0.42)
                _damage_player(entity_id, 3, attacker_id)
                if bool(alive_states.get(entity_id, false)):
                    _play_electrocute_reaction.rpc("player", entity_id, 0.48)
            "cop":
                if not cops.has(entity_id) or not cops[entity_id].is_alive:
                    continue
                _damage_cop(entity_id, 3, attacker_id)
                if cops.has(entity_id) and cops[entity_id].is_alive:
                    cops[entity_id].apply_electrocute(0.52)
                    _play_electrocute_reaction.rpc("cop", entity_id, 0.52)
            "civilian":
                if not civilians.has(entity_id) or not civilians[entity_id].is_alive:
                    continue
                _damage_civilian(entity_id, 3, attacker_id)
                if civilians.has(entity_id) and civilians[entity_id].is_alive:
                    civilians[entity_id].apply_electrocute(0.56)
                    _play_electrocute_reaction.rpc("civilian", entity_id, 0.56)

func _server_update_shock_channels(delta: float) -> void:
    if not multiplayer.is_server():
        return

    var active_ids: Array = shock_channel_active.keys()
    for raw_id: Variant in active_ids:
        var player_id: int = int(raw_id)
        if not bool(shock_channel_active.get(player_id, false)) or not _shock_channel_should_be_active(player_id):
            _set_shock_channel_state(player_id, false)
            continue

        var visual_clock: float = float(shock_channel_visual_clock.get(player_id, 0.0)) + delta
        var damage_clock: float = float(shock_channel_damage_clock.get(player_id, 0.0)) + delta
        var needs_visual: bool = visual_clock >= SHOCK_CHANNEL_VISUAL_INTERVAL
        var needs_damage: bool = damage_clock >= SHOCK_CHANNEL_DAMAGE_INTERVAL
        if not needs_visual and not needs_damage:
            shock_channel_visual_clock[player_id] = visual_clock
            shock_channel_damage_clock[player_id] = damage_clock
            continue

        var network: Dictionary = _build_shock_target_tree(player_id)
        var edges: PackedVector3Array = network["edges"]
        var targets: Array = network["targets"]

        if needs_visual:
            shock_channel_visual_clock[player_id] = 0.0
            _sync_shock_channel_visual.rpc(player_id, edges)
        else:
            shock_channel_visual_clock[player_id] = visual_clock

        if needs_damage:
            shock_channel_damage_clock[player_id] = 0.0
            _apply_shock_channel_tick(player_id, targets)
        else:
            shock_channel_damage_clock[player_id] = damage_clock

@rpc("authority", "call_local", "unreliable")
func _sync_shock_channel_visual(shooter_id: int, edges: PackedVector3Array) -> void:
    if edges.is_empty():
        return
    if players.has(shooter_id):
        players[shooter_id].show_fire_pose(WEAPON_DATA.STUN_GUN)
    var edge_index: int = 0
    while edge_index + 1 < edges.size():
        _spawn_shock_arc(edges[edge_index], edges[edge_index + 1])
        edge_index += 2

'''
main = main.replace(marker, channel_code + marker, 1)

# Drive the channel from the same global process that already runs on every peer.
process_anchor = "func _process(delta: float) -> void:\n"
if process_anchor not in main:
    raise SystemExit("Missing sustained shock anchor: main process")
main = main.replace(
    process_anchor,
    process_anchor + "    _update_local_shock_channel_input()\n    if multiplayer.is_server():\n        _server_update_shock_channels(delta)\n",
    1,
)

main_path.write_text(main, encoding="utf-8")
print("Applied sustained target-tracking branching Shock Gun channel framework.")
