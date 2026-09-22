#!/usr/bin/env python3
"""v0.6.18.14 — GTA2 Downtown car shops.

The prototype's three cyan MAX PAYNT pads were debug markers, not the original
drive-through garages. Official Downtown `wil.mis` places 6 complexes x 4
stalls (no Gold Mines) as invisible CAR_SHOP objects. This patch:

- relocates every stall to those script coordinates
- applies the stall's one service on drive-through (no stop, no catalog)
- drops the floating labels / discs so the map building is the workshop
"""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()


def read(rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (root / rel).write_text(text, encoding="utf-8")


def replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing garage patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"Garage patch anchor is not unique: {label}")
    return text.replace(old, new, 1)


tuning = read("scripts/tuning_data.gd")
old_shops = '''const RESPRAY: String = "respray"
const VEHICLE_GUN: String = "vehicle_gun"
const MINES: String = "mines"
const OIL: String = "oil"

# Original GTA2 garage prices (Car_BC.cpp). Kept here so mods can rebalance
# the economy without changing the authoritative purchase code.
const COSTS: Dictionary = {
    RESPRAY: 5000,
    OIL: 10000,
    VEHICLE_GUN: 25000,
    MINES: 50000,
}

# Kept data-driven so mods can add shops or palettes without touching main.gd.
const SHOPS: Array[Dictionary] = [
    {
        "id": "central_test_bay",
        "name": "MAX PAYNT // CENTRAL",
        "position": Vector3(351.25, 0.10, 323.75),
        "radius": 6.0,
    },
    {
        "id": "east_service_lot",
        "name": "MAX PAYNT // EAST LOT",
        "position": Vector3(521.25, 0.10, 96.25),
        "radius": 8.5,
    },
    {
        "id": "south_workshop",
        "name": "MAX PAYNT // SOUTH",
        "position": Vector3(388.75, 0.10, 543.75),
        "radius": 6.0,
    },
]
'''
new_shops = '''const RESPRAY: String = "respray"
const VEHICLE_GUN: String = "vehicle_gun"
const MINES: String = "mines"
const OIL: String = "oil"
const BOMB: String = "bomb"

# Original GTA2 garage prices (Car_BC.cpp / StrategyWiki).
const COSTS: Dictionary = {
    RESPRAY: 5000,
    BOMB: 5000,
    OIL: 10000,
    VEHICLE_GUN: 25000,
    MINES: 50000,
}

# GTA2: law and gang cars cannot use Max Paynt. Buses can. Taxis get plates.
const RESPRAY_BLOCKED: Array[String] = [
    "cop_car", "swat_van", "agent_car", "tank", "armed_land_roamer", "land_roamer",
    "z_type", "dementia", "miara",
]
const PLATE_ONLY: Array[String] = ["taxi", "taxi_xpress", "bus"]

# Official Downtown wil.mis OBJ_DATA CAR_SHOP. Six 4-stall complexes, no Gold
# Mines. world = (gta2_x * 2.5, (gta2_z - 2) * 1.2 + 0.10, gta2_y * 2.5).
# Stall centres are 2 GTA2 tiles / 5 m apart; radius 2.15 keeps adjacent
# bays from overlapping while still catching a car in the lane.
const SHOPS: Array[Dictionary] = [
    # Flotsam SE, west of crusher. Row along +X.
    {"id": "flotsam_se_gun", "name": "SMITH & HESTON'S", "service": VEHICLE_GUN, "gta2": Vector3(200.50, 221.50, 2.00), "radius": 2.15},
    {"id": "flotsam_se_bomb", "name": "RED ARMY SURPLUS", "service": BOMB, "gta2": Vector3(202.50, 221.50, 2.00), "radius": 2.15},
    {"id": "flotsam_se_paint", "name": "MAX PAYNT", "service": RESPRAY, "gta2": Vector3(204.50, 221.50, 2.00), "radius": 2.15, "paint": Color("a33b3b")},
    {"id": "flotsam_se_oil", "name": "HELL OIL", "service": OIL, "gta2": Vector3(206.50, 221.50, 2.00), "radius": 2.15},
    # Zarelli (Zaibatsu). Column along +Y.
    {"id": "zarelli_gun", "name": "SMITH & HESTON'S", "service": VEHICLE_GUN, "gta2": Vector3(219.50, 30.50, 2.00), "radius": 2.15},
    {"id": "zarelli_bomb", "name": "RED ARMY SURPLUS", "service": BOMB, "gta2": Vector3(219.50, 32.50, 2.00), "radius": 2.15},
    {"id": "zarelli_paint", "name": "MAX PAYNT", "service": RESPRAY, "gta2": Vector3(219.50, 34.50, 2.00), "radius": 2.15, "paint": Color("565a64")},
    {"id": "zarelli_oil", "name": "HELL OIL", "service": OIL, "gta2": Vector3(219.50, 36.50, 2.00), "radius": 2.15},
    # Fruitbat (Loonies), elevated z=3.
    {"id": "fruitbat_gun", "name": "SMITH & HESTON'S", "service": VEHICLE_GUN, "gta2": Vector3(20.50, 60.50, 3.00), "radius": 2.15},
    {"id": "fruitbat_bomb", "name": "RED ARMY SURPLUS", "service": BOMB, "gta2": Vector3(22.50, 60.50, 3.00), "radius": 2.15},
    {"id": "fruitbat_paint", "name": "MAX PAYNT", "service": RESPRAY, "gta2": Vector3(24.50, 60.50, 3.00), "radius": 2.15, "paint": Color("7dbb54")},
    {"id": "fruitbat_oil", "name": "HELL OIL", "service": OIL, "gta2": Vector3(26.50, 60.50, 3.00), "radius": 2.15},
    # Shiroto (Yakuza).
    {"id": "shiroto_gun", "name": "SMITH & HESTON'S", "service": VEHICLE_GUN, "gta2": Vector3(42.50, 136.50, 2.00), "radius": 2.15},
    {"id": "shiroto_bomb", "name": "RED ARMY SURPLUS", "service": BOMB, "gta2": Vector3(44.50, 136.50, 2.00), "radius": 2.15},
    {"id": "shiroto_paint", "name": "MAX PAYNT", "service": RESPRAY, "gta2": Vector3(46.50, 136.50, 2.00), "radius": 2.15, "paint": Color("1a1a1e")},
    {"id": "shiroto_oil", "name": "HELL OIL", "service": OIL, "gta2": Vector3(48.50, 136.50, 2.00), "radius": 2.15},
    # Funabashi (Yakuza).
    {"id": "funabashi_gun", "name": "SMITH & HESTON'S", "service": VEHICLE_GUN, "gta2": Vector3(82.50, 160.50, 2.00), "radius": 2.15},
    {"id": "funabashi_bomb", "name": "RED ARMY SURPLUS", "service": BOMB, "gta2": Vector3(84.50, 160.50, 2.00), "radius": 2.15},
    {"id": "funabashi_paint", "name": "MAX PAYNT", "service": RESPRAY, "gta2": Vector3(86.50, 160.50, 2.00), "radius": 2.15, "paint": Color("4c83d1")},
    {"id": "funabashi_oil", "name": "HELL OIL", "service": OIL, "gta2": Vector3(88.50, 160.50, 2.00), "radius": 2.15},
    # Flotsam, east of church / south of Omnitron.
    {"id": "omnitron_gun", "name": "SMITH & HESTON'S", "service": VEHICLE_GUN, "gta2": Vector3(205.50, 121.50, 2.00), "radius": 2.15},
    {"id": "omnitron_bomb", "name": "RED ARMY SURPLUS", "service": BOMB, "gta2": Vector3(207.50, 121.50, 2.00), "radius": 2.15},
    {"id": "omnitron_paint", "name": "MAX PAYNT", "service": RESPRAY, "gta2": Vector3(209.50, 121.50, 2.00), "radius": 2.15, "paint": Color("c4a04a")},
    {"id": "omnitron_oil", "name": "HELL OIL", "service": OIL, "gta2": Vector3(211.50, 121.50, 2.00), "radius": 2.15},
]
'''
tuning = replace(tuning, old_shops, new_shops, "tuning shop table")
tuning = replace(
    tuning,
    '''static func shop_near(world_position: Vector3) -> Dictionary:
    for shop: Dictionary in SHOPS:
        var shop_position: Vector3 = shop["position"]
        if Vector2(world_position.x, world_position.z).distance_to(Vector2(shop_position.x, shop_position.z)) <= float(shop["radius"]):
            return shop
    return {}
''',
    '''static func gta2_world(gta2: Vector3) -> Vector3:
    return Vector3(gta2.x * 2.5, (gta2.z - 2.0) * 1.2 + 0.10, gta2.y * 2.5)

static func stall_world(shop: Dictionary) -> Vector3:
    if shop.has("position"):
        return shop["position"]
    return gta2_world(shop["gta2"])

static func shop_near(world_position: Vector3) -> Dictionary:
    for shop: Dictionary in SHOPS:
        var shop_position: Vector3 = stall_world(shop)
        if absf(world_position.y - shop_position.y) > 0.85:
            continue
        if Vector2(world_position.x, world_position.z).distance_to(Vector2(shop_position.x, shop_position.z)) <= float(shop["radius"]):
            return shop
    return {}
''',
    "shop_near world helper",
)
tuning = replace(
    tuning,
    '''    for shop: Dictionary in SHOPS:
        var center3: Vector3 = shop["position"]
        var center: Vector2 = Vector2(center3.x, center3.z)
        var closest: Vector2 = _closest_point_on_segment(center, a, b)
        if closest.distance_to(center) <= float(shop["radius"]) + padding:
            return shop
''',
    '''    var mid_y: float = (from_position.y + to_position.y) * 0.5
    for shop: Dictionary in SHOPS:
        var center3: Vector3 = stall_world(shop)
        if absf(mid_y - center3.y) > 0.85:
            continue
        var center: Vector2 = Vector2(center3.x, center3.z)
        var closest: Vector2 = _closest_point_on_segment(center, a, b)
        if closest.distance_to(center) <= float(shop["radius"]) + padding:
            return shop
''',
    "shop_crossed world helper",
)
write("scripts/tuning_data.gd", tuning)

