# ViceQuest Quest Hardware Handoff

## Authoritative development line

The hardware-working Quest line is branch `continue-from-v0.6.18.5`.

Do not continue Quest work from current `main` v0.6.18.11/12/13 unless explicitly requested. That line was mistakenly used for later fixes and is not the current hardware baseline.

## Last user-confirmed running base

- APK: `ViceQuest-v0.6.18.26-Engines.apk`
- Commit: `6c7981c44d5e37747937009c604f3fe17a847cb0`
- Branch: `continue-from-v0.6.18.5`
- 18.26 fixed per-engine PCM ownership so the player's driven engine remains audible.
- Known hardware limitation: traffic/vehicle engines are not audible while the player is on foot.

## Current candidate: v0.6.18.27

- Artifact: `ViceQuest-v0.6.18.27-Engines-VehicleFixes`
- Build head: `80391181324f8da86898103afa7e5f5f7f7116a3`
- GitHub Actions run: `35897726826`
- Result: successful Quest import, APK export, and artifact upload.

### Changes layered on the 18.26 baseline

1. Nearby traffic engines remain on the existing 18.26 2D/manual Ear mixer. No AudioStreamPlayer3D and no XR audio-listener experiment.
2. Traffic selection no longer requires replicated `current_speed >= 0.35`. Active AI or occupied vehicles can be heard even if remote speed is stale or zero.
3. Traffic hearing radius raised from 34 to 46 world units and on-foot attenuation made more audible. Quest still uses only three traffic engine voices.
4. The 18.26 per-voice PCM-copy ownership fix remains intact.
5. Ported the low-restitution anti-gummyball vehicle collision behavior that tested well.
6. Ported logical Cop drivers for pursuit vehicles, Cop ejection on police-car theft, and prevention of autonomous pursuit resuming after leaving a hijacked response vehicle.
7. Ported the Agent/Cop HP persistence fix so profile sync no longer refills health every response tick.

## Hardware test priority

- On foot near moving traffic: engine loops should be audible and fade based on distance from the player.
- In a vehicle: own engine should remain stable; surrounding traffic should remain audible but quieter.
- Head-on, rear-end, side-swipe, pile-up and police ram: verify reduced gummyball bounce.
- Steal a pursuing police vehicle: Cop should eject. Exit the stolen vehicle: it must not drive away under pursuit AI.
- Damage high-level Agents: HP must not silently refill.


## Current candidate: v0.6.18.28 Pursuit / Crash / Audio (2026-09-23)

- Artifact: `ViceQuest-v0.6.18.28-Pursuit-Crash-Audio`
- Build head: `49cc640c4c0269a3ebd7c4e05885b47e57635866`
- GitHub Actions run: `35901155716`
- Result: successful 18.26->18.27->18.28 patch application, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:06c69685c535cd8c07ca72674ee76e0b2f1e42d976514326f40b6c5f585cc6e5`

### v0.6.18.28 changes

1. **Traffic engines on foot**
   - Keeps the proven 18.26 manual Ear / 2D mixer and three bounded traffic voices.
   - `_owned_loop_instance()` now accepts any imported `AudioStreamWAV` format/stereo layout and deep-copies its sample data instead of silently returning null unless the import is 16-bit mono.
   - Non-WAV streams fall back to a deep resource duplicate.
   - Nearby selection now keeps visible/active fixed cars, ambient streamed cars, AI cars and occupied cars. Hidden ambient-pool members stay silent.
   - Traffic radius is 52 world units and active cars retain an idle engine floor.

2. **Crash momentum**
   - Retains the low-restitution/no-reverse behavior that removed gummy-ball bounce.
   - Transfers a mass-weighted external impulse into the struck vehicle.
   - Adds longitudinal velocity transfer when the impact aligns with the target's heading.
   - Applies a small immediate target shove so two CharacterBodies do not appear welded together before the next physics tick.
   - Tank crush branch remains unchanged.

3. **Police sirens and lightbar**
   - Uses the original GTA2 WIL siren sample `horn_siren.wav`, pinned from commit `50fda09274ece78985fb44fb9f7fc3ea1f7a4469`.
   - Two bounded manual-Ear siren voices track the nearest active response cars.
   - Police response FX state is replicated with `_sync_police_vehicle_fx`.
   - `cop_car` and `swat_van` gain a generated flashing blue lightbar sprite.
   - The Quest elevated-vehicle mirror now clones/restores the police lightbar, so it should remain visible on raised streets/roofs.

4. **Police box-in / pull-out behavior**
   - If a pursuing police car is within 3.15 units of the player's occupied car and both cars stay nearly stopped for ~850 ms, the Cop exits the response car.
   - The response car brakes and pauses its vehicle pursuit controller for 4.5 s while lights/siren remain active.
   - The Cop becomes an active on-foot response unit and the server forces the wanted player out of their vehicle.
   - Existing logical Cop-driver mapping and hijacked-response-car behavior remain in place.

### Hardware test priority for 18.28

- On foot beside ordinary moving/AI traffic: verify at least one to three engine loops can now be heard.
- Stand beside an idling/slow active car and confirm the engine no longer disappears solely because replicated speed is zero.
- Drive into a stationary car at low, medium and high speed: target should visibly roll/slide, while neither car should pinball backward.
- Trigger wanted pursuit: police car should show flashing blue lightbar and original GTA2 siren.
- Let a police car pin the player's car nearly stationary for about one second: Cop should exit and force the player out.


## Current candidate: v0.6.18.29 Vehicle Presentation (2026-09-23)

- Artifact: `ViceQuest-v0.6.18.29-Vehicle-Presentation`
- Build head: `ff389e038fd470feae3a690260e4884224ffaad2`
- GitHub Actions run: `35903714926`
- Result: successful full 18.26 -> 18.27 -> 18.28 -> 18.29 patch chain, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:f7d9bd329053a2453d6b1c7569bc5f0425cc2c0751112db99b9abd41880abcae`

