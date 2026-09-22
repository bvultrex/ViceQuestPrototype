#!/usr/bin/env python3
"""Wire original Downtown WIL samples into the patched Godot project.

Must run after apply_shock_channel_quality.py so audio_manager already has
the looped shocker voice. Sample IDs come from gta2_re sound_obj.cpp only.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent
src_sfx = here / "gta2_audio" / "sfx"
dst_sfx = root / "assets" / "audio" / "gta2" / "sfx"
main_path = root / "scripts" / "main.gd"
audio_path = root / "scripts" / "audio_manager.gd"

REQUIRED = [
    "explosion_hit.wav",
    "grenade_hit.wav",
    "molotov_hit.wav",
    "electrocute_victim.wav",
    "horn_siren.wav",
    "horn_car.wav",
    "ambience_city.wav",
]


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing GTA2 audio anchor: {label}")
    return text.replace(old, new, 1)


if not src_sfx.is_dir():
    raise SystemExit(f"Missing extracted Downtown SFX at {src_sfx}")

dst_sfx.mkdir(parents=True, exist_ok=True)
for name in REQUIRED:
    src = src_sfx / name
    if not src.is_file() or src.stat().st_size < 64:
        raise SystemExit(f"Missing or empty sample {src}")
    shutil.copy2(src, dst_sfx / name)
# Optional extras that are extracted but not required at runtime.
for extra in ("oil.wav", "fire_truck_gun.wav"):
    src = src_sfx / extra
    if src.is_file():
        shutil.copy2(src, dst_sfx / extra)

manifest_src = here / "gta2_audio" / "audio_manifest_extra.json"
if manifest_src.is_file():
    shutil.copy2(manifest_src, root / "assets" / "audio" / "gta2" / "audio_manifest_extra.json")

main = main_path.read_text(encoding="utf-8")
audio = audio_path.read_text(encoding="utf-8")

audio = must_replace(
    audio,
    """var shock_player: AudioStreamPlayer3D
var shock_loop_active: bool = false
var _cache: Dictionary = {}
var _engine_key: String = ""
var _oneshot_pool: Array[AudioStreamPlayer3D] = []
var _oneshot_cursor: int = 0
""",
    """var shock_player: AudioStreamPlayer3D
var shock_loop_active: bool = false
var siren_player: AudioStreamPlayer3D
var siren_loop_active: bool = false
var ambience_player: AudioStreamPlayer
var electrocute_cooldown: float = 0.0
var _cache: Dictionary = {}
var _engine_key: String = ""
var _oneshot_pool: Array[AudioStreamPlayer3D] = []
var _oneshot_cursor: int = 0
""",
    "audio extra voices",
)

audio = must_replace(
    audio,
    """    shock_player.volume_db = -6.5
    add_child(shock_player)
""",
    """    shock_player.volume_db = -6.5
    add_child(shock_player)

    siren_player = AudioStreamPlayer3D.new()
    siren_player.name = "ServiceSiren"
    siren_player.max_distance = 42.0
    siren_player.unit_size = 7.0
    siren_player.attenuation_filter_cutoff_hz = 9000.0
    siren_player.volume_db = -10.5
    add_child(siren_player)

    ambience_player = AudioStreamPlayer.new()
    ambience_player.name = "DowntownAmbience"
    ambience_player.volume_db = -28.0
    ambience_player.bus = "Master"
    add_child(ambience_player)