vehicle = read("scripts/vehicle.gd")
vehicle = replace(
    vehicle,
    "var has_vehicle_gun: bool = false\nvar has_mines: bool = false\nvar has_oil_slick: bool = false\n",
    "var has_vehicle_gun: bool = false\nvar has_mines: bool = false\nvar has_oil_slick: bool = false\nvar has_vehicle_bomb: bool = false\nvar bomb_fuse: float = 0.0\n",
    "vehicle bomb flags",
)
vehicle = replace(
    vehicle,
    "    has_vehicle_gun = false\n    has_mines = false\n    has_oil_slick = false\n    _apply_damage_visuals()\n",
    "    has_vehicle_gun = false\n    has_mines = false\n    has_oil_slick = false\n    has_vehicle_bomb = false\n    bomb_fuse = 0.0\n    _apply_damage_visuals()\n",
    "reset_tuning bomb",
)
write("scripts/vehicle.gd", vehicle)

main = read("scripts/main.gd")
old_build = '''func _build_tuning_shops() -> void:
    for shop: Dictionary in TUNING_DATA.SHOPS:
        var node: Node3D = Node3D.new()
        var shop_id: String = String(shop["id"])
        node.name = "TuningShop_%s" % shop_id
        node.position = shop["position"]

        var pad: MeshInstance3D = MeshInstance3D.new()
        var cylinder: CylinderMesh = CylinderMesh.new()
        cylinder.top_radius = float(shop["radius"]) * 0.72
        cylinder.bottom_radius = cylinder.top_radius
        cylinder.height = 0.025
        cylinder.radial_segments = 32
        var material: StandardMaterial3D = StandardMaterial3D.new()
        material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
        material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
        material.albedo_color = Color(0.12, 0.88, 1.0, 0.24)
        cylinder.material = material
        pad.mesh = cylinder
        pad.position.y = 0.035
        node.add_child(pad)

        # A real physics trigger makes workshop entry independent from the
        # server's population/update cadence. The distance poll below remains
        # as a conservative fallback for spawned or teleported vehicles.
        var trigger: Area3D = Area3D.new()
        trigger.name = "VehicleTrigger"
        trigger.collision_layer = 0
        trigger.collision_mask = 1
        trigger.monitoring = true
        trigger.monitorable = false
        var trigger_shape_node: CollisionShape3D = CollisionShape3D.new()
        var trigger_shape: CylinderShape3D = CylinderShape3D.new()
        trigger_shape.radius = float(shop["radius"])
        trigger_shape.height = 3.0
        trigger_shape_node.shape = trigger_shape
        trigger_shape_node.position.y = 1.0
        trigger.add_child(trigger_shape_node)
        trigger.body_entered.connect(_on_tuning_shop_body_entered.bind(shop_id))
        node.add_child(trigger)

        var label: Label3D = Label3D.new()
        label.text = "%s\\nDRIVE IN // AUTO OPEN" % String(shop["name"])
        label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
        label.no_depth_test = true
        label.position.y = 1.35
        label.font_size = 24
        label.outline_size = 8
        label.pixel_size = 0.009
        label.modulate = Color(0.60, 0.95, 1.0, 1.0)
        node.add_child(label)
        add_child(node)
        tuning_shop_nodes[shop_id] = node
'''
new_build = '''func _build_tuning_shops() -> void:
    # GTA2 car shops are invisible OBJ_DATA points inside already-mapped
    # drive-through buildings. No cyan pads, no floating MAX PAYNT labels.
    for shop: Dictionary in TUNING_DATA.SHOPS:
        var node: Node3D = Node3D.new()
        var shop_id: String = String(shop["id"])
        node.name = "TuningShop_%s" % shop_id
        node.position = TUNING_DATA.stall_world(shop)
        var trigger: Area3D = Area3D.new()
        trigger.name = "VehicleTrigger"
        trigger.collision_layer = 0
        trigger.collision_mask = 1
        trigger.monitoring = true
        trigger.monitorable = false
        var trigger_shape_node: CollisionShape3D = CollisionShape3D.new()
        var trigger_shape: CylinderShape3D = CylinderShape3D.new()
        trigger_shape.radius = float(shop["radius"])
        trigger_shape.height = 2.4
        trigger_shape_node.shape = trigger_shape
        trigger_shape_node.position.y = 0.55
        trigger.add_child(trigger_shape_node)
        trigger.body_entered.connect(_on_tuning_shop_body_entered.bind(shop_id))
        node.add_child(trigger)
        add_child(node)
        tuning_shop_nodes[shop_id] = node
'''
main = replace(main, old_build, new_build, "build tuning shops visuals")

