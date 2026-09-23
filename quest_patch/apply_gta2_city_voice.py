#!/usr/bin/env python3
"""v0.6.18.25 — three traffic engines, original ped voices, real radio.

Runs after street FX. Blood pools and brake marks are left alone. Sparks
were already made smaller in the street-FX patch.

Original files used here, and the ones deliberately left out:

  WIL.RAW 8 kHz speech 216/218/221/224/240/251 idle
  WIL.RAW 8 kHz speech 233/236/237/238/245/292 panic
  Vocals/Elvis.wav once, when that line walks into view
  GTAudio 1.wav-11.wav as mono 22050 excerpts (Head through King)

Not wired: menu beds A.wav and D.wav, station 12, the short *a* alternates,
frontend art, intro.bik, and the 5500 Hz effect bank (not ped speech).
Horns stay out — those indices are not labeled in the bank.

Quest audio stays on AudioStreamPlayer. No positional 3D nodes.
"""
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent


def read(rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (root / rel).write_text(text, encoding="utf-8")


def replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing city-voice anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"City-voice anchor is not unique: {label} x{text.count(old)}")
    return text.replace(old, new, 1)


def tabify(text: str) -> str:
    lines = []
    for line in text.splitlines():
        spaces = len(line) - len(line.lstrip(" "))
        if spaces % 4 != 0:
            raise SystemExit(f"Bad indent in generated audio script: {line!r}")
        lines.append("\t" * (spaces // 4) + line.lstrip(" "))
    return "\n".join(lines) + "\n"


def span_replace(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_at = text.find(start)
    end_at = text.find(end)
    if start_at < 0 or end_at < 0 or end_at <= start_at:
        raise SystemExit(f"Missing city-voice span: {label}")
    if text.find(start, start_at + 1) != -1:
        raise SystemExit(f"City-voice span start is not unique: {label}")
    return text[:start_at] + replacement + text[end_at:]


RADIO = (
    "head",
    "rockstar",
    "krez",
    "lofi",
    "futuro",
    "funami",
    "lithium",
    "osmosis",
    "heavenly",
    "kgbh",
    "king",
)

for name in [f"ped_idle_{i}.wav" for i in range(6)] + [f"ped_panic_{i}.wav" for i in range(6)] + ["elvis_line.wav"]:
    src = here / "sfx" / name
    if not src.is_file() or src.stat().st_size < 64:
        raise SystemExit(f"Missing quest_patch/sfx/{name}")
    dst = root / "assets/audio/gta2/sfx" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

for name in RADIO:
    src = here / "radio" / f"{name}.wav"
    if not src.is_file() or src.stat().st_size < 100_000:
        raise SystemExit(f"Missing quest_patch/radio/{name}.wav")
    dst = root / "assets/audio/gta2/radio" / f"{name}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

audio = read("scripts/audio_manager.gd")
audio = replace(
    audio,
    """const EXTRA_PATHS: Dictionary = {
	"city": "res://assets/audio/gta2/beds/city.wav",
	"radio_night": "res://assets/audio/gta2/radio/radio_night.wav",
	"radio_funk": "res://assets/audio/gta2/radio/radio_funk.wav",
	"radio_spark": "res://assets/audio/gta2/radio/radio_spark.wav",
}
const STATIONS: PackedStringArray = ["RADIO OFF", "RADIO // NIGHT", "RADIO // FUNK", "RADIO // SPARK"]
const STATION_KEYS: PackedStringArray = ["", "radio_night", "radio_funk", "radio_spark"]
""",
    """const EXTRA_PATHS: Dictionary = {
	"city": "res://assets/audio/gta2/beds/city.wav",
	"radio_head": "res://assets/audio/gta2/radio/head.wav",
	"radio_rockstar": "res://assets/audio/gta2/radio/rockstar.wav",
	"radio_krez": "res://assets/audio/gta2/radio/krez.wav",
	"radio_lofi": "res://assets/audio/gta2/radio/lofi.wav",
	"radio_futuro": "res://assets/audio/gta2/radio/futuro.wav",
	"radio_funami": "res://assets/audio/gta2/radio/funami.wav",
	"radio_lithium": "res://assets/audio/gta2/radio/lithium.wav",
	"radio_osmosis": "res://assets/audio/gta2/radio/osmosis.wav",
	"radio_heavenly": "res://assets/audio/gta2/radio/heavenly.wav",
	"radio_kgbh": "res://assets/audio/gta2/radio/kgbh.wav",
	"radio_king": "res://assets/audio/gta2/radio/king.wav",
}
const STATIONS: PackedStringArray = ["RADIO OFF", "HEAD RADIO", "ROCKSTAR", "KREZ", "LO-FI FM", "FUTURO FM", "FUNAMI FM", "LITHIUM FM", "OSMOSIS FM", "HEAVENLY", "KGBH", "KING"]
const STATION_KEYS: PackedStringArray = ["", "radio_head", "radio_rockstar", "radio_krez", "radio_lofi", "radio_futuro", "radio_funami", "radio_lithium", "radio_osmosis", "radio_heavenly", "radio_kgbh", "radio_king"]
const PED_IDLE: PackedStringArray = ["ped_idle_0", "ped_idle_1", "ped_idle_2", "ped_idle_3", "ped_idle_4", "ped_idle_5"]
const PED_PANIC: PackedStringArray = ["ped_panic_0", "ped_panic_1", "ped_panic_2", "ped_panic_3", "ped_panic_4", "ped_panic_5"]
""",
    "radio station table",
)
audio = replace(
    audio,
    "var engine_player: AudioStreamPlayer\n",
    "var engine_player: AudioStreamPlayer\n"
    "var traffic_players: Array[AudioStreamPlayer] = []\n"
    "var _traffic_keys: Array[String] = []\n"
    "var _traffic_ids: Array[int] = []\n"
    "var _traffic_wanted: Array[bool] = []\n"
    "var _local_vehicle_id: int = 0\n"
    "var _ped_gate: float = 0.0\n"
    "var _elvis_spotted: bool = false\n",
    "traffic voice fields",
)
audio = replace(
    audio,
    '\tengine_player = _make_voice("LocalVehicleEngine", -6.0)\n',
    '\tengine_player = _make_voice("LocalVehicleEngine", -6.0)\n'
    "\tfor index in range(3):\n"
    '\t\ttraffic_players.append(_make_voice("TrafficEngine_%d" % index, -10.0))\n'
    '\t\t_traffic_keys.append("")\n'
    "\t\t_traffic_ids.append(-1)\n"
    "\t\t_traffic_wanted.append(false)\n",
    "three traffic players",
)
audio = span_replace(
    audio,
    "func station_name() -> String:\n",
    "func _process(_delta: float) -> void:\n",
    tabify(
        """
func station_name() -> String:
    if _station < 0 or _station >= STATIONS.size():
        return "RADIO OFF"
    return STATIONS[_station]

func cycle_radio() -> String:
    _station = (_station + 1) % STATIONS.size()
    if radio_player != null:
        _silence(radio_player)
    _radio_wanted = false
    update_bed()
    return station_name()

"""
    ),
    "radio cycle",
)
audio = replace(
    audio,
    "func _process(_delta: float) -> void:\n\t_sync_fire()\n",
    "func _process(_delta: float) -> void:\n\t_ped_gate = maxf(0.0, _ped_gate - _delta)\n\t_sync_fire()\n",
    "ped voice gate",
)
audio = replace(
    audio,
    "\tif _engine_wanted:\n\t\t_service_loop(engine_player)\n",
    "\tif _engine_wanted:\n\t\t_service_loop(engine_player)\n"
    "\tfor index in range(traffic_players.size()):\n"
    "\t\tif _traffic_wanted[index]:\n"
    "\t\t\t_service_loop(traffic_players[index])\n",
    "service traffic loops",
)
audio = replace(
    audio,
    "\t_driving = true\n",
    "\t_driving = true\n\t_local_vehicle_id = vehicle.vehicle_id\n",
    "remember driven car",
)
audio = replace(
    audio,
    "func stop_engine() -> void:\n\t_engine_key = \"\"\n\t_driving = false\n",
    "func stop_engine() -> void:\n\t_engine_key = \"\"\n\t_driving = false\n\t_local_vehicle_id = 0\n",
    "forget driven car",
)
audio = replace(
    audio,
    '\t_hold_loop(radio_player, STATION_KEYS[_station], -3.0)\n',
    '\t_hold_loop(radio_player, STATION_KEYS[_station], -7.0)\n',
    "radio level",
)
audio = span_replace(
    audio,
    "func update_nearby_traffic(vehicles: Dictionary) -> void:\n",
    "func update_bed() -> void:\n",
    tabify(
        """
func update_nearby_traffic(vehicles: Dictionary) -> void:
    # Three other moving cars, each with its own loop. The driven car stays
    # on the local engine so a full street is not one shared motor.
    if traffic_players.is_empty():
        return
    var chosen_nodes: Array = []
    var chosen_dist: Array[float] = []
    var chosen_ids: Array[int] = []
    for raw_id: Variant in vehicles.keys():
        var vehicle_id: int = int(raw_id)
        if _driving and vehicle_id == _local_vehicle_id:
            continue
        var candidate: Node = vehicles[raw_id]
        if candidate == null or not is_instance_valid(candidate):
            continue
        if bool(candidate.get("is_destroyed")):
            continue
        if absf(float(candidate.get("current_speed"))) < 0.35:
            continue
        var pos: Vector3 = (candidate as Node3D).position
        var distance: float = Vector2(pos.x - _ear.x, pos.z - _ear.z).length()
        if distance > 34.0:
            continue
        var placed: bool = false
        for slot in range(chosen_dist.size()):
            if distance < chosen_dist[slot]:
                chosen_dist.insert(slot, distance)
                chosen_nodes.insert(slot, candidate)
                chosen_ids.insert(slot, vehicle_id)
                placed = true
                break
        if not placed:
            chosen_dist.append(distance)
            chosen_nodes.append(candidate)
            chosen_ids.append(vehicle_id)
        while chosen_dist.size() > 3:
            chosen_dist.pop_back()
            chosen_nodes.pop_back()
            chosen_ids.pop_back()
    for index in range(traffic_players.size()):
        var player: AudioStreamPlayer = traffic_players[index]
        if index >= chosen_nodes.size():
            _traffic_wanted[index] = false
            _traffic_ids[index] = -1
            _traffic_keys[index] = ""
            if player.playing:
                player.stop()
            continue
        var near_vehicle: Node = chosen_nodes[index]
        var variant: String = str(near_vehicle.get("variant_id"))
        var key: String = String(ENGINE_BY_VARIANT.get(variant, "engine_standard"))
        if key != _traffic_keys[index] or player.stream == null or not player.playing:
            _traffic_keys[index] = key
            player.stream = _owned_loop_instance(key)
            player.set_meta("loop_pos", -1.0)
            player.set_meta("loop_stall", 0.0)
            if player.stream != null:
                player.play()
        _traffic_ids[index] = chosen_ids[index]
        if player.stream == null:
            _traffic_wanted[index] = false
            continue
        var max_speed: float = maxf(float(near_vehicle.get("max_forward_speed")), 0.1)
        var speed_ratio: float = clampf(absf(float(near_vehicle.get("current_speed"))) / max_speed, 0.0, 1.0)
        var nearness: float = 1.0 - clampf(chosen_dist[index] / 34.0, 0.0, 1.0)
        player.pitch_scale = (0.78 + speed_ratio * (0.34 if variant == "tank" else 0.62)) * (0.94 + float(index) * 0.05)
        var loud: float = lerpf(-16.0, -4.0, nearness * nearness)
        if _driving:
            loud -= 4.0
        player.volume_db = loud
        _traffic_wanted[index] = true
        _service_loop(player)

"""
    ),
    "three traffic engines",
)
audio += tabify(
    """
func _owned_loop_instance(sample_key: String) -> AudioStream:
    var shared: AudioStream = _owned_loop(sample_key)
    if shared is AudioStreamWAV:
        var src: AudioStreamWAV = shared as AudioStreamWAV
        var owned: AudioStreamWAV = AudioStreamWAV.new()
        owned.format = src.format
        owned.mix_rate = src.mix_rate
        owned.stereo = src.stereo
        owned.loop_mode = AudioStreamWAV.LOOP_FORWARD
        owned.loop_begin = 0
        owned.loop_end = 0
        owned.data = src.data
        return owned
    return shared

func play_ped_voice(kind: String, world_position: Vector3) -> void:
    var panic: bool = kind == "panic"
    if panic:
        if _ped_gate > 0.2:
            return
    elif _ped_gate > 0.0:
        return
    var keys: PackedStringArray = PED_PANIC if panic else PED_IDLE
    if keys.is_empty():
        return
    var radius: float = 18.0 if panic else 12.0
    if _ear_ready:
        var distance: float = Vector2(world_position.x, world_position.z).distance_to(Vector2(_ear.x, _ear.z))
        if distance > radius:
            return
    var sample_key: String = keys[randi() % keys.size()]
    var gain: float = -1.0 if panic else -6.0
    _play_heard(sample_key, world_position, gain, randf_range(0.96, 1.05), radius)
    _ped_gate = 0.22 if panic else 1.35

func elvis_spotted() -> bool:
    return _elvis_spotted

func play_elvis_spot(world_position: Vector3) -> void:
    if _elvis_spotted:
        return
    _elvis_spotted = true
    _play_heard("elvis_line", world_position, -2.0, 1.0, 24.0)
"""
)
write("scripts/audio_manager.gd", audio)

civilian = read("scripts/civilian.gd")
civilian = replace(
    civilian,
    "var forced_skin: int = -1\n",
    "var forced_skin: int = -1\n"
    "var _voice_wait: float = -1.0\n"
    "var _was_panicking: bool = false\n",
    "ped voice fields",
)
civilian = replace(
    civilian,
    """func server_step(delta: float) -> void:
    if not multiplayer.is_server() or not stream_active or in_vehicle:
""",
    """func server_step(delta: float) -> void:
    if multiplayer.is_server():
        if stream_active and not in_vehicle and is_alive:
            _service_ped_voice(delta, panic_timer > 0.0 or burning_timer > 0.0)
        else:
            _was_panicking = false
    if not multiplayer.is_server() or not stream_active or in_vehicle:
""",
    "server ped voice",
)
civilian = replace(
    civilian,
    """func _process(delta: float) -> void:
    if multiplayer.is_server():
        return
""",
    """func _process(delta: float) -> void:
    if multiplayer.is_server():
        return
    if stream_active and not in_vehicle and is_alive and _remote_knockdown_state == 0:
        _service_ped_voice(delta, _remote_panicking)
    elif not is_alive or in_vehicle:
        _was_panicking = false
""",
    "client ped voice",
)
if not civilian.endswith("\n"):
    civilian += "\n"
civilian += """
func _service_ped_voice(delta: float, panicking: bool) -> void:
    if _voice_wait < 0.0:
        _voice_wait = randf_range(2.0, 7.0)
    if panicking and not _was_panicking:
        _play_ped_sample("panic")
        _voice_wait = 1.8
    _was_panicking = panicking
    _voice_wait = maxf(0.0, _voice_wait - delta)
    if panicking or _voice_wait > 0.0:
        return
    _voice_wait = randf_range(8.0, 18.0)
    _play_ped_sample("idle")

func _play_ped_sample(kind: String) -> void:
    var main_node: Node = get_parent()
    if main_node == null:
        return
    var audio: Node = main_node.get("audio_manager")
    if audio != null and audio.has_method("play_ped_voice"):
        audio.call("play_ped_voice", kind, position)
"""
write("scripts/civilian.gd", civilian)

main = read("scripts/main.gd")
traffic_tail = """                else:
                    audio_manager.stop_engine()
                    audio_manager.note_footstep(p._is_moving)
                audio_manager.update_nearby_traffic(vehicles)
                _cue_elvis_line(target)
"""
heard_else = """                else:
                    audio_manager.update_nearby_traffic(vehicles)
                    audio_manager.note_footstep(p._is_moving)
"""
foot_else = """                else:
                    audio_manager.stop_engine()
                    audio_manager.note_footstep(p._is_moving)
"""
if heard_else in main:
    main = replace(main, heard_else, traffic_tail, "traffic while driving")
elif foot_else in main:
    main = replace(main, foot_else, traffic_tail, "traffic while driving")
else:
    raise SystemExit("Missing city-voice anchor: traffic call site")
main = replace(
    main,
    "func _spawn_elvis_line() -> void:\n",
    """func _cue_elvis_line(ear: Vector3) -> void:
    if audio_manager == null or audio_manager.elvis_spotted():
        return
    for elvis_index in range(6):
        var elvis_id: int = 9001 + elvis_index
        if not civilians.has(elvis_id):
            continue
        var elvis_ped: Node3D = civilians[elvis_id] as Node3D
        if elvis_ped == null or not is_instance_valid(elvis_ped):
            continue
        if Vector2(elvis_ped.position.x - ear.x, elvis_ped.position.z - ear.z).length() < 16.0:
            audio_manager.play_elvis_spot(elvis_ped.position)
            return

func _spawn_elvis_line() -> void:
""",
    "elvis cue",
)
write("scripts/main.gd", main)


def balance(rel: str) -> None:
    text = read(rel)
    depth = 0
    i = 0
    line = 1
    in_str = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if ch == "\n":
            line += 1
        if not in_str and ch == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if not in_str and ch == "/" and nxt == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    raise SystemExit(f"Extra ) in {rel} near line {line}")
        i += 1
    if in_str or depth != 0:
        raise SystemExit(f"Unbalanced {rel}: depth={depth} string={in_str}")


for rel, needle in (
    ("scripts/audio_manager.gd", "HEAD RADIO"),
    ("scripts/audio_manager.gd", "func play_ped_voice"),
    ("scripts/audio_manager.gd", "func play_elvis_spot"),
    ("scripts/audio_manager.gd", 'TrafficEngine_%d'),
    ("scripts/audio_manager.gd", "func _owned_loop_instance"),
    ("scripts/audio_manager.gd", "lerpf(-5.0, 0.5, speed_ratio)"),
    ("scripts/main.gd", "func _cue_elvis_line"),
    ("scripts/main.gd", "audio_manager.update_nearby_traffic(vehicles)"),
    ("scripts/civilian.gd", "func _service_ped_voice"),
    ("assets/audio/gta2/radio/head.wav", None),
    ("assets/audio/gta2/radio/king.wav", None),
    ("assets/audio/gta2/sfx/ped_idle_0.wav", None),
    ("assets/audio/gta2/sfx/ped_panic_5.wav", None),
    ("assets/audio/gta2/sfx/elvis_line.wav", None),
):
    path = root / rel
    if not path.exists() or path.stat().st_size < 32:
        raise SystemExit(f"City voice missing: {rel}")
    if needle and needle not in path.read_text(encoding="utf-8"):
        raise SystemExit(f"City voice needle missing: {rel} / {needle}")

if read("scripts/main.gd").count("audio_manager.update_nearby_traffic(vehicles)") != 1:
    raise SystemExit("Traffic update must run once per frame")
if "AudioStreamPlayer3D" in read("scripts/audio_manager.gd"):
    raise SystemExit("Positional audio node slipped into the mix")
for rel in ("scripts/audio_manager.gd", "scripts/civilian.gd", "scripts/main.gd"):
    balance(rel)

print("GTA2 radio, traffic voices and ped SFX applied.")
