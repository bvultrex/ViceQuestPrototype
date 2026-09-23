class_name ViceQuestAudioManager
extends Node

# Quest hears the headset, not the city. One-shots already reach the ear.
# Loops must not copy the imported wav. That copy has no PCM on the Quest
# export and plays silence. Own a real AudioStreamWAV, and if the platform
# still drops the loop, restart it from _process.
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
var _oneshot_pool: Array[AudioStreamPlayer] = []
var _oneshot_cursor: int = 0
var _ear: Vector3 = Vector3.ZERO
var _ear_ready: bool = false
var _driving: bool = false
var _station: int = 0
var _skid_cooldown: float = 0.0
var _step_cooldown: float = 0.0
var _step_index: int = 0
var _fires: Dictionary = {}
var _engine_wanted: bool = false
var _radio_wanted: bool = false
var _bed_wanted: bool = false

func configure(quest_low_power: bool) -> void:
	low_power = quest_low_power
	engine_player = _make_voice("LocalVehicleEngine", -6.0)
	radio_player = _make_voice("CarRadio", -3.0)
	bed_player = _make_voice("CityBed", -8.0)
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
	return "RADIO OFF"

func cycle_radio() -> String:
	# Licensed GTA2 stations are not in WIL.RAW. Do not play the stand-in loops.
	_station = 0
	if radio_player != null:
		_silence(radio_player)
	_radio_wanted = false
	return station_name()

func _process(_delta: float) -> void:
	_sync_fire()
	if _engine_wanted:
		_service_loop(engine_player)
	if _radio_wanted:
		_service_loop(radio_player)
	if _bed_wanted:
		_service_loop(bed_player)

func _stream(sample_key: String) -> AudioStream:
	if _cache.has(sample_key):
		return _cache[sample_key] as AudioStream
	var path: String = String(EXTRA_PATHS.get(sample_key, SFX_ROOT + sample_key + ".wav"))
	if not ResourceLoader.exists(path):
		return null
	var stream: AudioStream = load(path) as AudioStream
	_cache[sample_key] = stream
	return stream

func _owned_loop(sample_key: String) -> AudioStream:
	if _loop_cache.has(sample_key):
		return _loop_cache[sample_key] as AudioStream
	var base: AudioStream = _stream(sample_key)
	if base == null:
		return null
	if base is AudioStreamWAV:
		var src: AudioStreamWAV = base as AudioStreamWAV
		var pcm: PackedByteArray = src.data
		if not pcm.is_empty() and src.format == AudioStreamWAV.FORMAT_16_BITS and not src.stereo:
			var owned: AudioStreamWAV = AudioStreamWAV.new()
			owned.format = AudioStreamWAV.FORMAT_16_BITS
			owned.mix_rate = src.mix_rate
			owned.stereo = false
			owned.loop_mode = AudioStreamWAV.LOOP_FORWARD
			owned.loop_begin = 0
			owned.loop_end = 0
			var frame_bytes: int = 2
			var target_bytes: int = int(src.mix_rate * 2.0) * frame_bytes
			if pcm.size() >= target_bytes:
				owned.data = pcm
			else:
				var tiled: PackedByteArray = PackedByteArray()
				while tiled.size() + pcm.size() <= target_bytes:
					tiled.append_array(pcm)
				if tiled.is_empty():
					tiled = pcm
				owned.data = tiled
			_loop_cache[sample_key] = owned
			return owned
	_loop_cache[sample_key] = base
	return base

func play_wasted() -> void:
	if wasted_player == null or wasted_player.stream == null:
		return
	wasted_player.stop()
	wasted_player.play()

func play_weapon(weapon_id: int, world_position: Vector3, tank_cannon: bool = false) -> void:
	# Molotov, grenade and fists have their own impact cues. Do not borrow the
	# gadget click or the metal crash for them.
	if weapon_id == 4 or weapon_id == 5 or weapon_id == 7:
		return
	var key: String = "rocket_tank" if tank_cannon else String(WEAPON_SAMPLE.get(weapon_id, "pistol"))
	var pitch: float = 1.04 if weapon_id == 11 else 0.98
	_play_heard(key, world_position, -4.0, pitch, 70.0)

func play_explosion(world_position: Vector3) -> void:
	# WIL 186 is the detonation. Sample 315 is the rocket launcher and must
	# not play on a crash or a grenade.
	_play_heard("detonation", world_position, 2.5, 1.0, 110.0)

func play_vehicle_impact(world_position: Vector3, heavy: bool = false) -> void:
	# WIL 12 is the bright metal crash. WIL 13 is only the hard hit.
	_play_heard("impact_heavy" if heavy else "impact_light", world_position, -1.0, 1.0, 48.0)

func play_molotov_break(world_position: Vector3) -> void:
	_play_heard("molotov_break", world_position, -1.0, 1.0, 26.0)

func play_grenade_bounce(world_position: Vector3, strength: float) -> void:
	_play_heard("grenade_bounce", world_position, -3.0, lerpf(0.9, 1.12, clampf(strength, 0.0, 1.0)), 18.0)

func play_fist_hit(world_position: Vector3) -> void:
	_play_heard("fist_hit", world_position, -2.0, 0.94 + randf() * 0.1, 16.0)

func note_footstep(moving: bool) -> void:
	_step_cooldown = maxf(0.0, _step_cooldown - get_process_delta_time())
	if _driving or not moving or _step_cooldown > 0.0:
		return
	_step_cooldown = 0.36
	var key: String = "step_%d" % (_step_index % 4)
	_step_index += 1
	_play_heard(key, _ear, -8.0, 0.96 if _step_index % 2 == 0 else 1.05, 10.0)