main = replace(
    main,
    '''    var shop: Dictionary = TUNING_DATA.shop_near(vehicle.position)
    if shop.is_empty() or absf(vehicle.current_speed) > 2.0:
        _show_combat_message.rpc_id(player_id, "TUNING // Stop inside a Max Paynt bay")
        return
    var cost: int = TUNING_DATA.service_cost(service)
    if cost < 0:
        return
    var already_installed: bool = (
        (service == TUNING_DATA.VEHICLE_GUN and vehicle.has_vehicle_gun)
        or (service == TUNING_DATA.MINES and vehicle.has_mines)
        or (service == TUNING_DATA.OIL and vehicle.has_oil_slick)
    )
    if already_installed:
        _show_combat_message.rpc_id(player_id, "MAX PAYNT // Upgrade already installed")
        _send_tuning_menu(player_id, vehicle, String(shop["name"]), false)
        return
    if not _spend_money(player_id, cost):
        _show_combat_message.rpc_id(player_id, "MAX PAYNT // Not enough cash ($%d required)" % cost)
        _send_tuning_menu(player_id, vehicle, String(shop["name"]), false)
        return
    var result: String = ""
    match service:
        TUNING_DATA.RESPRAY:
            vehicle.paint_index = posmod(vehicle.paint_index + 1, TUNING_DATA.PAINTS.size())
            vehicle.paint_color = TUNING_DATA.paint(vehicle.paint_index)["color"]
            vehicle.set_damage_state(vehicle.max_hp, false)
            _sync_vehicle_damage_state.rpc(vehicle_id, vehicle.max_hp, false)
            _clear_wanted(player_id)
            result = "RESPRAY // %s // WANTED CLEARED" % String(TUNING_DATA.paint(vehicle.paint_index)["name"])
        TUNING_DATA.VEHICLE_GUN:
            vehicle.has_vehicle_gun = true
            result = "VEHICLE GUN INSTALLED // SPACE or LMB"
        TUNING_DATA.MINES:
            vehicle.has_mines = true
            result = "MINE DISPENSER INSTALLED // R"
        TUNING_DATA.OIL:
            vehicle.has_oil_slick = true
            result = "OIL SLICK INSTALLED // G"
        _:
            return
    vehicle.apply_tuning_state(vehicle.paint_index, vehicle.paint_color, vehicle.has_vehicle_gun, vehicle.has_mines, vehicle.has_oil_slick)
    _sync_vehicle_tuning.rpc(vehicle_id, vehicle.paint_index, vehicle.paint_color, vehicle.has_vehicle_gun, vehicle.has_mines, vehicle.has_oil_slick)
    _show_combat_message.rpc_id(player_id, "%s // -$%d" % [result, cost])
    _send_tuning_menu(player_id, vehicle, String(shop["name"]), false)
''',
    '''    var shop: Dictionary = TUNING_DATA.shop_near(vehicle.position)
    if shop.is_empty():
        shop = TUNING_DATA.shop_by_id(String(player_tuning_shop_inside.get(player_id, "")))
    if shop.is_empty():
        return
    if not String(shop.get("service", "")).is_empty():
        service = String(shop["service"])
    var cost: int = TUNING_DATA.service_cost(service)
    if cost < 0:
        return
    var variant_id: String = String(vehicle.variant_id)
    if service == TUNING_DATA.RESPRAY and TUNING_DATA.RESPRAY_BLOCKED.has(variant_id):
        _show_combat_message.rpc_id(player_id, "I ain't touchin' that! Get outta here!")
        return
    var already_installed: bool = (
        (service == TUNING_DATA.VEHICLE_GUN and vehicle.has_vehicle_gun)
        or (service == TUNING_DATA.MINES and vehicle.has_mines)
        or (service == TUNING_DATA.OIL and vehicle.has_oil_slick)
        or (service == TUNING_DATA.BOMB and vehicle.has_vehicle_bomb)
    )
    if already_installed:
        _show_combat_message.rpc_id(player_id, "%s // already fitted" % String(shop["name"]))
        return
    if not _spend_money(player_id, cost):
        _show_combat_message.rpc_id(player_id, "You ain't got enough cash! You need $%d." % cost)
        return
    var result: String = "That's $%d." % cost
    match service:
        TUNING_DATA.RESPRAY:
            vehicle.set_damage_state(vehicle.max_hp, false)
            _sync_vehicle_damage_state.rpc(vehicle_id, vehicle.max_hp, false)
            _clear_wanted(player_id)
            if TUNING_DATA.PLATE_ONLY.has(variant_id):
                result = "It's clean - the plates have been changed."
            elif shop.has("paint"):
                vehicle.paint_color = shop["paint"]
                result = "That's $%d." % cost
            else:
                vehicle.paint_index = posmod(vehicle.paint_index + 1, TUNING_DATA.PAINTS.size())
                vehicle.paint_color = TUNING_DATA.paint(vehicle.paint_index)["color"]
                result = "That's $%d." % cost
        TUNING_DATA.VEHICLE_GUN:
            vehicle.has_vehicle_gun = true
            result = "That's $%d." % cost
        TUNING_DATA.MINES:
            vehicle.has_mines = true
            result = "That's $%d." % cost
        TUNING_DATA.OIL:
            vehicle.has_oil_slick = true
            result = "That's $%d." % cost
        TUNING_DATA.BOMB:
            vehicle.has_vehicle_bomb = true
            vehicle.bomb_fuse = 0.0
            result = "The vehicle's been rigged!"
        _:
            return
    vehicle.apply_tuning_state(vehicle.paint_index, vehicle.paint_color, vehicle.has_vehicle_gun, vehicle.has_mines, vehicle.has_oil_slick)
    _sync_vehicle_tuning.rpc(vehicle_id, vehicle.paint_index, vehicle.paint_color, vehicle.has_vehicle_gun, vehicle.has_mines, vehicle.has_oil_slick)
    _show_combat_message.rpc_id(player_id, result)
''',
    "drive-through apply tuning",
)

