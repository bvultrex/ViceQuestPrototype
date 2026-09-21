from pathlib import Path
import re, sys

root=Path(sys.argv[1]).resolve()

def read(rel): return (root/rel).read_text(encoding='utf-8')
def write(rel,text): (root/rel).write_text(text,encoding='utf-8')
def must(text, old, label):
    if old not in text: raise SystemExit(f'Missing shock patch anchor: {label}')
    return text

def replace(text, old, new, label):
    must(text,old,label)
    return text.replace(old,new,1)

# 1) Generate authentic GTA2 shooting and electrocution sprite sheets.
builder=read('tools/build_gta2_ped_animations.py')
builder=replace(builder,
"    'death':     {'offsets':list(range(81,98)), 'fps':10.0,'loop':False},",
"    'death':     {'offsets':list(range(81,98)), 'fps':10.0,'loop':False},\n    # GTA2 Char_B4 state 3 resolves to baseId+139 while attacking.\n    'shoot':     {'offsets':[139],              'fps':1.0, 'loop':True},\n    # ped_state_2::electrocuted_27 => animation state 17 => baseId+151..155.\n    'electrocute':{'offsets':list(range(151,156)),'fps':8.0,'loop':True},",
'ped source animation offsets')
write('tools/build_gta2_ped_animations.py',builder)

anim=read('scripts/ped_animation.gd')
anim=replace(anim,
'    "idle_alt_a", "idle_alt_b", "death"\n]',
'    "idle_alt_a", "idle_alt_b", "death", "shoot", "electrocute"\n]',
'ped animation names')
anim=replace(anim,
'    "death": 17,\n}',
'    "death": 17,\n    "shoot": 1,\n    "electrocute": 5,\n}',
'ped animation counts')
anim=replace(anim,
'    "death": 10.0,\n}',
'    "death": 10.0,\n    "shoot": 1.0,\n    "electrocute": 8.0,\n}',
'ped animation fps')
anim=replace(anim,
'    "death": false,\n}',
'    "death": false,\n    "shoot": true,\n    "electrocute": true,\n}',
'ped animation loops')
write('scripts/ped_animation.gd',anim)

# 2) Player reaction and authentic fire pose.
player=read('scripts/player.gd')
player=replace(player,
'var _fire_pose_remaining: float = 0.0',
'var _fire_pose_remaining: float = 0.0\nvar _electrocute_remaining: float = 0.0',
'player electro timer')
player=replace(player,
'    if _ped_visual == null or _fire_pose_remaining > 0.0 or not is_alive:',
'    if _ped_visual == null or _fire_pose_remaining > 0.0 or _electrocute_remaining > 0.0 or not is_alive:',
'player movement animation guard')
old_fire='''func show_fire_pose() -> void:
    if not is_alive or _ped_visual == null:
        return
    _fire_pose_remaining = FIRE_POSE_TIME
    # Keep the shared framework simple for now: hold the first authentic armed
    # locomotion frame during the short muzzle-flash window. A dedicated GTA2
    # pistol-fire sequence can be mapped later without changing player code.
    _ped_visual.show_frame("armed_walk", 0)
'''
new_fire='''func show_fire_pose(_weapon_id: int = -1) -> void:
    if not is_alive or _ped_visual == null or _electrocute_remaining > 0.0:
        return
    _fire_pose_remaining = FIRE_POSE_TIME
    # GTA2 Char_B4 attack flag uses the dedicated baseId+139 frame.
    _ped_visual.show_frame("shoot", 0)

func show_melee_pose() -> void:
    if not is_alive or _ped_visual == null or _electrocute_remaining > 0.0:
        return
    _fire_pose_remaining = FIRE_POSE_TIME
    _ped_visual.show_frame("armed_walk", 0)

func show_electrocute(duration: float = 2.2) -> void:
    if not is_alive or _ped_visual == null or vehicle_id != 0:
        return
    _electrocute_remaining = maxf(_electrocute_remaining, duration)
    _fire_pose_remaining = 0.0
    velocity = Vector3.ZERO
    _ped_visual.set_animation_enabled(true)
    _ped_visual.play_state("electrocute", true)
'''
player=replace(player,old_fire,new_fire,'player fire pose')
player=player.replace('        _fire_pose_remaining = 0.0\n    elif not was_alive:', '        _fire_pose_remaining = 0.0\n        _electrocute_remaining = 0.0\n    elif not was_alive:',1)
player=player.replace('        _fire_pose_remaining = 0.0\n\nfunc snap_to_position', '        _fire_pose_remaining = 0.0\n        _electrocute_remaining = 0.0\n\nfunc snap_to_position',1)
old_process='''    if _fire_pose_remaining > 0.0:
        _fire_pose_remaining = maxf(0.0, _fire_pose_remaining - delta)
        if _fire_pose_remaining <= 0.0 and is_alive:
            set_moving_state(_is_moving)
'''
new_process='''    if _electrocute_remaining > 0.0:
        _electrocute_remaining = maxf(0.0, _electrocute_remaining - delta)
        if _ped_visual != null and is_alive and vehicle_id == 0:
            if _electrocute_remaining > 0.0:
                _ped_visual.play_state("electrocute")
            else:
                set_moving_state(_is_moving)
    elif _fire_pose_remaining > 0.0:
        _fire_pose_remaining = maxf(0.0, _fire_pose_remaining - delta)
        if _fire_pose_remaining <= 0.0 and is_alive:
            set_moving_state(_is_moving)
'''
player=replace(player,old_process,new_process,'player process animation priority')
write('scripts/player.gd',player)

