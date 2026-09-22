# ViceQuest — Paste-Prompt für den nächsten Chat (vollständig kopieren)

Du bist der nächste Agent an einem **bestehenden Godot-4.5.1 Quest-Projekt**.  
**Kein neues Spiel. Kein Web/Three.js/Canvas/Phaser/React-Clone.**  
Änderungen nur in `quest_patch/` + GitHub Actions. Die Source-ZIP nie überschreiben.

---

## 0. Harte Fakten (2026-09-22, User-Hardware)

| Fakt | Wert |
|---|---|
| Repo | `https://github.com/bvultrex/ViceQuestPrototype` Branch `main` |
| Immutable ZIP | `ViceQuestPrototype-v0.6.17.0-GTA2-Behavior-Audio-Quest-FIXED.zip` als `.part1`+`.part2` |
| ZIP SHA256 | `1554e2a9fd43624013cd8f3d934652176d7eb0d556c61d979105318baeb2caf3` |
| Engine | Godot 4.5.1, OpenXR Vendors 4.3.1-stable, Android API 35, arm64, `gl_compatibility` |
| CI | `.github/workflows/build-quest-apk.yml` Ubuntu 24.04 |
| **Letzte APK die auf Quest 3 LIEF** | **`ViceQuest-v0.6.18.5-Blue-ShockArc`** Commit `053bec3d92b897656e6dec7464a2dbf1e9988b23` CI-Run `35656574036` |
| User 2026-09-22 | hat diese APK explizit als letzte funktionierende genannt |
| **0.6.18.8** Audio | komplett schwarz |
| **0.6.18.9** Tabletop-Rewrite | falsche Diagnose, nicht sideloaden |
| **0.6.18.10-From-185** Commit `76857df` Run `35751599571` SHA256 `7584f0f9…443812` | **18.5-Brett + Shock 18.7 + Audio 18.8 → IMMER NOCH KOMPLETT SCHWARZ** |

### Was 18.10 bewiesen hat

`quest_patch/presentation_rig.gd` war von 18.5 **bis 18.8 bytegleich** (SHA `0092b2202190…`, ~466 Zeilen, 16:9-Brett, `QUEST_DISPLAY_LAYER`, Popout).  
18.10 hat genau dieses Brett plus `downtown_flat` wiederhergestellt und trotzdem Schwarz.  
**Also ist das Brett nicht tot.** Die **Patches nach 18.5** (Shock-Channel, Quality, Audio, und die nachträglich aufgeblähte `apply_shock_animation_upgrade.py`) machen den Boot schwarz.

18.9 Tabletop (`world_scale=10`, HeadsetBootMarker, kein downtown_flat) war falsch. **Nicht wieder einführen.**

---

## 1. Sofortauftrag

1. **Exakten 18.5-Rebuild** als `ViceQuest-v0.6.18.11-Exact-185` (oder der Name der schon auf `main` liegt).  
   - `git checkout 053bec3 -- quest_patch/presentation_rig.gd quest_patch/apply_shock_animation_upgrade.py`  
   - CI wie 18.5: popout+flat, enforcement, VR-board (`downtown_flat` Swap, `QUEST_DISPLAY_LAYER`), `apply_v0618_upgrade.py`, **18.5-Animationspatch** (`shock_arc`, nicht `shock_chain`), OpenXR Vendors, Export.  
   - **Nicht** ausführen: `apply_shock_channel_upgrade.py`, `apply_shock_channel_quality.py`, `apply_gta2_audio_upgrade.py`. Dateien im Repo lassen, nur CI-Steps raus.  
   - Grep muss `"delivery": "shock_arc"` finden, nicht `shock_chain`.
2. Nach CI-grün: Artifact downloaden, APK **direkt hier als Datei-Download** an den User geben (nicht nur Actions-Link). User hat das ausdrücklich verlangt.
3. User sideloaded **nur** Exact-185. Wenn Bild wieder da: 18.5 ist reproduzierbar. Dann **einzeln** 18.6 / 18.7 / 18.8 bisecten, welches Patch den Boot tötet.  
   Wenn Exact-185 **auch schwarz**: CI/Godot/Vendors-Drift vs. Original-APK — Original `053bec3` Artifact Run `35656574036` zum Vergleich sideloaden, nicht Tabletop.
4. Dächer / Innenwände / Slopes **erst nach sichtbarem Brett**.

---

## 2. Working Quest-Sicht (18.5, nicht 0.6.17-Tabletop)