main = replace(
    main,
    '''    var shop_id: String = String(shop["id"])
    var already_waiting: bool = (
        String(player_tuning_shop_inside.get(player_id, "")) == shop_id
        and bool(player_tuning_paused.get(player_id, false))
    )
    vehicle.current_speed = 0.0
    inputs[player_id] = Vector2.ZERO
    player_tuning_shop_inside[player_id] = shop_id
    player_tuning_paused[player_id] = true
    if not already_waiting:
        _send_tuning_menu(player_id, vehicle, String(shop["name"]), true)
    return true
''',
    '''    var shop_id: String = String(shop["id"])
    if String(player_tuning_shop_inside.get(player_id, "")) == shop_id:
        return true
    player_tuning_shop_inside[player_id] = shop_id
    player_tuning_paused.erase(player_id)
    _server_apply_tuning(player_id, String(shop.get("service", TUNING_DATA.RESPRAY)))
    return true
''',
    "open shop becomes drive-through",
)

main = replace(
    main,
    '''        if String(player_tuning_shop_inside.get(player_id, "")) == shop_id:
            if bool(player_tuning_paused.get(player_id, false)):
                vehicle.current_speed = 0.0
                inputs[player_id] = Vector2.ZERO
            continue
        _server_open_tuning_shop(player_id, vehicle, shop)
''',
    '''        if String(player_tuning_shop_inside.get(player_id, "")) == shop_id:
            continue
        _server_open_tuning_shop(player_id, vehicle, shop)
''',
    "do not pause inside stall",
)

