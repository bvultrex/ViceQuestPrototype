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

**v0.6.18.5-Blue-ShockArc** — Commit `053bec3d92b897656e6dec7464a2dbf1e9988b23`  
CI-Run: `35656574036`  
APK-Name: `ViceQuest-v0.6.18.5-Blue-ShockArc.apk`

Der User hat diese APK 2026-09-22 als **letzte, die auf Quest 3 wirklich lief** bestätigt.

Quest-Sicht in diesem Build:

- 16:9 SubViewport-Brett im Raum (`QUEST_PANEL_SIZE` 1.72×0.9675, Position `(0, 1.05, -1.55)`, Tilt −18°)
- XR-Kamera `cull_mask = QUEST_DISPLAY_LAYER` (`1 << 19`)
- Spielwelt im `game_viewport` 1280×720
- UI in eigenem transparenten Viewport, `depth_test_disabled`
- World-Mesh auf Quest: `downtown_flat_*` (Straßen/Boden/Slopes)
- Gebäude nur in der stereoskopischen Popout-Schicht (`sync_popout_chunks` ist **kein** no-op)
- `quest_patch/presentation_rig.gd` aus diesem Commit (~466 Zeilen), SHA `0092b2202190…`

Das ist der Pfad, den die Quest **bewiesen** hat. **Nicht** der v0.6.17-Tabletop mit `world_scale = 10`.

### B. Was danach kam

| Version | Inhalt | Quest |
|---|---|---|
| 0.6.18.6 | Gehaltener Shock-Channel, Verzweigung | ungetestet / vermutlich schon Risiko |
| 0.6.18.7 | LOS, Hysterese, `local_fire_down()` | ungetestet |
| 0.6.18.8 | Downtown-Audio WIL 66/62/65/58/14/60 | **schwarz** (User) |
| 0.6.18.9 | Tabletop-Rewrite, Popout tot, kein `downtown_flat` | **falsche Diagnose** — 18.5 lief mit dem Brett |

`presentation_rig.gd` war von 18.5 bis 18.8 **bytegleich**. Das Schwarz von 18.8 kommt also nicht „weil SubViewport grundsätzlich tot ist“. 18.9 hat den Working-XR-Pfad zerstört.

### C. Aktueller CI-Stand

**v0.6.18.10-From-185** — 18.5-Brett wiederherstellen, Shock 18.7 + Audio 18.8 behalten.

- `quest_patch/presentation_rig.gd` = Stand `053bec3`
- Workflow wieder mit `downtown_flat` + `QUEST_DISPLAY_LAYER`
- Kein HeadsetBootMarker, kein Tabletop-`world_scale`

Falls 18.10 noch schwarz ist: nächster Schritt ist ein **reiner 18.5-Rebuild** ohne Channel/Audio-Patches, nicht noch ein Tabletop-Experiment.

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

### Quest-Präsentation (Working = 0.6.18.5)

16:9-Diorama-Brett im Raum, stereoskopische Gebäude-Popouts, UI auf eigener Depth-Ebene.  
**Nicht** Tabletop-`world_scale = 10` (das war 0.6.17 und der falsche 18.9-Fix).

`main.gd` ist ~6500 Zeilen und trägt Welt, Netzwerk, HUD, Combat, Population. Nicht „aufräumen“ als Nebenbei-Refactor.

---

## 4. Patch-Kette (Reihenfolge in CI, nicht umstellen)

1. Reconstruct ZIP + SHA256  
2. `quest_patch/build_popout_assets.py` (erzeugt popout **und** flat Meshes)  
3. `quest_patch/extract_enforcement_assets.py`  
4. Copy `quest_patch/presentation_rig.gd` → `scripts/presentation_rig.gd` (**18.5-Brett, nicht Tabletop**)  
   + früher `_build_camera()` in `_ready()`  
   + `ui_parent().add_child(boot/canvas)`  
   + input_bridge `ui_target`  
   + `downtown_flat` statt `downtown_visual` wenn `xr_active`  
   + `sync_popout_chunks` (echt, kein no-op)  
   + respawn `call_local`  
   + export `include_filter="assets/gta2/downtown/*"`  
5. `apply_v0618_upgrade.py` — Wanted 6, GTA2-HUD, kein Spawn-Tank  
6. `apply_shock_animation_upgrade.py` + `tools/build_gta2_ped_animations.py`  
7. `apply_shock_channel_upgrade.py` — Branching Channel  
8. `apply_shock_channel_quality.py` — LOS, Hysterese, Loop, Ammo, `local_fire_down()`  
9. `apply_gta2_audio_upgrade.py` — WIL-Samples, fügt `_play_electrocute_reaction` zurück falls Channel-Patch sie droppt  
10. OpenXR Vendors 4.3.1-stable  
11. Godot import + `--export-debug "Android Quest"`

Kein Patch darf `presentation_rig.gd` **nach** dem Copy auf Tabletop/`world_scale=10` umschreiben. Das 18.5-Brett ist der Working-Stand.

---

## 5. Nächste echte Spielfehler (User-Priorität)

Erst wenn **0.6.18.10** (oder reines 18.5) auf Quest **sichtbar** ist. Dann Downtown-Importer. Das Brett nicht nochmal durch Tabletop ersetzen.

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

