# ViceQuest — Continue-Prompt für den nächsten Agenten

**Stand:** 2026-09-22  
**Sprache:** Deutsch mit den englischen Datei-/API-Namen  
**Zweck:** Diesen Text **vollständig** in einen neuen ChatGPT / Grok / Codex-Chat kleben.  
Ohne diesen Prompt bauen Modelle ein neues Web-Spiel. Das ist falsch.

---

## 0. Hartes Stopp-Schild

Du arbeitest **nicht** an einem neuen Spiel.

ViceQuest ist ein **bestehendes Godot-4.5.1-Projekt** mit Meta-Quest-APK, ENet-Multiplayer, Downtown-Map, Fahrzeugen, NPCs, Waffen, UI, Animationen und Quest-Steuerung. Das lief bereits auf Quest 3.

**Verboten:**
- neues Three.js / Canvas / Phaser / React-Spiel
- Godot durch WebGL ersetzen
- die Source-ZIP überschreiben
- das Spiel „neu aufsetzen, weil der Prompt kurz ist“

**Erlaubt:** `quest_patch/` + GitHub Actions CI auf der immutable Source-ZIP.

Wenn der User „wir wollen weitermachen“ sagt, ist das **dieser** Stand, nicht ein Clone.

---

## 1. Source of Truth

| Was | Wert |
|---|---|
| Repo | `https://github.com/bvultrex/ViceQuestPrototype` |
| Branch | `main` |
| Immutable Source-ZIP | `ViceQuestPrototype-v0.6.17.0-GTA2-Behavior-Audio-Quest-FIXED.zip` (im Repo als `.part1` + `.part2`) |
| SHA256 der zusammengefügten ZIP | `1554e2a9fd43624013cd8f3d934652176d7eb0d556c61d979105318baeb2caf3` |
| Interner Ordner nach Unzip | `ViceQuestPrototype_v0.6.17.0-GTA2-Behavior-Audio-Quest/` |
| Engine | Godot **4.5.1** + OpenXR Vendors **4.3.1-stable** |
| Renderer | `gl_compatibility` |
| Export | Android API 35, arm64-v8a, Preset `Android Quest` |
| CI | `.github/workflows/build-quest-apk.yml` auf Ubuntu 24.04 |

Die ZIP ist **unveränderlich**. Jede Änderung lebt in `quest_patch/`. CI macht: `cat part1 part2` → SHA prüfen → unzip → Python-Patches → Godot headless export → Artifact.

Referenz für GTA2-Verhalten: `CriminalRETeam/gta2_re` (GTA2 10.5). Original-Assets aus einer legalen GTA2-Installation (`wil.sty`, `wil.gmp`, `WIL.RAW`, `WIL.SDT`).

---

## 2. Zwei Stände, die du nicht verwechseln darfst

### A. Letzter **hardware-erprobter** Spielstand

**v0.6.17.0** — Tabletop-XR.

So sah Quest aus, als Bild, Steuerung, Downtown, Gebäude, Autos, NPCs, Waffen und Multiplayer **sichtbar und spielbar** waren:

- `XROrigin3D.world_scale = 10`
- Origin-Offset `(0, -8, 8)`
- `XRCamera3D` sieht die **echte Downtown-Welt** (`downtown_visual_*.meshbin`)
- Gameplay-`Camera3D.current = false`, sobald OpenXR läuft
- HUD/Boot auf dem **Haupt-Viewport** (OpenXR compositet 2D)
- `_try_enable_openxr()` **nur** auf Android
- Kollision: `StaticBody3D` + `ConcavePolygonShape3D`, Layer 1
- Downtown-Atlas **unshaded**

Originaldatei in der ZIP: `scripts/presentation_rig.gd` (~166 Zeilen).  
Das ist der Pfad, den die Quest **schon bewiesen** hat.

### B. Letzter **CI-Stand** (noch nicht hardware-bestätigt)

**v0.6.18.9-Quest-Visible** — Commit `8379a320f4017d6e4d782e8d60d7d6a764799c0a`

- GitHub Actions Run: `https://github.com/bvultrex/ViceQuestPrototype/actions/runs/35749749078`
- Artifact: `ViceQuest-v0.6.18.9-Quest-Visible`
- APK SHA256: `0d3c31d9374bbfb09840d41a427aad7e596cae838ee958b54aec8d0aa2eed475`

Dieser Build stellt den Tabletop-Pfad aus A wieder her und **behält** Shock 0.6.18.7 + Audio 0.6.18.8.  
**Popout ist absichtlich tot** (`sync_popout_chunks` = no-op), bis Sicht auf Hardware steht.

### C. Der schwarze Bildschirm (Regression, nicht der Working-Stand)

`v0.6.18.1`–`v0.6.18.8` haben die Quest-Sicht auf ein isoliertes 16:9-Brett umgestellt:

- XR-Kamera `cull_mask = 1 << 19` (nur Layer 20)
- Spielwelt in `SubViewport` → Quad im Raum
- UI in zweitem SubViewport
- CI hat `downtown_flat_*` (nur Straßen) als World-Mesh genutzt, Gebäude nur im Popout

Auf Quest 3 + GL Compatibility bleibt die SubViewport-Textur **schwarz**. Komplettes Headset-Schwarz.  
**HANDOFF v0.6.18.6 beschreibt genau diese kaputte Architektur als „aktuell“. Nicht wieder einführen.**

`v0.6.18.8` (Audio) ist der schwarze APK. Nicht installieren.

---

## 3. Was im Working-Stand bereits existiert

Nicht neu bauen. Erweitern.

### Welt / Map
- Downtown aus originalem `wil.sty` / GMP, 256×256×8 Schichten
- 16 Visual-Chunks `downtown_visual_X_Y.meshbin` + 16 Collision-Chunks
- Tile-Atlas, Slope-Layers, Ground-Layers, Surface-Mask
- Traffic-Graph, Fahrzeug-Routen, Ped-Routen, Population-Bank
- XY-Kachel 2.5, vertikaler Block 1.2, Straße bei Y=0
- Unterführungen brauchen Full-Z (Top-Lid-only löscht die untere Straße)

### Spieler / Input
- `scripts/player.gd`, `input_bridge.gd`
- Tastatur/Maus, Gamepad, Quest Touch über **dieselbe** Semantik
- Quest: linker Stick laufen/fahren, rechter Trigger Feuer, A Interact, B Reload, X/Y Waffen/Gadgets
- Tank: rechter Stick X dreht Turm, Trigger feuert Kanone
- `openxr_action_map.tres` Oculus-Touch-Profil

### Fahrzeuge
- Original-GTA2-Sprites (STY/CARI), inkl. Z-Type, Tank, SWAT, Agent, Pacifier, Land Roamer
- Physik, Türen, Wracks, Tank-Crush (Tank → normales Auto explodiert, Tank vs Tank normal)
- Max Paynt / Tuning: Area3D + Swept-Trigger, East Lot 8,5 m
- Routen-Drive-Mask: Gebäude-Treppen/Dachrampen stoßen Autos ab

### NPCs / Wanted
- Civilian-Pool, Cop-Pool, Gang-Territorien, Adaptive Population (Quest low-power)
- Ab 0.6.18: Wanted 1–6, Reserve-Pool statt statischer Test-Cops
- Test-Panzer am Spawn in 0.6.18 **entfernt** (nicht zurückbauen)

### Waffen / Combat
- GTA2-Handwaffen inkl. Shock, Pistole, Dual, SMG, Silenced, Shotgun, Rocket, Flamethrower, Fists
- Serverautorität, Combat-FX, Pickups
- Shock ab 0.6.18.7: gehaltener Channel, Baum-Verzweigung, LOS, Hysterese, Loop-SFX, Ammo/Tick
- Quest-Feuer: `local_fire_down()` / `input_bridge.fire_down()` — **nicht** `Input.is_action_pressed("attack")`

### UI
- Boot, Lobby/Host/Join, Workshop, Money-Digits, WASTED aus `wil.sty`
- 0.6.18 legt GTA2-HUD (Heads, Hearts, Digits, Respect) **über** funktionierende Controls
- Alte Controls nicht zerstörerisch umbauen

### Animation
- GTA2-Ped-Frames; Shoot Offset 139; Electrocute 151–155
- Player, Cops, Civilians

### Audio
- `audio_manager.gd`, WIL.RAW/WIL.SDT, Manifest
- 0.6.17: Motor-Familien, Türen, Waffen, WASTED-Voice
- 0.6.18.8 extra: Explosion 66, Granate 62, Molotov 65, Electrocute 58, Sirene 14, Ambience 60
- **Kein Radio** auf die Quest (zu groß)
- Keine erfundenen Sample-IDs; nur `gta2_re` `sound_obj.cpp` / Manifest

### Multiplayer
- Serverautoritär, `ENetMultiplayerPeer`, UDP **7777**
- LAN-Broadcast 7778, UPnP-Internet, Join Direct / VPN
- v0.6.15: 3 Snapshot-RPCs/Tick statt ~1480, separate Channels, Adaptive POP
- Host besitzt Bewegung, Waffen, HP, Fahrzeuge, Police, Gangs, Missionen, Cash

### Quest-Präsentation (Working)
Tabletop-Miniatur, Headset blickt in die echte Stadt. **Nicht** Vampire-Survivors-Fenster als einzige Sicht.

`main.gd` ist ~6500 Zeilen und trägt Welt, Netzwerk, HUD, Combat, Population. Nicht „aufräumen“ als Nebenbei-Refactor.