- 16:9 SubViewport-Brett: 1280×720, Panel 1.72×0.9675 m, Pos `(0, 1.05, -1.55)`, Tilt −18°
- XR-Kamera `cull_mask = 1 << 19` (`QUEST_DISPLAY_LAYER`)
- UI eigener Viewport, depth_test_disabled
- Quest-World-Mesh: `downtown_flat_*` (Straßen/Boden/Slopes)
- Gebäude: stereoskopisches Popout, `sync_popout_chunks` **lebt** (kein no-op)
- `_try_enable_openxr()` nur Android
- Frühes `_build_camera()` in `_ready()` (CI-sed, auch in 18.5)
- HUD: `presentation_rig.ui_parent().add_child(boot/canvas)`

Original-ZIP `scripts/presentation_rig.gd` (~166 Zeilen Tabletop) ist **nicht** der Quest-Working-Stand von 18.5.

---

## 3. Was schon im Spiel ist (nicht neu bauen)

Map+Gebäude Downtown 256×256×8, Autos+Routen, NPCs/Cops/Gangs, Waffen, Teile UI/GTA2-HUD, Spieler, Ped-Anims (Shoot 139, Electrocute 151–155), Multiplayer ENet UDP 7777 serverautoritär, Quest-Touch über `input_bridge.gd`, Wanted 1–6, kein Spawn-Tank, kein statischer Test-Cop.  
Shock in 18.5: blauer GTA2-Arc (`shock_arc`), noch kein gehaltener Channel.  
Audio 18.5: WIL Motor/Türen/Waffen/WASTED. Extra-Downtown-SFX (66/62/65/58/14/60) war 18.8 — **verdächtig für Schwarz, nicht jetzt anwenden**.

`main.gd` ~6500 Zeilen. Kein Aufräum-Refactor.

---

## 4. Nächste echte Bugs (nach Sicht)

1. Innere Wände durchs Dach (Nord/Ost)  
2. Fehlende Dächer  
3. Falsche Slope-/Stair-**Grafik**  
4. Falsche Slope-/Stair-**Physik**  

Dateien: `tools/build_gta2_downtown.py`, `rebuild_gta2_runtime_assets.py`, `build_vehicle_surface_layers.py`, `quest_patch/build_popout_assets.py`.  
Regeln: Full-Z nicht nur Top-Lid; Godot OBJ V-Flip `1-v`; Collision layer-sensitiv; GMP-Z nicht aufs höchste Lid projizieren; Rampen nicht ins Popout.

---

## 5. Nie wieder

- Neues Web-Spiel
- Source-ZIP überschreiben
- 18.9 Tabletop / `world_scale=10` / HeadsetBootMarker / Popout-noop
- `downtown_flat`-Swap entfernen
- Orange Shock (Arc ist blau/weiß)
- Shock als One-Shot-Hitscan **zurück** (18.5 ist `shock_arc`; Channel kommt **nach** sichtbarem Boot, dann `local_fire_down()` nie `Input.is_action_pressed("attack")`)
- Rampen in Popout-Gebäude, Gebäude flat+stereo, UI hinter Häusern
- Test-Cops, Spawn-Tank, Radio-WAVs, erfundene WIL-IDs
- `apply_shock_animation_upgrade.py` wieder mit Channel-Code aufblähen (das war 18.6+; 18.5-Version endet mit `shock_arc`)

---

## 6. CI-Reihenfolge Exact-185

1. cat part1+part2, SHA prüfen, unzip  
2. `build_popout_assets.py`  
3. `extract_enforcement_assets.py`  
4. Copy `presentation_rig.gd` + VR-board-sed (`downtown_flat`, ui_parent, ui_target, sync_popout, respawn call_local, include_filter downtown)  
5. `apply_v0618_upgrade.py`  
6. `apply_shock_animation_upgrade.py` **Stand 053bec3** + `tools/build_gta2_ped_animations.py`  
7. OpenXR Vendors 4.3.1-stable  
8. Godot import + `--export-debug "Android Quest"`

Channel/Quality/Audio-Skripte existieren unter `quest_patch/` für späteres Bisect, laufen in Exact-185 **nicht**.

---

## 7. Arbeitsstil

- Ein Checkpoint, CI grün, APK als Download, User testet Quest.  
- Schwarz vs. Bild isolieren gegen 18.5.  
- User spricht Deutsch, Produktbegriffe, keine localhost/Shell-Anweisungen an ihn.  
- GitHub-Zugriff: `bvultrex` ist Admin, `gh` push auf `main` startet CI.

Wenn der User nichts weiter sagt: Exact-185 fertigmachen, APK geben, auf Hardware-Report warten. Nicht Dächer, nicht Channel, nicht Tabletop.