func note_fire_source(source_key: String, world_position: Vector3, active: bool) -> void:
	if active:
		_fires[source_key] = world_position
	else:
		_fires.erase(source_key)
	_sync_fire()

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
		engine_player.stream = _owned_loop(key)
		engine_player.set_meta("loop_pos", -1.0)
		engine_player.set_meta("loop_stall", 0.0)
		if engine_player.stream != null:
			engine_player.play()
	if engine_player.stream == null:
		_engine_wanted = false
		update_bed()
		return
	var speed_ratio: float = clampf(absf(vehicle.current_speed) / maxf(vehicle.max_forward_speed, 0.1), 0.0, 1.0)
	engine_player.pitch_scale = 0.82 + speed_ratio * (0.36 if vehicle.variant_id == "tank" else 0.55)
	var loud: float = lerpf(-8.0, -2.0, speed_ratio)
	if _station > 0:
		loud -= 3.0
	engine_player.volume_db = loud
	_engine_wanted = true
	_service_loop(engine_player)
	update_bed()

func stop_engine() -> void:
	_engine_key = ""
	_driving = false
	_engine_wanted = false
	if engine_player != null and engine_player.playing:
		engine_player.stop()
	update_bed()

func update_nearby_traffic(vehicles: Dictionary) -> void:
	# On foot the local engine is silent. Passing traffic still uses that
	# same loop, quieter as it gets further away. Parked cars stay quiet.
	if _driving or engine_player == null:
		return
	var best: Node = null
	var best_distance: float = 26.0
	for raw_id: Variant in vehicles.keys():
		var vehicle: Node = vehicles[raw_id]
		if vehicle == null or not is_instance_valid(vehicle):
			continue
		if bool(vehicle.get("is_destroyed")):
			continue
		if absf(float(vehicle.get("current_speed"))) < 0.6:
			continue
		var pos: Vector3 = (vehicle as Node3D).position
		var distance: float = Vector2(pos.x - _ear.x, pos.z - _ear.z).length()
		if distance < best_distance:
			best_distance = distance
			best = vehicle
	if best == null:
		if _engine_wanted:
			stop_engine()
		return
	var variant: String = str(best.get("variant_id"))
	var key: String = String(ENGINE_BY_VARIANT.get(variant, "engine_standard"))
	if key != _engine_key or engine_player.stream == null:
		_engine_key = key
		engine_player.stream = _owned_loop(key)
		engine_player.set_meta("loop_pos", -1.0)
		engine_player.set_meta("loop_stall", 0.0)
		if engine_player.stream != null:
			engine_player.play()
	if engine_player.stream == null:
		_engine_wanted = false
		return
	var max_speed: float = maxf(float(best.get("max_forward_speed")), 0.1)
	var speed_ratio: float = clampf(absf(float(best.get("current_speed"))) / max_speed, 0.0, 1.0)
	var nearness: float = 1.0 - clampf(best_distance / 26.0, 0.0, 1.0)
	engine_player.pitch_scale = 0.82 + speed_ratio * (0.36 if variant == "tank" else 0.55)
	engine_player.volume_db = lerpf(-28.0, -7.0, nearness * nearness)
	_engine_wanted = true
	_driving = false
	_service_loop(engine_player)

func update_bed() -> void:
	if radio_player == null:
		return
	if not _driving or _station <= 0:
		_silence(radio_player)
		_radio_wanted = false
		return
	_hold_loop(radio_player, STATION_KEYS[_station], -3.0)
	_radio_wanted = radio_player.stream != null

func _sync_fire() -> void:
	if bed_player == null:
		return
	var nearest: float = 99999.0
	if _ear_ready:
		for source_key in _fires.keys():
			var source_position: Vector3 = _fires[source_key]
			var distance: float = Vector2(source_position.x, source_position.z).distance_to(Vector2(_ear.x, _ear.z))
			if distance < nearest:
				nearest = distance
	if _fires.is_empty() or nearest > 22.0:
		_bed_wanted = false
		if bed_player.playing:
			_silence(bed_player)
		return
	var nearness: float = clampf(1.0 - nearest / 22.0, 0.0, 1.0)
	_hold_loop(bed_player, "fire_loop", lerpf(-14.0, -3.0, nearness * nearness))

func _hold_loop(player: AudioStreamPlayer, key: String, volume_db: float) -> void:
	var loaded: String = String(player.get_meta("loaded_key", ""))
	if loaded != key or player.stream == null:
		player.stream = _owned_loop(key)
		player.set_meta("loaded_key", key)
		player.set_meta("loop_pos", -1.0)
		player.set_meta("loop_stall", 0.0)
		if player.stream != null:
			player.play()
	if player.stream == null:
		if player == bed_player:
			_bed_wanted = false
		return
	player.volume_db = volume_db
	if player == bed_player:
		_bed_wanted = true
	_service_loop(player)

func _silence(player: AudioStreamPlayer) -> void:
	if player.playing:
		player.stop()
	player.set_meta("loaded_key", "")
	player.set_meta("loop_pos", -1.0)
	player.set_meta("loop_stall", 0.0)

func _service_loop(player: AudioStreamPlayer) -> void:
	if player == null or player.stream == null:
		return
	if not player.playing:
		player.set_meta("loop_stall", 0.0)
		player.play()
		return
	var length: float = player.stream.get_length()
	var pos: float = player.get_playback_position()
	var last: float = float(player.get_meta("loop_pos", -1.0))
	var stall: float = float(player.get_meta("loop_stall", 0.0))
	if last >= 0.0 and absf(pos - last) < 0.002:
		stall += get_process_delta_time()
	else:
		stall = 0.0
	player.set_meta("loop_pos", pos)
	player.set_meta("loop_stall", stall)
	if (length > 0.05 and pos >= length - 0.02) or stall > 0.12:
		player.set_meta("loop_stall", 0.0)
		player.play()

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
