#!/usr/bin/env python3
"""ViceQuest v0.6.18.27 gameplay fixes on the v0.6.18.26 engine baseline.

The working 18.26 Quest heard-audio/city-voice engine pipeline remains untouched.

Fixes:
- logical Cop NPC drivers for law response vehicles, including visible ejection
  on theft and no autonomous resume after the player leaves the stolen car
- preserve response-Cop/Agent damage instead of refreshing HP every response tick
- low-restitution vehicle contacts to remove pinball/gummy-ball rebounds
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
vehicle_path = root / "scripts" / "vehicle.gd"
cop_path = root / "scripts" / "cop.gd"

def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    hits = text.count(old)
    if hits < count:
        raise SystemExit(f"Missing v0.6.18.27 anchor {label}: found {hits}, need {count}")
    return text.replace(old, new, count)

def func_span(text: str, name: str) -> tuple[int, int]:
    match = re.search(rf"(?m)^func {re.escape(name)}\s*\(", text)
    if match is None:
        raise SystemExit(f"Missing function {name}")
    start = match.start()
    next_match = re.search(r"(?m)^func [A-Za-z0-9_]+\s*\(", text[match.end():])
    end = len(text) if next_match is None else match.end() + next_match.start()
    return start, end

def get_func(text: str, name: str) -> str:
    start, end = func_span(text, name)
    return text[start:end].rstrip()

def replace_func(text: str, name: str, replacement: str) -> str:
    start, end = func_span(text, name)
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]

main = main_path.read_text(encoding="utf-8")
vehicle = vehicle_path.read_text(encoding="utf-8")
cop = cop_path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1) Law NPC health: set_enforcement_profile used to refill HP.  The reliable
# call-local sync happened every response tick, making high-level Agents appear
# invulnerable.  Preserve damage unless an untouched/full-health unit changes
# to a profile with a different maximum.
# ---------------------------------------------------------------------------
cop = must_replace(
    cop,
    'func set_enforcement_profile(role: String) -> void:\n    enforcement_role = role\n',
    'func set_enforcement_profile(role: String) -> void:\n    var previous_profile_hp: int = profile_hp\n    enforcement_role = role\n',
    "profile previous HP",
)
cop = must_replace(
    cop,
    '''    if is_alive:
        hp = profile_hp
    if _visual != null:
''',
    '''    if is_alive:
        if hp >= previous_profile_hp:
            hp = profile_hp
        else:
            hp = mini(hp, profile_hp)
    if _visual != null:
''',
    "profile HP preservation",
)

sync_profile = '''func _sync_cop_profile(cop_id: int, role: String, active: bool) -> void:
    if not cops.has(cop_id):
        return
    var synced_cop: ViceQuestCop = cops[cop_id]
    # Do not replay the profile setter every network tick.  Besides doing
    # needless visual work it used to refill HP and made Agents effectively
    # immortal.
    if synced_cop.enforcement_role != role:
        synced_cop.set_enforcement_profile(role)
    synced_cop.set_response_active(active)
'''
main = replace_func(main, "_sync_cop_profile", sync_profile)

# ---------------------------------------------------------------------------
# 2) Police cars get a real logical Cop NPC occupant.  player driver_id stays
# reserved for network players; the NPC occupant is tracked separately so the
# existing authoritative vehicle controller can remain unchanged.
# ---------------------------------------------------------------------------
main = must_replace(
    main,
    '''var police_response_cop_ids: Array[int] = []
var police_pursuit_vehicle_ids: Array[int] = []
var police_response_accumulator: float = 0.0
''',
    '''var police_response_cop_ids: Array[int] = []
var police_pursuit_vehicle_ids: Array[int] = []
var police_driver_by_vehicle: Dictionary[int, int] = {}
var police_vehicle_by_driver: Dictionary[int, int] = {}
var police_ejected_driver_until_ms: Dictionary[int, int] = {}
var police_response_accumulator: float = 0.0
''',
    "law driver dictionaries",
)

driver_helpers = r'''func _law_driver_role_for_variant(variant_id: String) -> String:
    match variant_id:
        "swat_van":
            return "swat"
        "agent_car":
            return "agent_smg"
        "armed_land_roamer", "land_roamer", "pacifier", "tank":
            return "soldier"
        _:
            return "police"

func _law_driver_for_slot(slot: int) -> int:
    # Response foot units occupy the head of the reserve array.  Vehicle crews
    # come from the tail so the two duties cannot silently fight over one Cop.
    if police_response_cop_ids.is_empty():
        return 0
    var driver_pool: int = mini(POLICE_PURSUIT_CAR_COUNT, police_response_cop_ids.size())
    for offset in range(driver_pool):
        var tail_offset: int = posmod(slot + offset, driver_pool)
        var array_index: int = police_response_cop_ids.size() - 1 - tail_offset
        if array_index < 0:
            continue
        var candidate_id: int = police_response_cop_ids[array_index]
        if not cops.has(candidate_id):
            continue
        var candidate: ViceQuestCop = cops[candidate_id]
        if not candidate.is_alive:
            continue
        if police_ejected_driver_until_ms.has(candidate_id):
            continue
        if police_vehicle_by_driver.has(candidate_id):
            continue
        return candidate_id
    return 0

func _detach_police_driver(vehicle_id: int, activate_on_foot: bool = false, world_position: Vector3 = Vector3.ZERO, threat_position: Vector3 = Vector3.ZERO) -> int:
    var cop_id: int = int(police_driver_by_vehicle.get(vehicle_id, 0))
    if cop_id == 0 and vehicles.has(vehicle_id):
        var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
        cop_id = int(vehicle.get_meta("npc_driver_cop_id", 0))
    if cop_id == 0:
        return 0
    police_driver_by_vehicle.erase(vehicle_id)
    police_vehicle_by_driver.erase(cop_id)
    if vehicles.has(vehicle_id):
        var detached_vehicle: ViceQuestVehicle = vehicles[vehicle_id]
        if detached_vehicle.has_meta("npc_driver_cop_id"):
            detached_vehicle.remove_meta("npc_driver_cop_id")
    if not cops.has(cop_id):
        return cop_id
    var cop: ViceQuestCop = cops[cop_id]
    if activate_on_foot and cop.is_alive:
        cop.position = world_position
        cop.target_position = world_position
        var face: Vector3 = threat_position - world_position
        face.y = 0.0
        if face.length_squared() > 0.04:
            cop.facing = face.normalized()
            cop.rotation.y = -atan2(cop.facing.x, -cop.facing.z)
        cop.set_response_active(true)
        police_ejected_driver_until_ms[cop_id] = Time.get_ticks_msec() + 9000
        _sync_cop_profile.rpc(cop_id, cop.enforcement_role, true)
        _sync_cop_state.rpc(cop_id, cop.position, cop.facing, true, cop.hp)
    else:
        police_ejected_driver_until_ms.erase(cop_id)
        cop.set_response_active(false)
        _sync_cop_profile.rpc(cop_id, cop.enforcement_role, false)
    return cop_id

func _assign_police_driver(vehicle_id: int, driver_slot: int, desired_role: String) -> int:
    if not vehicles.has(vehicle_id):
        return 0
    if police_driver_by_vehicle.has(vehicle_id):
        var existing_id: int = int(police_driver_by_vehicle[vehicle_id])
        if cops.has(existing_id) and cops[existing_id].is_alive:
            var existing: ViceQuestCop = cops[existing_id]
            if existing.enforcement_role != desired_role:
                existing.set_enforcement_profile(desired_role)
            existing.set_response_active(false)
            existing.position = vehicles[vehicle_id].position
            existing.target_position = existing.position
            vehicles[vehicle_id].set_meta("npc_driver_cop_id", existing_id)
            _sync_cop_profile.rpc(existing_id, desired_role, false)
            return existing_id
        _detach_police_driver(vehicle_id, false)

    var cop_id: int = _law_driver_for_slot(driver_slot)
    if cop_id == 0:
        return 0
    var cop: ViceQuestCop = cops[cop_id]
    if cop.enforcement_role != desired_role:
        cop.set_enforcement_profile(desired_role)
    cop.set_response_active(false)
    cop.position = vehicles[vehicle_id].position
    cop.target_position = cop.position
    police_driver_by_vehicle[vehicle_id] = cop_id
    police_vehicle_by_driver[cop_id] = vehicle_id
    vehicles[vehicle_id].set_meta("npc_driver_cop_id", cop_id)
    _sync_cop_profile.rpc(cop_id, desired_role, false)
    return cop_id

func _eject_police_driver(vehicle_id: int, thief_id: int) -> bool:
    if not vehicles.has(vehicle_id):
        return false
    var cop_id: int = int(police_driver_by_vehicle.get(vehicle_id, vehicles[vehicle_id].get_meta("npc_driver_cop_id", 0)))
    if cop_id == 0:
        return false
    var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
    var side: Vector3 = vehicle.get_side_vector()
    var eject_position: Vector3 = vehicle.position + side * 1.50
    eject_position.y = sample_surface_height(eject_position, vehicle.position.y - 0.10) + PLAYER_Y
    var threat: Vector3 = players[thief_id].position if players.has(thief_id) else vehicle.position
    vehicle.clear_pursuit()
    vehicle.ai_controlled = false
    vehicle.set_meta("response_hijacked", true)
    vehicle.set_meta("response_hijacked_at_ms", Time.get_ticks_msec())
    _detach_police_driver(vehicle_id, true, eject_position, threat)
    return true

'''

old_pursuit = get_func(main, "_server_update_pursuit_forces")
gang_marker = "    # Gang cars reuse the same lightweight pursuit steering."
if gang_marker not in old_pursuit:
    raise SystemExit("Missing gang pursuit tail")
gang_tail = old_pursuit[old_pursuit.index(gang_marker):]

new_law_pursuit = r'''func _server_update_pursuit_forces(delta: float) -> void:
    police_response_accumulator += delta
    if police_response_accumulator < POLICE_RESPONSE_INTERVAL:
        return
    police_response_accumulator = 0.0

    var now_ms: int = Time.get_ticks_msec()
    var expired_ejected: Array[int] = []
    for raw_cop_id in police_ejected_driver_until_ms.keys():
        var ejected_id: int = int(raw_cop_id)
        if int(police_ejected_driver_until_ms[ejected_id]) <= now_ms:
            expired_ejected.append(ejected_id)
    for ejected_id in expired_ejected:
        police_ejected_driver_until_ms.erase(ejected_id)

    var wanted_target_id: int = 0
    var highest_wanted: int = 0
    for raw_player_id in players.keys():
        var player_id: int = int(raw_player_id)
        var level: int = int(wanted_levels.get(player_id, 0))
        if alive_states.get(player_id, false) and level > highest_wanted:
            highest_wanted = level
            wanted_target_id = player_id

    if wanted_target_id == 0:
        police_ejected_driver_until_ms.clear()
        for reserve_id: int in police_response_cop_ids:
            if not cops.has(reserve_id):
                continue
            var idle_cop: ViceQuestCop = cops[reserve_id]
            if idle_cop.response_active:
                idle_cop.set_response_active(false)
                _sync_cop_profile.rpc(reserve_id, idle_cop.enforcement_role, false)
        for police_vehicle_id: int in police_pursuit_vehicle_ids:
            if not vehicles.has(police_vehicle_id):
                continue
            var idle_vehicle: ViceQuestVehicle = vehicles[police_vehicle_id]
            idle_vehicle.clear_pursuit()
            if bool(idle_vehicle.get_meta("response_hijacked", false)) or idle_vehicle.driver_id != 0:
                # A stolen response car is now an ordinary player-owned world
                # vehicle.  Never let the response controller steal it back.
                idle_vehicle.ai_controlled = false
                continue
            _detach_police_driver(police_vehicle_id, false)
            idle_vehicle.set_stream_active(false)
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
        # A Cop hidden in a response vehicle is not simultaneously an on-foot
        # pursuer.  Recently ejected drivers remain on foot for a short window.
        if police_vehicle_by_driver.has(reserve_id):
            continue
        if police_ejected_driver_until_ms.has(reserve_id):
            var ejected_cop: ViceQuestCop = cops[reserve_id]
            if ejected_cop.is_alive and not ejected_cop.response_active:
                ejected_cop.set_response_active(true)
                _sync_cop_profile.rpc(reserve_id, ejected_cop.enforcement_role, true)
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
    var active_driver_slot: int = 0
    for raw_police_vehicle_id in police_pursuit_vehicle_ids:
        var police_vehicle_id: int = int(raw_police_vehicle_id)
        if not vehicles.has(police_vehicle_id):
            continue
        var police_vehicle: ViceQuestVehicle = vehicles[police_vehicle_id]

        if bool(police_vehicle.get_meta("response_hijacked", false)) or police_vehicle.driver_id != 0:
            police_vehicle.clear_pursuit()
            police_vehicle.ai_controlled = false
            if police_driver_by_vehicle.has(police_vehicle_id):
                _detach_police_driver(police_vehicle_id, false)
            continue

        if active_driver_slot >= desired_variants.size():
            _detach_police_driver(police_vehicle_id, false)
            police_vehicle.clear_pursuit()
            police_vehicle.set_stream_active(false)
            vehicle_stream_states[police_vehicle_id] = false
            _sync_vehicle_stream_state.rpc(police_vehicle_id, false)
            continue

        var desired_variant: String = desired_variants[active_driver_slot]
        if not police_vehicle.stream_active or police_vehicle.variant_id != desired_variant or _planar_distance(police_vehicle.position, target) > 165.0:
            _detach_police_driver(police_vehicle_id, false)
            var vehicle_spawn: Vector3 = _response_spawn_point(target, true, police_vehicle_id + highest_wanted * 43)
            var direction: Vector3 = target - vehicle_spawn
            direction.y = 0.0
            var heading: float = atan2(direction.z, direction.x)
            var response_route: Array[Vector3] = [vehicle_spawn, target]
            police_vehicle.recycle_ambient(vehicle_spawn, heading, response_route, police_vehicle.max_forward_speed * 0.94, desired_variant)
            police_vehicle.ai_cruise_speed = police_vehicle.max_forward_speed * 0.94
            police_vehicle.set_meta("response_role", "law")
            police_vehicle.set_meta("response_hijacked", false)
            if police_vehicle.has_meta("response_hijacked_at_ms"):
                police_vehicle.remove_meta("response_hijacked_at_ms")
            vehicle_stream_states[police_vehicle_id] = true
            _sync_ambient_vehicle_activation.rpc(police_vehicle_id, police_vehicle.position, police_vehicle.heading, police_vehicle.current_speed, desired_variant, 0)

        var driver_role: String = _law_driver_role_for_variant(desired_variant)
        var assigned_driver: int = _assign_police_driver(police_vehicle_id, active_driver_slot, driver_role)
        if assigned_driver == 0:
            police_vehicle.clear_pursuit()
            police_vehicle.current_speed = move_toward(police_vehicle.current_speed, 0.0, police_vehicle.brake_deceleration * POLICE_RESPONSE_INTERVAL)
            active_driver_slot += 1
            continue
        police_vehicle.set_pursuit_target(target, "police")
        active_driver_slot += 1
'''
main = replace_func(main, "_server_update_pursuit_forces", driver_helpers + new_law_pursuit + gang_tail)

server_enter = r'''func _server_enter_vehicle(player_id: int, vehicle_id: int) -> void:
    if not players.has(player_id) or not vehicles.has(vehicle_id):
        return
    var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
    if vehicle.driver_id != 0 or vehicle.is_destroyed:
        return

    var had_police_driver: bool = police_driver_by_vehicle.has(vehicle_id) or int(vehicle.get_meta("npc_driver_cop_id", 0)) != 0
    var was_theft: bool = vehicle.claim_by_player()
    if had_police_driver:
        _eject_police_driver(vehicle_id, player_id)
        _add_wanted(player_id, 1, "POLICE VEHICLE THEFT")
    elif was_theft:
        _eject_traffic_driver(vehicle_id)
        _add_wanted(player_id, 1, "VEHICLE THEFT")

    player_vehicle[player_id] = vehicle_id
    player_tuning_last_position[player_id] = vehicle.position
    vehicle.set_driver(player_id)
    inputs[player_id] = Vector2.ZERO
    var player: ViceQuestPlayer = players[player_id]
    player.snap_to_position(Vector3(vehicle.position.x, vehicle.position.y + 0.02, vehicle.position.z))
    player.facing = vehicle.get_forward_vector()
    player.set_vehicle_state(vehicle_id)
    _sync_vehicle_driver.rpc(vehicle_id, player_id)
    _play_vehicle_door.rpc(vehicle.position, _vehicle_uses_heavy_door_sound(vehicle), false)
    if had_police_driver:
        _show_combat_message.rpc("%s hijacked a police %s" % [_display_name(player_id), vehicle.display_name])
    elif was_theft:
        _show_combat_message.rpc("%s stole a civilian %s" % [_display_name(player_id), vehicle.display_name])
    else:
        _show_combat_message.rpc("%s entered a %s" % [_display_name(player_id), vehicle.display_name])
'''
main = replace_func(main, "_server_enter_vehicle", server_enter)

old_exit = get_func(main, "_server_exit_vehicle")
old_exit = must_replace(
    old_exit,
    '''    vehicle.set_driver(0)
    tank_turret_inputs.erase(player_id)
    vehicle.current_speed *= 0.72
''',
    '''    vehicle.set_driver(0)
    if bool(vehicle.get_meta("response_hijacked", false)):
        vehicle.clear_pursuit()
        vehicle.ai_controlled = false
    tank_turret_inputs.erase(player_id)
    vehicle.current_speed *= 0.72
''',
    "stolen law car exit",
)
main = replace_func(main, "_server_exit_vehicle", old_exit)

old_release = get_func(main, "_server_release_vehicle")
old_release = must_replace(
    old_release,
    '''    if vehicles.has(vehicle_id):
        vehicles[vehicle_id].set_driver(0)
        _sync_vehicle_driver.rpc(vehicle_id, 0)
''',
    '''    if vehicles.has(vehicle_id):
        vehicles[vehicle_id].set_driver(0)
        if bool(vehicles[vehicle_id].get_meta("response_hijacked", false)):
            vehicles[vehicle_id].clear_pursuit()
            vehicles[vehicle_id].ai_controlled = false
        _sync_vehicle_driver.rpc(vehicle_id, 0)
''',
    "stolen law car release",
)
main = replace_func(main, "_server_release_vehicle", old_release)

old_destroy = get_func(main, "_destroy_vehicle")
old_destroy = must_replace(
    old_destroy,
    '''    var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
    if vehicle.is_destroyed:
''',
    '''    var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
    if police_driver_by_vehicle.has(vehicle_id):
        _detach_police_driver(vehicle_id, false)
    if vehicle.is_destroyed:
''',
    "destroy law driver detach",
)
main = replace_func(main, "_destroy_vehicle", old_destroy)

old_respawn = get_func(main, "_respawn_vehicle_server")
old_respawn = must_replace(
    old_respawn,
    '''    var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
    vehicle.reset_to_spawn()
    _sync_tank_crush.rpc(vehicle_id, false)
''',
    '''    var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
    vehicle.reset_to_spawn()
    if police_pursuit_vehicle_ids.has(vehicle_id):
        _detach_police_driver(vehicle_id, false)
        vehicle.set_meta("response_role", "law")
        vehicle.set_meta("response_hijacked", false)
        if vehicle.has_meta("response_hijacked_at_ms"):
            vehicle.remove_meta("response_hijacked_at_ms")
        vehicle.ai_controlled = false
        vehicle.set_stream_active(false)
        vehicle_stream_states[vehicle_id] = false
    _sync_tank_crush.rpc(vehicle_id, false)
''',
    "law pool respawn reset",
)
main = replace_func(main, "_respawn_vehicle_server", old_respawn)

# ---------------------------------------------------------------------------
# 3) Anti-gummyball contacts.  CharacterBody contacts should lose energy and
# separate gently, not flip longitudinal speed and inject huge opposite impulses.
# ---------------------------------------------------------------------------
vehicle = vehicle.replace(
    "        current_speed *= -0.18\n        _resolve_vehicle_collisions(impact_speed)",
    "        current_speed *= 0.16\n        _resolve_vehicle_collisions(impact_speed)",
    1,
)

anti_bounce = r'''func _resolve_vehicle_collisions(impact_speed: float) -> void:
    for collision_index in range(get_slide_collision_count()):
        var collision: KinematicCollision3D = get_slide_collision(collision_index)
        var collider: Object = collision.get_collider()
        if not collider is ViceQuestVehicle:
            continue
        var other: ViceQuestVehicle = collider as ViceQuestVehicle
        if other == self or other.is_destroyed:
            continue
        if variant_id == "tank" and other.variant_id != "tank" and multiplayer.is_server():
            var main_node: Node = get_parent()
            if main_node != null and main_node.has_method("_server_tank_crush_vehicle"):
                main_node.call("_server_tank_crush_vehicle", vehicle_id, other.vehicle_id, driver_id)
            var travel_sign: float = 1.0 if current_speed >= 0.0 else -1.0
            current_speed = travel_sign * maxf(absf(current_speed), impact_speed * 0.82)
            position += get_forward_vector() * travel_sign * clampf(impact_speed * 0.045, 0.38, 0.92)
            _snap_to_map_surface()
            target_position = position
            continue

        var normal: Vector3 = collision.get_normal()
        normal.y = 0.0
        if normal.length_squared() <= 0.001:
            normal = position - other.position
        if normal.length_squared() <= 0.001:
            normal = get_side_vector()
        normal = normal.normalized()

        var relative_velocity: Vector3 = velocity - other.velocity
        relative_velocity.y = 0.0
        var normal_speed: float = absf(relative_velocity.dot(normal))
        var relative_speed: float = maxf(impact_speed, maxf(normal_speed, relative_velocity.length() * 0.65))
        if relative_speed < 1.2:
            continue

        var self_mass: float = maxf(collision_mass, 1.0)
        var other_mass: float = maxf(other.collision_mass, 1.0)
        var total_mass: float = self_mass + other_mass

        # Near-inelastic GTA-style contact: retain some longitudinal momentum
        # but never invert it.  A tiny normal separation keeps CharacterBodies
        # from remaining interpenetrated without turning the cars into balls.
        var self_retention: float = clampf(0.36 + (self_mass / total_mass) * 0.30, 0.42, 0.66)
        var other_retention: float = clampf(0.36 + (other_mass / total_mass) * 0.30, 0.42, 0.66)
        current_speed *= self_retention
        other.current_speed *= other_retention

        var separation_speed: float = clampf(relative_speed * 0.040, 0.10, 0.70)
        apply_external_impulse(normal * separation_speed * (other_mass / total_mass))
        other.apply_external_impulse(-normal * separation_speed * (self_mass / total_mass))

        if _crash_damage_cooldown <= 0.0 and relative_speed >= CRASH_DAMAGE_MIN_SPEED:
            _pending_crash_damage = maxi(_pending_crash_damage, clampi(roundi(relative_speed * 1.6), 5, 24))
            _crash_damage_cooldown = CRASH_DAMAGE_COOLDOWN
        if other._crash_damage_cooldown <= 0.0 and relative_speed >= CRASH_DAMAGE_MIN_SPEED:
            other._pending_crash_damage = maxi(other._pending_crash_damage, clampi(roundi(relative_speed * 1.35), 4, 20))
            other._crash_damage_cooldown = CRASH_DAMAGE_COOLDOWN
'''
vehicle = replace_func(vehicle, "_resolve_vehicle_collisions", anti_bounce)

# Sanity checks before CI asks Godot to parse the generated project.
checks = [
    ("police_driver_by_vehicle", main),
    ("response_hijacked", main),
    ("func _eject_police_driver", main),
    ("synced_cop.enforcement_role != role", main),
    ("previous_profile_hp", cop),
    ("Near-inelastic GTA-style contact", vehicle),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"v0.6.18.27 verification failed: {needle}")

main_path.write_text(main, encoding="utf-8")
vehicle_path.write_text(vehicle, encoding="utf-8")
cop_path.write_text(cop, encoding="utf-8")
print("Applied v0.6.18.27 gameplay fixes: Cop-driven law cars, durable Agent HP, anti-bounce crashes. 18.26 audio untouched.")