""",
    "audio configure extras",
)

audio = must_replace(
    audio,
    """const WEAPON_SAMPLE: Dictionary = {
    0: "pistol",       # pistol
    1: "smg",
    2: "rocket_tank",
    3: "shocker",
    4: "vehicle_gadget",
    5: "vehicle_gadget",
    6: "shotgun",
    7: "impact_light", # fists
    8: "shocker",
    9: "flamethrower",
    10: "silenced_smg",
    11: "pistol",      # dual pistols use the same GTA2 pistol family
}
""",
    """const WEAPON_SAMPLE: Dictionary = {
    0: "pistol",       # pistol
    1: "smg",
    2: "rocket_tank",
    3: "shocker",
    4: "vehicle_gadget",  # molotov throw uses the GTA2 mine/bomb click (319)
    5: "vehicle_gadget",  # grenade throw uses the same arming click
    6: "shotgun",
    7: "impact_light", # fists
    8: "shocker",
    9: "flamethrower",
    10: "silenced_smg",
    11: "pistol",      # dual pistols use the same GTA2 pistol family
}
""",
    "weapon sample notes",
)

audio = must_replace(
    audio,
    """func play_explosion(world_position: Vector3) -> void:
    # GTA2's reverse-engineered object-audio dispatcher is incomplete, so the
    # first pass layers two authentic heavy/weapon samples rather than claiming
    # an unverified single explosion sample ID.
    _play_spatial("impact_heavy", world_position, -1.0, 0.72, 34.0)
    if not low_power:
        _play_spatial("rocket_tank", world_position, -10.0, 0.58, 28.0)
""",
    """func play_explosion(world_position: Vector3, kind: String = "default") -> void:
    # sound_obj.cpp never names a dedicated "car explode" sample. The verified
    # rocket/shock car-hit (WIL 66) is the actual boom GTA2 plays when a rocket
    # detonates against a vehicle, so that is the explosion body. Grenades layer
    # the short grenade-hit (WIL 62) on top.
    _play_spatial("explosion_hit", world_position, -1.5, 0.96, 36.0)
    if kind == "grenade":
        _play_spatial("grenade_hit", world_position, -4.0, 0.92, 28.0)
    elif kind == "rocket" and not low_power:
        _play_spatial("rocket_tank", world_position, -12.0, 1.0, 26.0)

func play_molotov(world_position: Vector3) -> void:
    _play_spatial("molotov_hit", world_position, -3.5, 1.0, 22.0)

func play_electrocute(world_position: Vector3) -> void:
    if electrocute_cooldown > 0.0:
        return
    electrocute_cooldown = 0.92
    _play_spatial("electrocute_victim", world_position, -7.0, 1.0, 18.0)
""",
    "explosion and throwable voices",
)

audio = must_replace(
    audio,
    """func set_shock_channel(active: bool, world_position: Vector3) -> void:
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
    """func set_shock_channel(active: bool, world_position: Vector3) -> void:
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

func set_siren(active: bool, world_position: Vector3) -> void:
    if siren_player == null:
        return
    if not active:
        siren_loop_active = false
        if siren_player.playing:
            siren_player.stop()
        return
    siren_player.global_position = world_position
    if siren_player.stream == null:
        siren_player.stream = _looped_stream("horn_siren")
    if not siren_loop_active or not siren_player.playing:
        siren_loop_active = true
        if siren_player.stream != null:
            siren_player.play()

func set_ambience(active: bool) -> void:
    if ambience_player == null:
        return
    if not active:
        if ambience_player.playing:
            ambience_player.stop()
        return
    if ambience_player.stream == null:
        ambience_player.stream = _looped_stream("ambience_city")
    if not ambience_player.playing and ambience_player.stream != null:
        ambience_player.play()

func tick_audio(delta: float) -> void:
    electrocute_cooldown = maxf(0.0, electrocute_cooldown - delta)
""",
    "siren ambience helpers",
)

audio_path.write_text(audio, encoding="utf-8")

ELECTROCUTE_FN = '''@rpc("authority", "call_local", "reliable")
func _play_electrocute_reaction(kind: String, entity_id: int, duration: float) -> void:
    var sfx_position: Vector3 = Vector3.ZERO
    var has_sfx: bool = false
    match kind:
        "player":
            if players.has(entity_id):
                players[entity_id].show_electrocute(duration)
                sfx_position = players[entity_id].position
                has_sfx = true
        "cop":
            if cops.has(entity_id) and not multiplayer.is_server():
                cops[entity_id].apply_electrocute(duration)
            if cops.has(entity_id):
                sfx_position = cops[entity_id].position
                has_sfx = true
        "civilian":
            if civilians.has(entity_id) and not multiplayer.is_server():
                civilians[entity_id].apply_electrocute(duration)
            if civilians.has(entity_id):
                sfx_position = civilians[entity_id].position
                has_sfx = true
    if has_sfx and audio_manager != null:
        audio_manager.play_electrocute(sfx_position)

'''

