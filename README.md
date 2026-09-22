# ViceQuestPrototype

Quest-Build-Repository für Vice Quest.

Aktueller Stand: **v0.6.18.7-Shock-LOS**

GitHub Actions rekonstruiert die Source-ZIP, wendet `quest_patch/` an und exportiert die Quest-APK.

## v0.6.18.7

Shock Gun Qualitätspass auf der bestehenden Godot-Basis:

- Gehaltener Channel nutzt `local_fire_down()` (Quest-Trigger, Space, Maus) statt einer nicht gemappten `attack`-Action
- Line of Sight: Arc geht nicht mehr durch Gebäude
- Target-Hysterese gegen Flackern der Verzweigungen
- `shocker.wav` als Loop, kein One-Shot-Spam
- Ammo wird pro Damage-Tick verbraucht