Stereoskopisches Gebäude-Popout ist in 18.5 **aktiv** und Teil des Working-Stands. Dächer/Slopes dort verbessern, das Brett nicht abschalten.

---

## 6. Historische Regressionen — nie wieder

- Shock-Arc orange/gelb (das Z im Screenshot war nicht der Arc; Arc ist blau/weiß)
- Shock als One-Shot-Hitscan
- `Input.is_action_pressed("attack")` (Action existiert nicht; Quest-Trigger stirbt)
- Rampen/Treppen in die Popout-Gebäude-Schicht
- Gebäude flat **und** stereo gleichzeitig
- UI in derselben Depth wie Gebäude
- 18.5-Brett durch Tabletop `world_scale=10` ersetzen (18.9, falsche Schwarz-Diagnose)
- `downtown_flat` Swap entfernen
- `sync_popout_chunks` zum no-op machen
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
3. **Nicht** 0.6.17-Tabletop als Quest-Working-Stand nehmen. Working ist **0.6.18.5-Blue-ShockArc**.  
4. ZIP rekonstruieren, SHA prüfen. XR-Referenz: `quest_patch/presentation_rig.gd` aus Commit `053bec3`.  
5. Aktuellen `presentation_rig.gd` prüfen: `QUEST_DISPLAY_LAYER`, `_build_quest_display`, **kein** `HeadsetBootMarker`.  
6. CI-Workflow prüfen: `downtown_flat_%d_%d.meshbin` **muss** in `main.gd` landen.  
7. Nächste Arbeit nur nach User-Report:
   - **18.10 noch schwarz** → reiner 18.5-Rebuild ohne Channel/Audio. Kein Tabletop.
   - **Sichtbar** → Dächer / Innenwände / Slopes / Stairs (Punkt 5).
8. Nach Code: Workflow `EXPORT_NAME` hochzählen, commit auf `main`, CI-Artifact abwarten.  
9. User sagt, welches Artifact er sideloaded. CI-grün ≠ Quest-grün.

---

## 8. Was der Mensch liefern muss (kurz)

Nicht das ganze Godot-Projekt nochmal. Das liegt im Repo.

1. GitHub-Zugriff auf `bvultrex/ViceQuestPrototype` (Push auf `main` startet CI).  
2. Hardware-Ergebnis von **0.6.18.10-From-185**: 16:9-Brett sichtbar? Gebäude-Popout? Menü/Host? Shock/Audio?  
3. Falls 18.10 schwarz bleibt: bei **0.6.18.5-Blue-ShockArc** bleiben und Channel/Audio isoliert nachziehen.  
4. Diesen Prompt in jeden neuen Chat kleben.  
5. Optional für Importer: originale `wil.sty` / `wil.gmp` / `WIL.RAW` / `WIL.SDT` (im Workspace oft schon als 9-teilige ZIP).

---

## 9. Wichtige Commits

- Hardware-Working XR: `053bec3` `quest_patch/presentation_rig.gd` (~466 Zeilen, `QUEST_DISPLAY_LAYER`)
- Nicht verwenden für Quest-Sicht: `8379a32` (Tabletop-Rewrite 18.9)

Shock/Audio-Patches bleiben die aktuellen Dateien auf `main`. Nach jedem Push SHA selbst `sha256sum`en, nicht die alten 18.9-Werte kopieren.

Direkt vom Commit laden. Nicht aus APKs zurückentwickeln.

---

## 10. Startauftrag, wenn der User nichts weiter sagt

> Bleib auf Godot ViceQuest. Kein neues Spiel.  
> Basis: ZIP v0.6.17.0 (SHA `1554e2a9…caf3`) + `quest_patch/` auf `main`.  
> Quest-Sicht: **v0.6.18.5-Blue-ShockArc** 16:9-Brett + Popout. Nicht Tabletop 18.9.  
> Shock 0.6.18.7 und Audio 0.6.18.8 oben drauf.  
> Wenn 18.10 sichtbar: Dächer, Innenwände, Slope/Stair. Wenn schwarz: reines 18.5, kein Tabletop.

---

## 11. Einzeiler zum drüberkleben

```
CONTINUE ViceQuest Godot 4.5.1 Quest APK. Repo bvultrex/ViceQuestPrototype.
Immutable ZIP v0.6.17.0 SHA256 1554e2a9fd43624013cd8f3d934652176d7eb0d556c61d979105318baeb2caf3.
Patches only in quest_patch/. Last hardware-working APK: ViceQuest-v0.6.18.5-Blue-ShockArc (commit 053bec3).
Working XR is the 16:9 SubViewport board + QUEST_DISPLAY_LAYER + downtown_flat + live popout. NOT tabletop world_scale=10.
Do NOT rebuild as web. Do NOT re-apply the 0.6.18.9 tabletop rewrite (wrong black-screen diagnosis).
Keep Shock 0.6.18.7 (held channel, local_fire_down, LOS, hysteresis) and GTA2 audio 0.6.18.8 (WIL IDs 66/62/65/58/14/60).
Next after visibility: interior walls through roofs, missing roofs, wrong slope/stair gfx+physics.
Read CONTINUE_PROMPT.md in the repo before writing code.
```