---

## 4. Patch-Kette (Reihenfolge in CI, nicht umstellen)

1. Reconstruct ZIP + SHA256  
2. `quest_patch/build_popout_assets.py` (erzeugt popout/flat Meshes; **World bleibt visual**)  
3. `quest_patch/extract_enforcement_assets.py`  
4. Copy `quest_patch/presentation_rig.gd` → `scripts/presentation_rig.gd`  
   + früher `_build_camera()` in `_ready()`  
   + `ui_parent().add_child(boot/canvas)`  
   + input_bridge `ui_target`  
   + `sync_popout_chunks` Calls (aktuell no-op)  
   + respawn `call_local`  
   + export `include_filter="assets/gta2/downtown/*"`  
5. `apply_v0618_upgrade.py` — Wanted 6, GTA2-HUD, kein Spawn-Tank  
6. `apply_shock_animation_upgrade.py` + `tools/build_gta2_ped_animations.py`  
7. `apply_shock_channel_upgrade.py` — Branching Channel  
8. `apply_shock_channel_quality.py` — LOS, Hysterese, Loop, Ammo, `local_fire_down()`  
9. `apply_gta2_audio_upgrade.py` — WIL-Samples, fügt `_play_electrocute_reaction` zurück falls Channel-Patch sie droppt  
10. OpenXR Vendors 4.3.1-stable  
11. Godot import + `--export-debug "Android Quest"`

Kein Patch darf `presentation_rig.gd` **nach** dem Copy wieder auf Layer-20/SubViewport zurückschreiben.

---

## 5. Nächste echte Spielfehler (User-Priorität)

Erst wenn 0.6.18.9 auf Quest **sichtbar** ist. Dann Downtown-Importer, nicht XR-Brett.

1. **Innere Wände durchs Dach sichtbar** (Nord-/Ost-Innenseiten, fehlende/falsch gefilterte Roof-Lids)  
2. **Fehlende Dächer**  
3. **Slope- und Stair-Grafik falsch** (`slope_type` → Ramp-Vertices, Diagonal-Familien 45–48, Atlas-Flip)  
4. **Slope- und Stair-Physik falsch** (Höhe-Sampler darf Roof-Layer nicht greifen ohne Step/Slope; Fahrzeuge nicht auf Gebäude-Treppen; Peds schon)

Dateien dafür (in der ZIP, per Patch anfassen):

- `tools/build_gta2_downtown.py`
- `tools/build_gta2_downtown_legacy.py`
- `tools/rebuild_gta2_runtime_assets.py`
- `tools/build_vehicle_surface_layers.py`
- `quest_patch/build_popout_assets.py`
- Runtime-Sampler in `scripts/main.gd` / vehicle height

Bekannte Importer-Regeln aus `GTA2_IMPORT_NOTES.md`:

- Full-Z, nicht nur Top-Lid  
- Godot OBJ flippt V → `1 - desired_v`  
- Collision layer-sensitiv, keine Vollsäule unter erhöhten Wänden  
- Traffic/Spawn-Punkte behalten GMP-Z, nicht aufs höchste Lid projizieren  

Stereoskopisches Gebäude-Popout **erst wieder**, wenn Tabletop sichtbar ist **und** Dächer/Slopes stimmen. Sonst kommt Schwarz oder doppelte Gebäude zurück.

---

## 6. Historische Regressionen — nie wieder

- Shock-Arc orange/gelb (das Z im Screenshot war nicht der Arc; Arc ist blau/weiß)
- Shock als One-Shot-Hitscan
- `Input.is_action_pressed("attack")` (Action existiert nicht; Quest-Trigger stirbt)
- Rampen/Treppen in die Popout-Gebäude-Schicht
- Gebäude flat **und** stereo gleichzeitig
- UI in derselben Depth wie Gebäude
- XR-Kamera nur Layer 20 / SubViewport als einzige Sicht
- `downtown_flat_*` als einziges Quest-World-Mesh
- Statische Test-Cops
- Test-Panzer am Player-Spawn
- Source-ZIP überschreiben
- Radio-WAVs in die APK
- Erfundene WIL-Sample-IDs
- Neues Web-Spiel statt Godot

---

## 7. Erste 30 Minuten eines neuen Agenten

1. `git clone` / Checkout `bvultrex/ViceQuestPrototype` `main`.  
2. Diesen `CONTINUE_PROMPT.md` + Repo-`README.md` lesen.  
3. **Nicht** den alten HANDOFF-Block „Quest = SubViewport-Brett“ als Zielarchitektur nehmen.  
4. ZIP rekonstruieren, SHA prüfen, Original-`scripts/presentation_rig.gd` als XR-Referenz behalten.  
5. Aktuellen `quest_patch/presentation_rig.gd` prüfen: `QUEST_WORLD_SCALE`, `HeadsetBootMarker`, **kein** `QUEST_DISPLAY_LAYER`.  
6. CI-Workflow prüfen: kein `downtown_flat_%d_%d.meshbin` in `main.gd`.  
7. Nächste Arbeit nur nach User-Report:
   - **Noch schwarz** → OpenXR-Init / Vendors-Pairing / Origin. **Kein** neues Isolation-Brett.
   - **Sichtbar** → Dächer / Innenwände / Slopes / Stairs (Punkt 5).