# 3) Civilian electric reaction. State 3 is reserved for networked electrocution.
civ=read('scripts/civilian.gd')
civ=replace(civ,
'var recovery_timer: float = 0.0',
'var recovery_timer: float = 0.0\nvar electrocute_timer: float = 0.0\nvar _fire_pose_remaining: float = 0.0',
'civilian electro timer')
insert_after='''func apply_unconscious(duration: float, threat_position: Vector3) -> void:
    if not is_alive or in_vehicle:
        return
    unconscious_timer = maxf(unconscious_timer, duration)
    recovery_timer = 0.0
    knockdown_threat = threat_position
    stun_timer = 0.0
    panic_timer = 0.0
    velocity = Vector3.ZERO
    if _visual != null:
        _visual.set_animation_enabled(true)
        _visual.play_state("death", true)
    _refresh_presence()
'''
must(civ,insert_after,'civilian unconscious function')
civ=civ.replace(insert_after,insert_after+'''
func apply_electrocute(duration: float) -> void:
    if not is_alive or in_vehicle:
        return
    electrocute_timer = maxf(electrocute_timer, duration)
    unconscious_timer = 0.0
    recovery_timer = 0.0
    stun_timer = 0.0
    panic_timer = 0.0
    velocity = Vector3.ZERO
    if _visual != null:
        _visual.set_animation_enabled(true)
        _visual.play_state("electrocute", true)
    _refresh_presence()
''',1)

marker='func is_incapacitated() -> bool:'
if marker not in civ: raise SystemExit('Missing shock patch anchor: civilian incapacitated marker')
civ=civ.replace(marker,'''func show_fire_pose() -> void:
    if not is_alive or in_vehicle or electrocute_timer > 0.0 or _visual == null:
        return
    _fire_pose_remaining = 0.15
    _visual.show_frame("shoot", 0)

''' + marker,1)

civ=replace(civ,
'    return unconscious_timer > 0.0 or recovery_timer > 0.0 or (not multiplayer.is_server() and _remote_knockdown_state > 0)',
'    return electrocute_timer > 0.0 or unconscious_timer > 0.0 or recovery_timer > 0.0 or (not multiplayer.is_server() and _remote_knockdown_state > 0)',
'civilian incapacitated state')
civ=replace(civ,
'''func knockdown_state() -> int:
    if unconscious_timer > 0.0:
        return 1''',
'''func knockdown_state() -> int:
    if electrocute_timer > 0.0:
        return 3
    if unconscious_timer > 0.0:
        return 1''',
'civilian network state 3')
server_anchor='''    if unconscious_timer > 0.0:
        unconscious_timer = maxf(0.0, unconscious_timer - delta)'''
must(civ,server_anchor,'civilian server unconscious')
civ=civ.replace(server_anchor,'''    if electrocute_timer > 0.0:
        electrocute_timer = maxf(0.0, electrocute_timer - delta)
        velocity = Vector3.ZERO
        knockback_velocity = Vector3.ZERO
        if _visual != null:
            _visual.play_state("electrocute")
        if electrocute_timer <= 0.0:
            trigger_panic(position - facing)
            if _visual != null:
                _visual.play_state("run", true)
            _refresh_presence()
        return
    if unconscious_timer > 0.0:
        unconscious_timer = maxf(0.0, unconscious_timer - delta)''',1)

