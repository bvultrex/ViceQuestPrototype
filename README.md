# ViceQuestPrototype

Quest-Build-Repository für Vice Quest.

Aktueller Stand: **v0.6.18.9-Quest-Visible**

**Neuen Chat starten:** zuerst [`CONTINUE_PROMPT.md`](CONTINUE_PROMPT.md) lesen und vollständig einfügen. Nicht ein neues Spiel bauen.

GitHub Actions rekonstruiert die Source-ZIP, wendet `quest_patch/` an und exportiert die Quest-APK.

## v0.6.18.9

Quest 3 zeigte ein komplett schwarzes Bild: die XR-Kamera sah nur Layer 20 (SubViewport-Brett), und diese Textur bleibt auf Quest/GL Compatibility schwarz.

Fix: wieder der hardware-erprobte Tabletop-Pfad aus v0.6.17.0.

- XR-Kamera sieht die echte Downtown, `world_scale = 10`
- Kein Layer-20-Only, keine Abhängigkeit von SubViewport-Textur
- Gebäude bleiben im World-Mesh (`downtown_visual`), nicht nur im Popout
- HUD/Boot wieder im Haupt-Viewport, damit OpenXR 2D compositen kann
- Kurzer unshaded Marker vor dem Headset, bis das Spiel startet

Shock 0.6.18.7 und Audio 0.6.18.8 bleiben.

## v0.6.18.8

Original-GTA2-Downtown-Audio aus WIL.RAW / WIL.SDT (Sample-IDs aus `gta2_re` `sound_obj.cpp`):

- Explosion nutzt WIL 66 (Rocket/Shock-Car-Hit), nicht mehr pitched Gunfire
- Granate legt WIL 62 drauf, Molotov spielt WIL 65
- Electrocuted-Victim: WIL 58, mit Cooldown gegen Channel-Spam
- Wanted-Sirene: WIL 14 (Type_4 / Firetruck-Horn, derselbe Pfad wie `HandleSirenActivationSound`)
- Leise Downtown-Ambience: WIL 60 (Type_11), einmal als 2D-Loop, kein kurzer Nerv-Loop
- Radio-WAVs bleiben draußen (zu groß für Quest)

## v0.6.18.7

Shock Gun Qualitätspass auf der bestehenden Godot-Basis:

- Gehaltener Channel nutzt `local_fire_down()` (Quest-Trigger, Space, Maus) statt einer nicht gemappten `attack`-Action
- Line of Sight: Arc geht nicht mehr durch Gebäude
- Target-Hysterese gegen Flackern der Verzweigungen
- `shocker.wav` als Loop, kein One-Shot-Spam
- Ammo wird pro Damage-Tick verbraucht
