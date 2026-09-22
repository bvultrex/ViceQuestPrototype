# ViceQuestPrototype

Quest-Build-Repository für Vice Quest.

Aktueller Stand: **v0.6.18.10-From-185**

Letzte APK, die auf Quest 3 **wirklich lief:** `ViceQuest-v0.6.18.5-Blue-ShockArc` (Commit `053bec3`).

**Neuen Chat starten:** zuerst [`CONTINUE_PROMPT.md`](CONTINUE_PROMPT.md) lesen. Nicht ein neues Spiel bauen. Nicht den Tabletop-Fix aus 0.6.18.9 wiederholen.

GitHub Actions rekonstruiert die Source-ZIP, wendet `quest_patch/` an und exportiert die Quest-APK.

## v0.6.18.10

Stellt den hardware-erprobten Quest-Blick aus 0.6.18.5 wieder her:

- 16:9 SubViewport-Brett, `QUEST_DISPLAY_LAYER`, Gebäude-Popout
- World-Mesh auf Quest: `downtown_flat_*`
- Shock 0.6.18.7 und Audio 0.6.18.8 bleiben oben drauf

0.6.18.9 war die falsche Diagnose (Tabletop statt Brett). 0.6.18.8 war schwarz, obwohl `presentation_rig.gd` noch der 18.5-Stand war.

## v0.6.18.9

Falscher Schwarz-Fix: Tabletop `world_scale=10`, Popout tot, kein `downtown_flat`. Nicht sideloaden.

## v0.6.18.8

Original-GTA2-Downtown-Audio aus WIL.RAW / WIL.SDT (Sample-IDs aus `gta2_re` `sound_obj.cpp`):

- Explosion nutzt WIL 66 (Rocket/Shock-Car-Hit), nicht mehr pitched Gunfire
- Granate legt WIL 62 drauf, Molotov spielt WIL 65
- Electrocuted-Victim: WIL 58, mit Cooldown gegen Channel-Spam
- Wanted-Sirene: WIL 14 (Type_4 / Firetruck-Horn, derselbe Pfad wie `HandleSirenActivationSound`)
- Leise Downtown-Ambience: WIL 60 (Type_11), einmal als 2D-Loop, kein kurzer Nerv-Loop
- Radio-WAVs bleiben draußen (zu groß für Quest)

Auf Quest schwarz — XR war aber noch 18.5. Nicht sideloaden.

## v0.6.18.7

Shock Gun Qualitätspass auf der bestehenden Godot-Basis:

- Gehaltener Channel nutzt `local_fire_down()` (Quest-Trigger, Space, Maus) statt einer nicht gemappten `attack`-Action
- Line of Sight: Arc geht nicht mehr durch Gebäude
- Target-Hysterese gegen Flackern der Verzweigungen
- `shocker.wav` als Loop, kein One-Shot-Spam
- Ammo wird pro Damage-Tick verbraucht

## v0.6.18.5

Letzter bestätigter Quest-Lauf: blauer GTA2 Shock-Arc, 16:9-Brett, Popout-Gebäude, Wanted/HUD 0.6.18.