fire_branch='''    var knockback: Vector3 = _take_knockback_step(delta)'''
if fire_branch not in civ: raise SystemExit('Missing shock patch anchor: civilian knockback branch')
civ=civ.replace(fire_branch,'''    if _fire_pose_remaining > 0.0:
        _fire_pose_remaining = maxf(0.0, _fire_pose_remaining - delta)
        velocity = Vector3.ZERO
        if _visual != null:
            _visual.show_frame("shoot", 0)
        return
    var knockback: Vector3 = _take_knockback_step(delta)''',1)

civ=civ.replace('        recovery_timer = 0.0\n        _remote_panicking = false', '        recovery_timer = 0.0\n        electrocute_timer = 0.0\n        _fire_pose_remaining = 0.0\n        _remote_panicking = false',1)
civ=civ.replace('    recovery_timer = 0.0\n    gang_combat_timer = 0.0', '    recovery_timer = 0.0\n    electrocute_timer = 0.0\n    _fire_pose_remaining = 0.0\n    gang_combat_timer = 0.0',1)
civ=civ.replace('''        elif _remote_knockdown_state == 2:
            _visual.show_frame("death", 6)
        else:''','''        elif _remote_knockdown_state == 2:
            _visual.show_frame("death", 6)
        elif _remote_knockdown_state == 3:
            _visual.play_state("electrocute", true)
        else:''',1)
civ=civ.replace('''        elif _remote_knockdown_state == 2:
            _visual.show_frame("death", 6)
        elif _remote_panicking:''','''        elif _remote_knockdown_state == 2:
            _visual.show_frame("death", 6)
        elif _remote_knockdown_state == 3:
            _visual.play_state("electrocute")
        elif _remote_panicking:''',1)

process_marker='''func _process(delta: float) -> void:
    if multiplayer.is_server():
        return'''
if process_marker not in civ: raise SystemExit('Missing shock patch anchor: civilian client process')
civ=civ.replace(process_marker,'''func _process(delta: float) -> void:
    if multiplayer.is_server():
        return
    _fire_pose_remaining = maxf(0.0, _fire_pose_remaining - delta)''',1)
civ=civ.replace('''        elif _remote_panicking:
            _visual.play_state("run")''','''        elif _fire_pose_remaining > 0.0:
            _visual.show_frame("shoot", 0)
        elif _remote_panicking:
            _visual.play_state("run")''',1)
write('scripts/civilian.gd',civ)