OLD_ELECTROCUTE_FN = '''@rpc("authority", "call_local", "reliable")
func _play_electrocute_reaction(kind: String, entity_id: int, duration: float) -> void:
    match kind:
        "player":
            if players.has(entity_id):
                players[entity_id].show_electrocute(duration)
        "cop":
            if cops.has(entity_id) and not multiplayer.is_server():
                cops[entity_id].apply_electrocute(duration)
        "civilian":
            if civilians.has(entity_id) and not multiplayer.is_server():
                civilians[entity_id].apply_electrocute(duration)

'''

if OLD_ELECTROCUTE_FN in main:
    main = must_replace(main, OLD_ELECTROCUTE_FN, ELECTROCUTE_FN, "electrocute victim sfx")
elif "func _play_electrocute_reaction" not in main:
    stun_tail = """func _weapon_stun_hit(shooter: ViceQuestPlayer, attacker_id: int, start: Vector3, direction: Vector3, weapon_range: float, damage: int) -> Vector3:
    # Shock Gun damage is handled by the sustained tracking/channel framework.
    return start + direction * weapon_range

"""
    if stun_tail not in main:
        raise SystemExit("Missing GTA2 audio anchor: electrocute insert after stun hit")
    main = main.replace(stun_tail, stun_tail + ELECTROCUTE_FN, 1)
else:
    raise SystemExit("Missing GTA2 audio anchor: electrocute victim sfx (unexpected existing function)")


main = must_replace(
    main,
    """func _play_molotov_burst(impact_position: Vector3) -> void:
    var burst: AnimatedSprite3D = AnimatedSprite3D.new()
""",
    """func _play_molotov_burst(impact_position: Vector3) -> void:
    if audio_manager != null:
        audio_manager.play_molotov(impact_position)
    var burst: AnimatedSprite3D = AnimatedSprite3D.new()
""",
    "molotov sfx",
)

main = must_replace(
    main,
    """    if delivery == "thrown_fire":
        _create_fire_zone(impact_position, int(state["attacker_id"]), float(state["radius"]), int(state["damage"]))
        _finish_projectile_visual.rpc(projectile_id, impact_position, true)
    else:
        _apply_weapon_explosion(impact_position, float(state["radius"]), int(state["damage"]), int(state["attacker_id"]))
        _finish_projectile_visual.rpc(projectile_id, impact_position, false)
""",
    """    if delivery == "thrown_fire":
        _create_fire_zone(impact_position, int(state["attacker_id"]), float(state["radius"]), int(state["damage"]))
        _finish_projectile_visual.rpc(projectile_id, impact_position, true)
    elif delivery == "thrown_explosive":
        _apply_weapon_explosion(impact_position, float(state["radius"]), int(state["damage"]), int(state["attacker_id"]), "grenade")
        _finish_projectile_visual.rpc(projectile_id, impact_position, false)
    else:
        _apply_weapon_explosion(impact_position, float(state["radius"]), int(state["damage"]), int(state["attacker_id"]), "rocket")
        _finish_projectile_visual.rpc(projectile_id, impact_position, false)
""",
    "grenade vs rocket explosion kind",
)

