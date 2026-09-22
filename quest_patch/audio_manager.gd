class_name ViceQuestAudioManager
extends Node

# Quest hears the headset, not the city. Gameplay audio is therefore mixed in
# 2D from the player's position: full volume in the car, quieter with distance
# for everyone else. The original WIL.RAW engines, impacts and weapons stay.
const SFX_ROOT: String = "res://assets/audio/gta2/sfx/"
const WASTED_PATH: String = "res://assets/audio/gta2/vocals/wasted.wav"
const EXTRA_PATHS: Dictionary = {
    "city": "res://assets/audio/gta2/beds/city.wav",
    "radio_night": "res://assets/audio/gta2/radio/radio_night.wav",
    "radio_funk": "res://assets/audio/gta2/radio/radio_funk.wav",
    "radio_spark": "res://assets/audio/gta2/radio/radio_spark.wav",
}
const STATIONS: PackedStringArray = ["RADIO OFF", "RADIO // NIGHT", "RADIO // FUNK", "RADIO // SPARK"]
const STATION_KEYS: PackedStringArray = ["", "radio_night", "radio_funk", "radio_spark"]

const ENGINE_BY_VARIANT: Dictionary = {
    "tank": "engine_tank",
    "z_type": "engine_sport",
    "van": "engine_van",
    "box_truck": "engine_van",
    "tow_truck": "engine_van",
    "bus": "engine_van",
    "bug": "engine_compact",
}

const WEAPON_SAMPLE: Dictionary = {
    0: "pistol",
    1: "smg",
    2: "rocket_tank",
    3: "shocker",
    4: "vehicle_gadget",
    5: "vehicle_gadget",
    6: "shotgun",
    7: "impact_light",
    8: "shocker",
    9: "flamethrower",
    10: "silenced_smg",
    11: "pistol",
}

var low_power: bool = false
var engine_player: AudioStreamPlayer
var radio_player: AudioStreamPlayer
var bed_player: AudioStreamPlayer
var wasted_player: AudioStreamPlayer
var _cache: Dictionary = {}
var _loop_cache: Dictionary = {}
var _engine_key: String = ""
var _radio_key: String = ""
var _bed_key: String = ""
var _oneshot_pool: Array[AudioStreamPlayer] = []
var _oneshot_cursor: int = 0
var _ear: Vector3 = Vector3.ZERO
var _ear_ready: bool = false
var _driving: bool = false
var _station: int = 1
var _skid_cooldown: float = 0.0

func configure(quest_low_power: bool) -> void:
    low_power = quest_low_power
    engine_player = _make_voice("LocalVehicleEngine", -10.0)
    radio_player = _make_voice("CarRadio", -8.0)
    bed_player = _make_voice("CityBed", -18.0)
    wasted_player = _make_voice("WastedVoice", -3.0)
    if ResourceLoader.exists(WASTED_PATH):
        wasted_player.stream = load(WASTED_PATH)
    var oneshot_count: int = 8 if low_power else 16
    for index in range(oneshot_count):
        var voice: AudioStreamPlayer = _make_voice("OneShot_%02d" % index, -6.0)
        _oneshot_pool.append(voice)

func _make_voice(voice_name: String, volume_db: float) -> AudioStreamPlayer:
    var voice: AudioStreamPlayer = AudioStreamPlayer.new()
    voice.name = voice_name
    voice.volume_db = volume_db
    voice.bus = &"Master"
    add_child(voice)
    return voice

func set_ear(world_position: Vector3) -> void:
    _ear = world_position
    _ear_ready = true

func station_name() -> String:
    return STATIONS[_station]

func cycle_radio() -> String:
    _station = (_station + 1) % STATIONS.size()
    _radio_key = ""
    update_bed()
    return station_name()

func _stream(sample_key: String) -> AudioStream:
    if _cache.has(sample_key):
        return _cache[sample_key] as AudioStream
    var path: String = String(EXTRA_PATHS.get(sample_key, SFX_ROOT + sample_key + ".wav"))
    if not ResourceLoader.exists(path):
        return null
    var stream: AudioStream = load(path) as AudioStream
    _cache[sample_key] = stream
    return stream

func _looped_stream(sample_key: String) -> AudioStream:
    if _loop_cache.has(sample_key):
        return _loop_cache[sample_key] as AudioStream
    var base: AudioStream = _stream(sample_key)
    if base == null:
        return null
    if base is AudioStreamWAV:
        var looped: AudioStreamWAV = (base as AudioStreamWAV).duplicate() as AudioStreamWAV
        looped.loop_mode = AudioStreamWAV.LOOP_FORWARD
        _loop_cache[sample_key] = looped
        return looped
    _loop_cache[sample_key] = base
    return base

func play_wasted() -> void:
    if wasted_player == null or wasted_player.stream == null:
        return
    wasted_player.stop()
    wasted_player.play()