# 4) Cop electric reaction + networked authentic fire pose.
cop=read('scripts/cop.gd')
cop=replace(cop,'var recovery_timer: float = 0.0','var recovery_timer: float = 0.0\nvar electrocute_timer: float = 0.0', 'cop electro timer')
cop=replace(cop,'var _label: Label3D','var _label: Label3D\nvar _fire_pose_remaining: float = 0.0','cop fire timer')
anchor='''func apply_unconscious(duration: float, threat_position: Vector3) -> void:
    if not is_alive:
        return
    unconscious_timer = maxf(unconscious_timer, duration)
    recovery_timer = 0.0
    knockdown_threat = threat_position
    velocity = Vector3.ZERO
    if _visual != null:
        _visual.play_state("death", true)
    _refresh_visuals()
'''
must(cop,anchor,'cop unconscious')
cop=cop.replace(anchor,anchor+'''
func apply_electrocute(duration: float) -> void:
    if not is_alive:
        return
    electrocute_timer = maxf(electrocute_timer, duration)
    unconscious_timer = 0.0
    recovery_timer = 0.0
    velocity = Vector3.ZERO
    _moving = false
    _armed = false
    if _visual != null:
        _visual.play_state("electrocute", true)
    _refresh_visuals()

func show_fire_pose() -> void:
    if not is_alive or electrocute_timer > 0.0 or _visual == null:
        return
    _fire_pose_remaining = 0.15
    _visual.show_frame("shoot", 0)
''',1)
cop=replace(cop,
'    return unconscious_timer > 0.0 or recovery_timer > 0.0 or (not multiplayer.is_server() and _remote_knockdown_state > 0)',
'    return electrocute_timer > 0.0 or unconscious_timer > 0.0 or recovery_timer > 0.0 or (not multiplayer.is_server() and _remote_knockdown_state > 0)',
'cop incapacitated')
cop=replace(cop,
'''func knockdown_state() -> int:
    if unconscious_timer > 0.0:
        return 1''',
'''func knockdown_state() -> int:
    if electrocute_timer > 0.0:
        return 3
    if unconscious_timer > 0.0:
        return 1''',
'cop network state 3')
cop=replace(cop,
'''func status_step(delta: float) -> void:
    if unconscious_timer > 0.0:''',
'''func status_step(delta: float) -> void:
    _fire_pose_remaining = maxf(0.0, _fire_pose_remaining - delta)
    if electrocute_timer > 0.0:
        electrocute_timer = maxf(0.0, electrocute_timer - delta)
        _moving = false
        _armed = false
        velocity = Vector3.ZERO
        if _visual != null:
            _visual.play_state("electrocute")
        if electrocute_timer <= 0.0:
            recovery_flee_timer = 2.2
            recovery_flee_direction = -facing
            if _visual != null:
                _visual.play_state("run", true)
        return
    if unconscious_timer > 0.0:''',
'cop status electrocute')
cop=replace(cop,
'''    elif is_incapacitated():
        _visual.show_frame("death", 16 if knockdown_state() == 1 else 6)
    elif _moving:''',
'''    elif knockdown_state() == 3:
        _visual.play_state("electrocute")
    elif is_incapacitated():
        _visual.show_frame("death", 16 if knockdown_state() == 1 else 6)
    elif _fire_pose_remaining > 0.0:
        _visual.show_frame("shoot", 0)
    elif _moving:''',
'cop animation priority')
cop=cop.replace('        recovery_timer = 0.0\n        if _visual != null:', '        recovery_timer = 0.0\n        electrocute_timer = 0.0\n        if _visual != null:',1)
cop=cop.replace('    recovery_timer = 0.0\n    recovery_flee_timer = 0.0', '    recovery_timer = 0.0\n    electrocute_timer = 0.0\n    _fire_pose_remaining = 0.0\n    recovery_flee_timer = 0.0',1)
cop=cop.replace('''        elif _remote_knockdown_state == 2:
            _visual.show_frame("death", 6)
''','''        elif _remote_knockdown_state == 2:
            _visual.show_frame("death", 6)
        elif _remote_knockdown_state == 3:
            _visual.play_state("electrocute", true)
''',1)

if 'func _process(delta: float) -> void:\n    if multiplayer.is_server() or not response_active:\n        return' in cop:
    cop=cop.replace('func _process(delta: float) -> void:\n    if multiplayer.is_server() or not response_active:\n        return', 'func _process(delta: float) -> void:\n    if multiplayer.is_server() or not response_active:\n        return\n    _fire_pose_remaining = maxf(0.0, _fire_pose_remaining - delta)',1)
elif 'func _process(delta: float) -> void:\n    if multiplayer.is_server():\n        return' in cop:
    cop=cop.replace('func _process(delta: float) -> void:\n    if multiplayer.is_server():\n        return', 'func _process(delta: float) -> void:\n    if multiplayer.is_server():\n        return\n    _fire_pose_remaining = maxf(0.0, _fire_pose_remaining - delta)',1)
else:
    raise SystemExit('Missing shock patch anchor: cop client fire timer')
write('scripts/cop.gd',cop)

# 5) Main: electric hit state, network reactions, authentic fire pose and visible arc.
main=read('scripts/main.gd')
if 'var shock_arc_material_cache:' not in main:
    main=replace(main,'var projectile_material_cache: ShaderMaterial','var projectile_material_cache: ShaderMaterial\nvar shock_arc_material_cache: StandardMaterial3D', 'shock material cache')