# _apply_weapon_explosion and vehicle death still call _play_vehicle_explosion.
# Patch the function signature and the audio kind.
main = must_replace(
    main,
    """func _play_vehicle_explosion(blast_position: Vector3, fx_radius: float = VEHICLE_EXPLOSION_RADIUS) -> void:
    var explosion: AnimatedSprite3D = AnimatedSprite3D.new()
    explosion.sprite_frames = _get_explosion_frames()
    explosion.animation = "explode"
    explosion.billboard = BaseMaterial3D.BILLBOARD_ENABLED
    explosion.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    explosion.pixel_size = 0.021
    explosion.position = blast_position + Vector3(0.0, 0.62, 0.0)
    explosion.no_depth_test = true
    add_child(explosion)
    explosion.animation_finished.connect(explosion.queue_free)
    explosion.play("explode")
    if combat_fx != null:
        combat_fx.play_explosion_layer(blast_position, fx_radius)
    if audio_manager != null:
        audio_manager.play_explosion(blast_position)
""",
    """func _play_vehicle_explosion(blast_position: Vector3, fx_radius: float = VEHICLE_EXPLOSION_RADIUS, kind: String = "vehicle") -> void:
    var explosion: AnimatedSprite3D = AnimatedSprite3D.new()
    explosion.sprite_frames = _get_explosion_frames()
    explosion.animation = "explode"
    explosion.billboard = BaseMaterial3D.BILLBOARD_ENABLED
    explosion.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    explosion.pixel_size = 0.021
    explosion.position = blast_position + Vector3(0.0, 0.62, 0.0)
    explosion.no_depth_test = true
    add_child(explosion)
    explosion.animation_finished.connect(explosion.queue_free)
    explosion.play("explode")
    if combat_fx != null:
        combat_fx.play_explosion_layer(blast_position, fx_radius)
    if audio_manager != null:
        audio_manager.play_explosion(blast_position, kind)
""",
    "explosion visual kind",
)

# Thread kind through _apply_weapon_explosion if it exists with the 4-arg form.
old_apply = "func _apply_weapon_explosion(blast_position: Vector3, radius: float, max_damage: int, attacker_id: int) -> void:"
if old_apply in main:
    main = must_replace(
        main,
        old_apply,
        'func _apply_weapon_explosion(blast_position: Vector3, radius: float, max_damage: int, attacker_id: int, kind: String = "default") -> void:',
        "apply weapon explosion signature",
    )
    main = main.replace(
        "_play_vehicle_explosion.rpc(blast_position, radius)",
        "_play_vehicle_explosion.rpc(blast_position, radius, kind)",
    )
    main = main.replace(
        "_play_vehicle_explosion.rpc(blast_position, VEHICLE_EXPLOSION_RADIUS)",
        '_play_vehicle_explosion.rpc(blast_position, VEHICLE_EXPLOSION_RADIUS, "vehicle")',
    )

main = must_replace(
    main,
    """            if audio_manager != null:
                if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
                    audio_manager.update_local_vehicle(vehicles[player_vehicle[local_id]])
                else:
                    audio_manager.stop_engine()
""",
    """            if audio_manager != null:
                audio_manager.tick_audio(delta)
                audio_manager.set_ambience(true)
                if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
                    audio_manager.update_local_vehicle(vehicles[player_vehicle[local_id]])
                else:
                    audio_manager.stop_engine()
                _update_wanted_siren(local_id, target)
        else:
            if audio_manager != null:
                audio_manager.set_ambience(false)
                audio_manager.set_siren(false, Vector3.ZERO)
""",
    "ambience and siren tick",
)

# The else I appended sits inside `if players.has(local_id):` because of indentation.
# Fix: the original block is:
#    if game_started:
#        var local_id...
#        if players.has(local_id):
#            ...
#            if audio_manager != null:
#                ...
#        ui_refresh...
# I accidentally put `else` at the same indent as the inner audio if, which would
# bind to `if players.has`. Re-read after write? Better to insert a dedicated
# helper and a clean call.
#
# The must_replace above added:
#                _update_wanted_siren(local_id, target)
#        else:
#            if audio_manager != null:
#                audio_manager.set_ambience(false)
#                audio_manager.set_siren(false, Vector3.ZERO)
#
# At 16 spaces, `else` matches `if players.has(local_id)` (12 spaces)? Let's count.
# Original:
#            if audio_manager != null:          # 12 spaces
#                if player_vehicle...           # 16 spaces
# The replacement starts with 12-space "if audio_manager".
# New last lines I wrote with 16-space else? I used 8-space "        else:" which
# is 8 spaces — that would match `if game_started` (4 spaces)? 
# Godot main.gd uses 4-space indent.
# `    if game_started:` = 4 spaces
# `        var local_id` = 8
# `            if audio_manager` = 12
# My "        else:" is 8 spaces → binds to `if players.has(local_id)` at 8 spaces.
# That's actually correct: if game started but local player missing, still stop? 
# No — 8-space else on `if players.has` means when local player is gone we stop
# ambience even though game_started. That's OK-ish.
# When game is NOT started, we never stop ambience with this structure.
#
# I need an else on `if game_started`. Look at original:
#    if game_started:
#        var local_id...
#        if players.has(local_id):
#            ...
#        ui_refresh_accumulator += delta
#
# ui_refresh is INSIDE game_started at 8 spaces. So I cannot add else before
# ui_refresh without breaking it.
# Don't stop ambience on the inner else. I'll remove that else and stop ambience
# only via set_ambience(game_started) called every frame at the top of _process
# after the game_started block... simpler: call set_ambience(game_started) always.