func play_weapon(weapon_id: int, world_position: Vector3, tank_cannon: bool = false) -> void:
    var key: String = "rocket_tank" if tank_cannon else String(WEAPON_SAMPLE.get(weapon_id, "pistol"))
    var pitch: float = 1.04 if weapon_id == 11 else 0.98
    _play_heard(key, world_position, -4.0, pitch, 70.0)

func play_explosion(world_position: Vector3) -> void:
    _play_heard("impact_heavy", world_position, 1.0, 0.72, 90.0)
    if not low_power:
        _play_heard("rocket_tank", world_position, -8.0, 0.58, 80.0)

func play_vehicle_impact(world_position: Vector3, heavy: bool = false) -> void:
    _play_heard("impact_heavy" if heavy else "impact_light", world_position, -2.0, 0.94, 60.0)

func play_vehicle_door(world_position: Vector3, heavy: bool, opening: bool) -> void:
    var key: String
    if heavy:
        key = "door_heavy_open" if opening else "door_heavy_close"
    else:
        key = "door_light_open" if opening else "door_light_close"
    _play_heard(key, world_position, -6.0, 1.0, 28.0)

func note_skid(speed: float, steer_amount: float, max_speed: float) -> void:
    _skid_cooldown = maxf(0.0, _skid_cooldown - get_process_delta_time())
    if _skid_cooldown > 0.0 or not _driving:
        return
    var speed_ratio: float = clampf(speed / maxf(max_speed, 0.1), 0.0, 1.0)
    if speed_ratio < 0.42 or steer_amount < 0.55:
        return
    _skid_cooldown = 0.85
    _play_heard("skid", _ear, -10.0, lerpf(0.9, 1.08, speed_ratio), 12.0)

func update_local_vehicle(vehicle: ViceQuestVehicle) -> void:
    if engine_player == null or vehicle == null or vehicle.is_destroyed or vehicle.driver_id == 0:
        stop_engine()
        return
    _driving = true
    var key: String = String(ENGINE_BY_VARIANT.get(vehicle.variant_id, "engine_standard"))
    if key != _engine_key or engine_player.stream == null:
        _engine_key = key
        engine_player.stream = _looped_stream(key)
        if engine_player.stream != null:
            engine_player.play()
    if engine_player.stream == null:
        update_bed()
        return
    var speed_ratio: float = clampf(absf(vehicle.current_speed) / maxf(vehicle.max_forward_speed, 0.1), 0.0, 1.0)
    engine_player.pitch_scale = 0.78 + speed_ratio * (0.42 if vehicle.variant_id == "tank" else 0.62)
    var loud: float = lerpf(-14.0, -6.0, speed_ratio)
    if _station > 0:
        loud -= 7.0
    engine_player.volume_db = loud
    if not engine_player.playing:
        engine_player.play()
    update_bed()

func stop_engine() -> void:
    _engine_key = ""
    _driving = false
    if engine_player != null and engine_player.playing:
        engine_player.stop()
    update_bed()

func update_bed() -> void:
    if bed_player == null or radio_player == null:
        return
    if not _driving:
        _hold_loop(bed_player, "city", -17.0)
        _silence(radio_player)
        return
    if _station <= 0:
        _hold_loop(bed_player, "city", -26.0)
        _silence(radio_player)
        return
    _hold_loop(bed_player, "city", -34.0)
    _hold_loop(radio_player, STATION_KEYS[_station], -7.5)

func _hold_loop(player: AudioStreamPlayer, key: String, volume_db: float) -> void:
    var loaded: String = String(player.get_meta("loaded_key", ""))
    if loaded != key or player.stream == null:
        player.stream = _looped_stream(key)
        player.set_meta("loaded_key", key)
        if player.stream != null:
            player.play()
    if player.stream == null:
        return
    player.volume_db = volume_db
    if not player.playing:
        player.play()

func _silence(player: AudioStreamPlayer) -> void:
    if player.playing:
        player.stop()
    player.set_meta("loaded_key", "")

func _play_heard(sample_key: String, world_position: Vector3, full_db: float, pitch: float, radius: float) -> void:
    var stream: AudioStream = _stream(sample_key)
    if stream == null or _oneshot_pool.is_empty():
        return
    var volume_db: float = full_db
    if _ear_ready:
        var distance: float = Vector2(world_position.x, world_position.z).distance_to(Vector2(_ear.x, _ear.z))
        if distance > radius:
            return
        var nearness: float = clampf(1.0 - distance / radius, 0.0, 1.0)
        volume_db = full_db + lerpf(-26.0, 0.0, nearness * nearness)
    var player: AudioStreamPlayer = _oneshot_pool[_oneshot_cursor]
    _oneshot_cursor = (_oneshot_cursor + 1) % _oneshot_pool.size()
    player.stop()
    player.stream = stream
    player.volume_db = volume_db
    player.pitch_scale = pitch
    player.play()