8. Nach Code: Workflow `EXPORT_NAME` hochzählen, commit auf `main`, CI-Artifact abwarten.  
9. User sagt, welches Artifact er sideloaded. CI-grün ≠ Quest-grün.

---

## 8. Was der Mensch liefern muss (kurz)

Nicht das ganze Godot-Projekt nochmal. Das liegt im Repo.

1. GitHub-Zugriff auf `bvultrex/ViceQuestPrototype` (Push auf `main` startet CI).  
2. Hardware-Ergebnis von **0.6.18.9**: grünes Rechteck? Downtown mit Gebäuden? immer noch schwarz? Menü/Host?  
3. Falls 0.6.18.9 schwarz bleibt: **Dateiname der letzten APK, die auf der Quest Bild hatte** (vermutlich `ViceQuest-v0.6.17.0-Quest.apk`).  
4. Diesen Prompt in jeden neuen Chat kleben.  
5. Optional für Importer: originale `wil.sty` / `wil.gmp` / `WIL.RAW` / `WIL.SDT` (im Workspace oft schon als 9-teilige ZIP).

---

## 9. Aktuelle Datei-SHAs auf main (`8379a32`)

```
quest_patch/presentation_rig.gd
  ae520b7e9a5a9407631868019a65d3077823c48972daab5179da3c8480219149
.github/workflows/build-quest-apk.yml
  c24cfc821a44865cb8fbcc3a0f1fafa50a6db36d15526b30b5b7f4f2a6afb15a
quest_patch/apply_v0618_upgrade.py
  2b1dedafd3b529589ac3b797e58b305a64501786e2352e00a5cc1723aba9740f
quest_patch/apply_shock_channel_upgrade.py
  4e9f2ea7fd97c4ec86537d0bd6cf5e4eb3243bb085cc7f17cb8434a7b99501b8
quest_patch/apply_shock_channel_quality.py
  8fc822870068424ac7ab57af16629af494ffad7e7de9129fc3123677dcdefe58
quest_patch/apply_shock_animation_upgrade.py
  a320fc1ab4be3431809995f8ff3705fef840fbb2d0403f61a637c6706f270bcb
quest_patch/apply_gta2_audio_upgrade.py
  e974b3ca396dba335f4963914bd758d1a2547d0326e9e575da15708b38d08bb8
```

Direkt vom Commit laden. Nicht aus APKs zurückentwickeln.

---

## 10. Startauftrag, wenn der User nichts weiter sagt

> Bleib auf Godot ViceQuest. Kein neues Spiel.  
> Basis: ZIP v0.6.17.0 (SHA `1554e2a9…caf3`) + `quest_patch/` auf `main`.  
> Quest-Sicht: Tabletop wie 0.6.17, nicht SubViewport-Layer-20.  
> Warte auf Hardware von 0.6.18.9.  
> Wenn sichtbar: Dächer, Innenwände, Slope/Stair-Grafik und -Physik im Downtown-Importer.  
> Shock 0.6.18.7 und Audio 0.6.18.8 nicht zurückbauen.

---

## 11. Einzeiler zum drüberkleben

```
CONTINUE ViceQuest Godot 4.5.1 Quest APK. Repo bvultrex/ViceQuestPrototype.
Immutable ZIP v0.6.17.0 SHA256 1554e2a9fd43624013cd8f3d934652176d7eb0d556c61d979105318baeb2caf3.
Patches only in quest_patch/. Last hardware-working XR: tabletop world_scale=10, XRCamera sees downtown_visual, HUD on main viewport.
Do NOT rebuild as web. Do NOT isolate XR camera to layer 20 / SubViewport board (black on Quest 3 GL Compatibility).
CI HEAD: v0.6.18.9-Quest-Visible commit 8379a32, run 35749749078, APK SHA256 0d3c31d9374bbfb09840d41a427aad7e596cae838ee958b54aec8d0aa2eed475.
Keep Shock 0.6.18.7 (held channel, local_fire_down, LOS, hysteresis) and GTA2 audio 0.6.18.8 (WIL IDs 66/62/65/58/14/60).
Popout deferred. Next gameplay bugs after visibility: interior walls through roofs, missing roofs, wrong slope/stair gfx+physics.
Read CONTINUE_PROMPT.md in the repo before writing code.
```