old_stun=re.search(r'func _weapon_stun_hit\(.*?\n(?=func _melee_candidate_score)',main,re.S)
if not old_stun: raise SystemExit('Missing shock patch anchor: stun hit function')
new_stun='''func _weapon_stun_hit(shooter: ViceQuestPlayer, attacker_id: int, start: Vector3, direction: Vector3, weapon_range: float, damage: int) -> Vector3:
    var end: Vector3 = start + direction * weapon_range
    var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(start, end)
    query.exclude = [shooter.get_rid()]
    query.collision_mask = 3
    query.collide_with_areas = false
    var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
    if hit.is_empty():
        return end
    var collider: Object = hit["collider"]
    if collider is ViceQuestPlayer:
        var target: ViceQuestPlayer = collider as ViceQuestPlayer
        if target.peer_id != attacker_id:
            player_stun_timers[target.peer_id] = 2.2
            _damage_player(target.peer_id, damage, attacker_id)
            if alive_states.get(target.peer_id, false):
                _play_electrocute_reaction.rpc("player", target.peer_id, 2.2)
    elif collider != null and collider.has_meta("cop_id"):
        var cop_id: int = int(collider.get_meta("cop_id"))
        _damage_cop(cop_id, damage, attacker_id)
        if cops.has(cop_id) and cops[cop_id].is_alive:
            cops[cop_id].apply_electrocute(2.6)
            _play_electrocute_reaction.rpc("cop", cop_id, 2.6)
    elif collider != null and collider.has_meta("civilian_id"):
        var civilian_id: int = int(collider.get_meta("civilian_id"))
        if civilians.has(civilian_id):
            _damage_civilian(civilian_id, damage, attacker_id)
            if civilians[civilian_id].is_alive:
                civilians[civilian_id].apply_electrocute(2.8)
                _play_electrocute_reaction.rpc("civilian", civilian_id, 2.8)
    return hit["position"]

@rpc("authority", "call_local", "reliable")
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
main=main[:old_stun.start()]+new_stun+main[old_stun.end():]

main=main.replace('players[attacker_id].show_fire_pose()','players[attacker_id].show_melee_pose()',1)
main=main.replace('''        _spawn_combat_projectile(id, int(weapon_def["id"]), start, shot_direction, weapon_def)
        shooter.show_fire_pose()''','''        _spawn_combat_projectile(id, int(weapon_def["id"]), start, shot_direction, weapon_def)
        if delivery == "projectile_explosive":
            shooter.show_fire_pose(int(weapon_def["id"]))
        else:
            shooter.show_melee_pose()''',1)

main=main.replace('''                    _play_shot_effect.rpc(0, start, visual_end, cop.weapon_id)''','''                    _play_cop_fire_pose.rpc(cop_id)
                    _play_shot_effect.rpc(0, start, visual_end, cop.weapon_id)''',1)
main=main.replace('''                    _play_shot_effect.rpc(0, start, visual_end)''','''                    _play_cop_fire_pose.rpc(cop_id)
                    _play_shot_effect.rpc(0, start, visual_end)''',1)

gang_pos=main.find('func _server_gang_member_step')
if gang_pos >= 0:
    p=main.find('_play_shot_effect.rpc(0, start, visual_end)',gang_pos)
    if p>=0:
        main=main[:p]+'_play_civilian_fire_pose.rpc(civilian_id)\n    '+main[p:]

shot_marker='@rpc("authority", "call_local", "unreliable")\nfunc _play_shot_effect('
if shot_marker not in main: raise SystemExit('Missing shock patch anchor: shot effect marker')
pose_rpcs='''@rpc("authority", "call_local", "unreliable")
func _play_cop_fire_pose(cop_id: int) -> void:
    if cops.has(cop_id):
        cops[cop_id].show_fire_pose()

@rpc("authority", "call_local", "unreliable")
func _play_civilian_fire_pose(civilian_id: int) -> void:
    if civilians.has(civilian_id):
        civilians[civilian_id].show_fire_pose()