### v0.6.18.29 changes

1. **Traffic engines and sirens**
   - Keeps the proven 18.26 manual Ear/2D audio architecture and own-car engine path.
   - At build time creates three physically separate WAV files for every traffic engine family and two separate siren WAVs. Traffic/siren voices load these unique paths instead of runtime PCM/resource duplicates.
   - Traffic engines now update both on foot and while driving; the player's own car remains excluded from the traffic pool.
   - Sirens also update both on foot and while driving.
   - Police FX synchronization is now reliable.
   - Traffic radius 58 world units; siren radius 82 world units.

2. **Police exit visibility**
   - Adds reliable `_sync_cop_exit` RPC.
   - During box-in extraction the player is forced out first, then the Cop is spawned at a separate offset beside/forward of the response vehicle.
   - Cop is explicitly response-active and visible on every peer.

3. **Police lightbar**
   - No longer depends on local `stream_active` when response FX is active.
   - Larger 24x7 blue/white lightbar, no-depth-test, higher render priority.
   - Existing Quest elevated-vehicle mirroring from 18.28 remains.

4. **Collision**
   - Mass-weighted target transfer raised from 0.30 to 0.42.
   - Max transfer raised from 4.25 to 5.60, longitudinal transfer from 0.72 to 0.88 and immediate shove increased.
   - Anti-reversal / low-restitution behavior remains, so impacts should feel heavier without returning to gummy-ball bounce.

5. **Vehicle orientation / identification**
   - Confirmed backwards `swat_van.png` is rotated 180 degrees at build time.
   - Adds GTA-style vehicle-name popup at the right HUD edge for ~2.8 seconds on entry.
   - Use that displayed name to report any other backwards vehicles so their exact variants can be corrected without guessing.

### Hardware test priority for 18.29

- On foot beside normal traffic: confirm engines are audible.
- While driving: confirm own engine remains audible and nearby traffic can also be heard.
- Wanted pursuit while in vehicle: confirm original GTA2 siren is audible and police/SWAT lightbar is visible.
- Allow police to box the player in: confirm the player is pulled out AND a visible Cop appears beside the response car.
- Crash into stationary cars at medium/high speed: verify stronger displacement but no pinball reversal.
- Enter SWAT van: verify sprite now faces driving direction.
- Enter several cars and note the displayed vehicle name for any model still visually reversed.


## Current candidate: v0.6.18.31 Timecycle / Lamps (2026-09-23)

- Artifact: `ViceQuest-v0.6.18.31-Timecycle-Lamps`
- Build head: `b0e14c26e650abe04da2ee15085471bc62114b65`
- GitHub Actions run: `35906690167`
- Result: successful full patch chain through 18.31, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:94bcabbfd5038c145d0c5ec69d6f4b6500691cc1dd11ccb3e0da2b65ec22789d`

### v0.6.18.30 / 18.31 changes

1. **Traffic audio range**
   - Hardware 18.29 finally confirmed vehicle engine audio works.
   - Nearby traffic engine radius reduced from 58 to 36 world units.
   - Unique physical traffic WAV architecture from 18.29 is retained.

2. **Police blue beacon**
   - Replaces the too-subtle 24x7 roof strip with a 48x48 soft blue roof corona plus bright core.
   - No depth test, higher render priority, stronger alternating blue modulation.
   - Existing reliable police FX sync, siren audio and Quest elevated-vehicle copying remain.

3. **GTA2-inspired timecycle**
   - Full cycle currently 720 real seconds (12 minutes), starting around 17:30 for hardware testing.
   - Dusk blends from 18:00 to 20:00, full night 20:00-05:00, dawn 05:00-07:00.
   - Quest base game viewport gets a dark blue night tint without darkening the UI viewport.
   - Quest pop-out buildings, elevated peds and elevated vehicles receive matching night tint.

4. **Map lights**
   - 18.30 includes a parser for the official GTA2 GMP `LGHT` chunk (ARGB, XYZ, radius, intensity, shape/on/off).
   - The currently reconstructed source pack contains no preserved GMP/LGHT source: CI confirmed 0 original lights available.
   - 18.31 therefore generated **420** warm Downtown curb lights from the exact `downtown_exact_map.json` road/pavement topology.
   - Runtime renders only the nearest **36** lights inside **44 world units**, refreshed at a low cadence for Quest performance.
   - If a future source pack contains original LGHT data, 18.31 leaves those original lights untouched and the fallback is not generated.

### Hardware test priority for 18.31

- Confirm traffic engines now fade out sooner and do not sound like the whole city is loaded at once.
- Trigger police pursuit and confirm the larger blue roof beacon is finally obvious while siren remains audible.
- Watch the board through dusk into night; full cycle is 12 minutes and starts around 17:30.
- At night confirm warm curb/street light pools appear around nearby roads and move through the 36-light pool as the player travels.
- Check Quest performance at night, especially while driving through dense traffic and a police pursuit.
- Verify the UI stays normally bright while the world darkens.