main = replace(
    main,
    '''    if not vehicle.has_vehicle_gun or vehicle.is_destroyed:
        _show_combat_message.rpc_id(player_id, "VEHICLE // No mounted gun installed")
        return
''',
    '''    if vehicle.has_vehicle_bomb and vehicle.bomb_fuse <= 0.0:
        vehicle.bomb_fuse = 3.0
        _show_combat_message.rpc_id(player_id, "The vehicle's been rigged!")
    if not vehicle.has_vehicle_gun or vehicle.is_destroyed:
        if vehicle.bomb_fuse > 0.0:
            return
        _show_combat_message.rpc_id(player_id, "VEHICLE // No mounted gun installed")
        return
''',
    "prime car bomb on fire",
)

main = replace(
    main,
    '''        var crash_damage: int = vehicle.consume_crash_damage()
        if crash_damage > 0:
            _damage_vehicle(vehicle_id, crash_damage, vehicle.driver_id)
        if vehicle.driver_id != 0 and players.has(vehicle.driver_id):
''',
    '''        var crash_damage: int = vehicle.consume_crash_damage()
        if crash_damage > 0:
            _damage_vehicle(vehicle_id, crash_damage, vehicle.driver_id)
        if vehicle.has_vehicle_bomb and vehicle.bomb_fuse > 0.0:
            vehicle.bomb_fuse = maxf(0.0, vehicle.bomb_fuse - delta)
            if vehicle.bomb_fuse <= 0.0 and not vehicle.is_destroyed:
                _destroy_vehicle(vehicle_id, vehicle.driver_id)
                continue
        if vehicle.driver_id != 0 and players.has(vehicle.driver_id):
''',
    "tick car bomb fuse",
)
write("scripts/main.gd", main)

print("GTA2 Downtown garage drive-through patch applied.")