'''
main=main.replace(shot_marker,pose_rpcs+shot_marker,1)

shot=re.search(r'@rpc\("authority", "call_local", "unreliable"\)\nfunc _play_shot_effect\(.*?\n(?=@rpc\("authority", "call_local", "reliable"\)\nfunc _spawn_projectile_visual)',main,re.S)
if not shot: raise SystemExit('Missing shock patch anchor: complete shot effect')
new_shot='''@rpc("authority", "call_local", "unreliable")
func _play_shot_effect(shooter_id: int, start: Vector3, end: Vector3, weapon_override: int = -1) -> void:
    var shot_weapon: int = weapon_override if weapon_override >= 0 else WEAPON_DATA.PISTOL
    var tank_cannon: bool = false
    if shooter_id > 0 and weapon_override < 0:
        shot_weapon = int(player_current_weapon.get(shooter_id, WEAPON_DATA.PISTOL))
        if player_vehicle.has(shooter_id) and vehicles.has(player_vehicle[shooter_id]):
            tank_cannon = vehicles[player_vehicle[shooter_id]].variant_id == "tank"
    if players.has(shooter_id):
        players[shooter_id].show_fire_pose(shot_weapon)
    if audio_manager != null:
        audio_manager.play_weapon(shot_weapon, start, tank_cannon)

    var delta: Vector3 = end - start
    var distance: float = delta.length()
    if distance <= 0.02:
        return
    var direction: Vector3 = delta.normalized()

    if shot_weapon == WEAPON_DATA.STUN_GUN:
        _spawn_shock_arc(start, end)
        return

    var muzzle: MeshInstance3D = MeshInstance3D.new()
    muzzle.mesh = _get_muzzle_flash_mesh()
    muzzle.position = start + direction * 0.08 + Vector3(0.0, 0.08, 0.0)
    muzzle.rotation_degrees.x = -90.0
    muzzle.rotation.y = atan2(direction.x, direction.z)
    add_child(muzzle)

    var flash_tween: Tween = create_tween()
    flash_tween.set_parallel(true)
    flash_tween.tween_property(muzzle, "scale", Vector3(1.45, 1.45, 1.45), 0.065)
    flash_tween.finished.connect(muzzle.queue_free)
    if not runtime_low_power:
        var flash_light: OmniLight3D = OmniLight3D.new()
        flash_light.position = muzzle.position + Vector3(0.0, 0.18, 0.0)
        flash_light.light_color = Color("ffb84c")
        flash_light.light_energy = 2.8
        flash_light.omni_range = 2.0
        add_child(flash_light)
        flash_tween.tween_property(flash_light, "light_energy", 0.0, 0.065)
        flash_tween.finished.connect(flash_light.queue_free)

    _spawn_projectile_streak(start, end)

func _get_shock_arc_material() -> StandardMaterial3D:
    if shock_arc_material_cache != null:
        return shock_arc_material_cache
    var material: StandardMaterial3D = StandardMaterial3D.new()
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.albedo_color = Color("b9f7ff")
    material.emission_enabled = true
    material.emission = Color("5edfff")
    material.emission_energy_multiplier = 4.0
    material.no_depth_test = true
    shock_arc_material_cache = material
    return shock_arc_material_cache

func _spawn_shock_arc(start: Vector3, end: Vector3) -> void:
    var delta: Vector3 = end - start
    var distance: float = delta.length()
    if distance <= 0.04:
        return
    var direction: Vector3 = delta / distance
    var side: Vector3 = Vector3(-direction.z, 0.0, direction.x)
    if side.length_squared() <= 0.001:
        side = Vector3.RIGHT
    side = side.normalized()

    var root: Node3D = Node3D.new()
    root.name = "ShockArc"
    add_child(root)
    var segment_count: int = 6 if runtime_low_power else 9
    var points: Array[Vector3] = []
    points.append(start + Vector3(0.0, 0.05, 0.0))
    for i in range(1, segment_count):
        var t: float = float(i) / float(segment_count)
        var zig: float = sin(float(i) * 4.73 + distance * 1.31) * (0.10 + 0.025 * distance)
        var lift: float = sin(float(i) * 7.11) * 0.055
        points.append(start.lerp(end, t) + side * zig + Vector3(0.0, 0.05 + lift, 0.0))
    points.append(end + Vector3(0.0, 0.05, 0.0))

    for i in range(points.size() - 1):
        var a: Vector3 = points[i]
        var b: Vector3 = points[i + 1]
        var piece_delta: Vector3 = b - a
        var piece_length: float = piece_delta.length()
        if piece_length <= 0.001:
            continue
        var bolt: MeshInstance3D = MeshInstance3D.new()
        var box: BoxMesh = BoxMesh.new()
        box.size = Vector3(0.035, 0.035, piece_length)
        box.material = _get_shock_arc_material()
        bolt.mesh = box
        bolt.position = (a + b) * 0.5
        bolt.look_at(b, Vector3.UP)
        root.add_child(bolt)

    var tween: Tween = create_tween()
    tween.tween_interval(0.085)
    tween.finished.connect(root.queue_free)

'''
main=main[:shot.start()]+new_shot+main[shot.end():]
write('scripts/main.gd',main)

# 6) Keep weapon data explicit about electric delivery.
weapon=read('scripts/weapon_data.gd')
weapon=weapon.replace('"delivery": "stun_hitscan"','"delivery": "shock_arc"',1)
write('scripts/weapon_data.gd',weapon)
main=read('scripts/main.gd')
main=main.replace('if delivery == "stun_hitscan":','if delivery in ["stun_hitscan", "shock_arc"]:',1)
write('scripts/main.gd',main)

print('Applied GTA2 shoot/electrocute animation framework and Shock Gun lightning system.')