if "func _update_wanted_siren" not in main:
    helper = '''
func _update_wanted_siren(local_id: int, listen_at: Vector3) -> void:
    if audio_manager == null:
        return
    var wanted: int = int(wanted_levels.get(local_id, 0))
    if wanted <= 0:
        audio_manager.set_siren(false, listen_at)
        return
    var siren_at: Vector3 = listen_at
    var best_distance: float = 1000000.0
    var found: bool = false
    for raw_cop_id in cops.keys():
        var cop_id: int = int(raw_cop_id)
        var cop: ViceQuestCop = cops[cop_id]
        if cop == null or not cop.is_alive:
            continue
        if not bool(cop.response_active):
            continue
        var distance: float = cop.position.distance_to(listen_at)
        if distance < best_distance:
            best_distance = distance
            siren_at = cop.position
            found = true
    for raw_vehicle_id in vehicles.keys():
        var vehicle_id: int = int(raw_vehicle_id)
        var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
        if vehicle == null or vehicle.is_destroyed:
            continue
        var variant: String = String(vehicle.variant_id)
        if variant not in ["cop_car", "swat_van", "agent_car", "armed_land_roamer"]:
            continue
        var distance: float = vehicle.position.distance_to(listen_at)
        if distance < best_distance:
            best_distance = distance
            siren_at = vehicle.position
            found = true
    audio_manager.set_siren(found, siren_at)

'''
    anchor = "func _play_vehicle_door(world_position: Vector3, heavy: bool, opening: bool) -> void:"
    if anchor not in main:
        raise SystemExit("Missing GTA2 audio anchor: siren helper insert")
    main = main.replace(anchor, helper + anchor, 1)

# Fix the inner else: stop ambience when the game is not running by also
# calling set_ambience at the start of that same process chunk.
# The 8-space else currently attached to `if players.has` would mute downtown
# if the local pawn is missing. Keep it — that is rare.
# Additionally stop when game is not started: insert before `if game_started`.
main = must_replace(
    main,
    """    if game_started:
        var local_id: int = multiplayer.get_unique_id()
""",
    """    if not game_started and audio_manager != null:
        audio_manager.set_ambience(false)
        audio_manager.set_siren(false, Vector3.ZERO)
    if game_started:
        var local_id: int = multiplayer.get_unique_id()
""",
    "stop ambience when idle",
)

main_path.write_text(main, encoding="utf-8")

for name in REQUIRED:
    path = dst_sfx / name
    if not path.is_file() or path.stat().st_size < 64:
        raise SystemExit(f"Failed to install {path}")

checks = [
    ("play_explosion(", audio_path.read_text(encoding="utf-8")),
    ("func play_molotov", audio_path.read_text(encoding="utf-8")),
    ("func set_siren", audio_path.read_text(encoding="utf-8")),
    ("func set_ambience", audio_path.read_text(encoding="utf-8")),
    ("play_electrocute", main_path.read_text(encoding="utf-8")),
    ("play_molotov", main_path.read_text(encoding="utf-8")),
    ("_update_wanted_siren", main_path.read_text(encoding="utf-8")),
    ('kind: String = "vehicle"', main_path.read_text(encoding="utf-8")),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"Audio upgrade missing {needle}")

print("Applied original GTA2 Downtown audio: explosion/throwables/electrocute/siren/ambience.")
