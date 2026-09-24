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


## Current candidate: v0.6.18.32 Visible Lights (2026-09-23)

- Artifact: `ViceQuest-v0.6.18.32-Visible-Lights`
- Build head: `fddbf87a191e13eaab53515dc61c16e86cb54816`
- GitHub Actions run: `35907995040`
- Result: successful full patch chain through 18.32, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:ae948cdd4cdc68496e8e67f226631ce80be5ee37e0a86d31d6004a1ad7bc6ba4`

### v0.6.18.32 changes

1. **Street-light coordinate fix**
   - 18.31 hardware showed day/night tint and police beacon but no curb/street glows.
   - Root cause candidate: 18.30 converted map-block lights with a hard-coded 2.8 world-units-per-block value, while the actual runtime already uses `DOWNTOWN_DATA.TILE_SIZE`.
   - 18.32 converts light X/Z using `DOWNTOWN_DATA.TILE_SIZE` directly.
   - Each selected light is snapped to the actual nearby surface with `sample_surface_height()`.
   - Map-light sprites explicitly use visual layer 1, no depth test and a higher render priority.
   - Warm corona texture is stronger/larger than 18.31.

2. **Vehicle headlights / tail lights**
   - Adds a bounded nearest-vehicle light pool: maximum 18 vehicles inside 31 world units.
   - Uses shared textures, not one texture allocation per vehicle.
   - Each active vehicle receives two warm headlight glows, a short forward road-light beam and two red tail-light glows at night.
   - Light placement follows the vehicle's actual `get_forward_vector()` and `get_side_vector()`, so it is independent of sprite orientation.
   - Vans/trucks/SWAT use a slightly larger longitudinal/width offset.
   - Tank keeps front/tail glows but no headlight road beam.
   - All vehicle-light sprites are unshaded/no-depth-test and render on gameplay layer 1.

### Hardware test priority for 18.32

- Let the cycle reach night and confirm warm curb/street coronas are now visible beside roads.
- Enter/approach ordinary traffic at night and confirm twin warm headlights plus red tail lights.
- Watch moving traffic to verify the forward light beam follows driving direction instead of sprite orientation.
- Verify the already-working police blue beacon and siren still work.
- Check Quest performance in dense night traffic; vehicle lights are capped at 18 nearby vehicles and map lights at 36 nearby lights.
- If a light appears on the wrong side of a vehicle, note the displayed vehicle name from the 18.29 HUD popup.


## Current candidate: v0.6.18.33 Light / Audio Cleanup (2026-09-23)

- Artifact: `ViceQuest-v0.6.18.33-Light-Audio-Cleanup`
- Build head: `8f123282392e89bc9b1fbdf3f5bffd70c25f35f4`
- GitHub Actions run: `35910090760`
- Result: successful full patch chain through 18.33, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:eb6d474e608923f22a03f7ee91aab0028f7f610f00c380ddeb89ce7a313ad4be`

### Hardware feedback entering 18.33

- 18.32 confirmed the day/night lighting system and vehicle lighting are visible.
- Lighting should be somewhat stronger.
- Some orphan/ghost vehicle lights remained on the road after traffic vehicles despawned/recycled.
- At spawn, nearby traffic engines briefly sounded heavily doubled/chorused before settling.
- Reverse driving produced a trail of fading skull/blob decals because reverse throttle was misread as braking.
- Train work is now the next planned major gameplay block after this cleanup.

### v0.6.18.33 changes

1. **Stronger lighting**
   - Headlight glow sprites increased from 0.026 to 0.032 pixel size.
   - Tail-light glow sprites increased from 0.022 to 0.027.
   - Forward road beam increased from 0.055 to 0.070.
   - Head/tail alpha reaches full night intensity and beam alpha is increased.
   - Warm curb/street-light corona size and opacity are both increased.

2. **Ghost vehicle-light cleanup**
   - Ambient pooled traffic now owns lights only while actually `stream_active` (or actively occupied).
   - A stale `ai_controlled=true` flag can no longer keep a recycled ambient vehicle illuminated.
   - Hidden/non-board vehicles are rejected unless they are occupied or have active police FX.
   - Light holders explicitly hide every child Sprite3D when released from the pool.

3. **Spawn engine de-chorusing**
   - Traffic engine candidates are ranked by distance and same-engine vehicles closer than 4.8 world units are collapsed to one audible voice.
   - Newly assigned traffic voices start around -32 dB and ramp toward target volume instead of appearing at full volume in one frame.
   - Each traffic voice receives a deterministic playback phase offset based on vehicle ID and voice index.
   - Loop restarts preserve that phase offset, so identical engine samples do not keep snapping back into synchronization.
   - The proven 18.29 unique physical WAV-per-voice architecture remains intact.

4. **Reverse skid / skull-coin fix**
   - `play_skid_mark()` now receives signed vehicle speed instead of `absf(current_speed)`.
   - Reverse throttle while already moving backward is propulsion, not braking.
   - A brake decal is generated only when throttle opposes actual travel direction.
   - Existing lateral sliding/skid streak behavior remains.
   - Brake-blob lifetime is also reduced from 6.5 s to 4.2 s.

### Hardware test priority for 18.33

- At spawn, listen for the previous three-engine chorus/phasing. It should fade in cleanly and clustered same-engine cars should no longer stack loudly.
- Drive around until ambient traffic recycles/despawns. No headlight/taillight/beam should remain without a vehicle.
- Let night reach full darkness and compare curb, headlight, beam and taillight intensity to 18.32.
- Reverse normally for several seconds. No fading skull/blob trail should be created.
- Brake while moving forward and while moving backward with opposite input. Real brake/skid marks should still appear.

## Next major block: Train update

After 18.33 hardware validation, the next dedicated development pass should be the Downtown train system. Treat it as a feature block rather than a hotfix. Scope should include:

- reconstruct/verify the Downtown rail path and station stops,
- train consist movement and carriage spacing,
- proper stop/dwell/depart cycle,
- doors and passenger entry/exit,
- player boarding and leaving at stations,
- train collision/impact behavior,
- rail/train audio,
- Quest pop-out/elevated presentation,
- network authority/synchronization,
- performance limits and despawn/recycle behavior if the train leaves the active area.

Do not mix the train implementation into unrelated lighting/audio micro-fixes unless explicitly requested.


## Current candidate: v0.6.18.34 Train Core (2026-09-23)

- Artifact: `ViceQuest-v0.6.18.34-Train-Core`
- Build head: `4fabb3a2c3cba24033de291cfe312d70188f7025`
- GitHub Actions run: `35915952029`
- Result: successful full patch chain through 18.34, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:2319eb4ba858c18ec155814fb3f88b42d4b515c99b6e5d009ca54a0c64e10c0b`

### Original GTA2 train findings used for 18.34

- GTA2 railway blocks are FIELD blocks carrying green direction arrows in the low nibble.
- Green arrow direction bits: left bit0, right bit1, up bit2, down bit3.
- Original car models: TRAIN=59, TRAINCAB=60, TRAINFB=61, boxcar=6.
- Downtown open mission source contains `SET_STATION_INFO (trak02platform, 3, 0, 0)` and `SET_STATION_INFO (trak11platform, 3, 0, 0)`, so this pass builds up to two lines with a cab plus three passenger cars.
- Original station metadata distinguishes platform, entry, exit and stop-point zones; station service is cyclic.

### Build-time reconstruction result

CI reconstructed the actual Downtown railway directly from `downtown_exact_map.json`:

- **1360 railway cells**
- line 0: **816 route points**
- line 1: **544 route points**
- **5 station stops per line**
- all four original train sprite types were found in `wil.sty`, each with one base sprite:
  - train_passenger / TRAIN
  - train_cab / TRAINCAB
  - train_freight / TRAINFB
  - train_boxcar / boxcar

### v0.6.18.34 runtime features

1. **Two Downtown train services**
   - Up to two reconstructed railway lines.
   - Each consist is one original GTA2 TRAINCAB sprite plus three original passenger TRAIN sprites.
   - Carriages follow the same route with fixed physical spacing instead of being one stretched sprite.

2. **Station service**
   - Route stop points are inferred from preserved Downtown platform tiles near the railway graph.
   - Five operational stop points were recovered on each reconstructed line.
   - Trains brake into stops, dwell for ~4.6 seconds, then accelerate away toward the next cyclic stop.

3. **Networking**
   - Server owns train progress/speed/dwell state.
   - Lightweight unreliable state sync is sent about every 0.22 seconds.
   - Clients continue/interpolate route progress between syncs.

4. **Train collision interaction**
   - Moving train cars check nearby gameplay vehicles.
   - Vehicles are pushed away and receive substantial train impact damage with a short per-train/vehicle cooldown.
   - Player-vs-train pedestrian damage/knockdown is not yet wired and should be handled in the boarding/gameplay follow-up.

5. **Train audio**
   - Manual distance-attenuated train rumble and wheel-clack loops, following the same non-3D-audio philosophy as the proven Quest mix.
   - Door/station transition cue when the train changes stopped/door state.
   - Audio is bounded by distance and one pair of loop players per train.

6. **Quest presentation**
   - Ground-level trains render in the gameplay viewport.
   - Elevated train cars are cloned into the existing Quest pop-out layer so elevated rail/station segments can rise out of the tabletop.

7. **Skull-coin skid cleanup**
   - The incorrectly identified `skid_blob` (actually from the flipping skull/coin sequence) is no longer used by `play_skid_mark()`.
   - Straight braking now uses the actual dual streak skid texture only.

### Hardware test priority for 18.34

- Locate both active train services and verify they stay on rails through curves/slopes.
- Confirm consist order and spacing: cab + 3 passenger cars.
- Follow a train through multiple stops: brake -> stop -> ~4.6 s dwell -> depart.
- Verify the five inferred stops per line visually line up with stations/platforms rather than random track cells.
- Listen for train rumble/clack approaching and fading with distance.
- Check elevated/station rail segments on Quest for correct pop-out treatment.
- Put a vehicle in the train's path and verify train impact/push/damage.
- Brake/reverse a normal car and verify the flipping skull/coin sprite never appears as a skid mark.

### Next train follow-up after hardware validation

Once 18.34 route/visual behavior is validated, continue with a dedicated train interaction pass:
- player boarding/exiting at stopped stations,
- original-style train hijacking/driver control where appropriate,
- passenger NPC enter/leave behavior,
- real door-state visuals if additional train sprite frames/assets are identified,
- pedestrian impact/knockdown/death rules,
- exact original train sample-bank extraction to replace the temporary synthesized rumble/clack if feasible.


## Current candidate: v0.6.18.35 Train Recovery (2026-09-24)

- Artifact: `ViceQuest-v0.6.18.35-Train-Recovery`
- Build head: `59ebe1009e963cb3e2ec2b8fb1493b868467a284`
- GitHub Actions run: `36014682235`
- Result: successful full patch chain through 18.35, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:9f75db77f9dc9927601390775e528ec2e3c623c58660e6397d93c73e05b70f2d`

### Important hardware regression / recovery

- **v0.6.18.34 is NOT a valid hardware baseline.**
- Hardware result for 18.34: Quest app remained black from startup and produced no sound.
- Last confirmed hardware-good baseline before train work remains **v0.6.18.33**.
- Audit found the 18.34 train startup ran synchronously inside the critical main/XR startup path and referenced `DOWNTOWN_DATA.HEIGHT_UNIT`, which is not part of the previously proven Downtown runtime contract.
- The first 18.35 CI attempt intentionally failed because a guard detected another remaining `DOWNTOWN_DATA.HEIGHT_UNIT` reference after the full generated patch chain.
- Final 18.35 normalizes every remaining `DOWNTOWN_DATA.HEIGHT_UNIT` occurrence in generated `main.gd` to the established vertical scale `0.60`.

### v0.6.18.35 recovery changes

1. **Deferred train boot**
   - Main game/XR/audio startup no longer calls `_build_train_system()` synchronously.
   - It schedules `_start_train_system_after_boot()` and waits three normal process frames before building trains.
   - This keeps optional public transport out of the critical Quest startup path.

2. **Safe Downtown height contract**
   - Train configure call uses `DOWNTOWN_DATA.TILE_SIZE` plus explicit `0.60` vertical scale.
   - CI asserts that no `DOWNTOWN_DATA.HEIGHT_UNIT` reference remains.

3. **Train runtime fail-safe**
   - Train system now has `_configured=false` until routes and trains are successfully constructed.
   - If no valid lines/trains are created, configure returns with warnings and train physics remains inert.
   - `_physics_process()` exits immediately while not configured, so a failed train configuration cannot run a broken per-frame system.

4. **Reduced startup-validation workload**
   - Train/vehicle impact scanning is throttled to 10 Hz rather than every physics frame for this recovery candidate.

### Hardware test priority for 18.35

1. **First priority: verify the app boots normally with picture and sound.**
2. If boot succeeds, confirm the pre-train 18.33 systems still work: traffic sound, lighting, vehicles and input.
3. Then locate trains and verify whether the 18.34 route/visual core appears.
4. If the game boots but no train appears, that is an acceptable recovery result and indicates the deferred train configure hit a guarded runtime problem; preserve the stable boot and debug train construction next.
5. Do not treat 18.35 as hardware-good until Quest startup is explicitly confirmed.


## Current recovery candidate: v0.6.18.36 Recovery-18.33 (2026-09-24)

- Artifact: `ViceQuest-v0.6.18.36-Recovery-18.33`
- Build head: `9d98e7bfacc8c8a4192879a0a04b68e570e43bf2`
- GitHub Actions run: `36024937685`
- Result: successful 18.33 gameplay patch chain + isolated real-skid fix, clean audio-manager normalization, runtime smoke diagnostic, Godot 4.5.1 import, Quest APK export and artifact upload.
- Artifact digest: `sha256:3c65b518e75b81320cd57d8b02aeca803d1e32c58c38199424eb988daa459fe5`

### Hardware regression history

- **18.33 is the last hardware-confirmed working gameplay baseline.**
- 18.34 Train Core booted to black screen with no sound on Quest hardware.
- 18.35 Train Recovery also booted to black screen with no sound.
- Therefore 18.34/18.35 must NOT be used as a stable baseline.
- 18.36 deliberately removes all 18.34/18.35 train runtime/init/popout hooks from the build pipeline and returns generated runtime code to the 18.33 line.
- Train assets/research/route reconstruction patches remain in the repository for later controlled reintroduction, but they are not applied by 18.36.

### Important clean-build issue discovered

A new direct Godot parser diagnostic found a real generated-source problem independent of the train system:

`res://scripts/audio_manager.gd:298` reported:
`Parse Error: Used space character for indentation instead of tab as used before in the file.`

The historical audio patch chain had inserted several 4-space-indented blocks into a tab-indented GDScript file. Older artifacts could appear to work if an imported script cache masked the clean parse, but a later clean build can expose it and prevent `main.gd` from preloading `ViceQuestAudioManager`.

18.36 now runs `apply_v061836_audio_indent_fix.py` after the full 18.33 patch chain:
- converts mixed leading block indentation in generated `audio_manager.gd` to the project tab convention,
- CI reported **213 normalized lines**,
- the direct `audio_manager.gd --check-only` parser diagnostic no longer produced the indentation error,
- the following runtime smoke diagnostic produced no GDScript parse/runtime errors,
- Quest Android export then completed successfully.

Headless CI still has no physical OpenXR runtime/HMD; OpenXR loader warnings in that environment are expected and are not equivalent to Quest hardware failure.

### Isolated skid-sprite fix retained

18.36 applies `apply_v061836_skid_sprite_fix.py` independently of the train patch:
- removes the misidentified `skid_blob` / flipping skull-coin sprite from `play_skid_mark()`,
- straight braking uses the real dual `skid` streak texture,
- no train code is required for this fix.

### Immediate hardware validation

The only priority for 18.36 is startup recovery:
1. Install `ViceQuest-v0.6.18.36-Recovery-18.33`.
2. Confirm the app boots into the normal Quest tabletop instead of a black screen.
3. Confirm normal game audio returns.
4. Briefly confirm the established 18.33 systems still exist: traffic engines, police siren/blue beacon, day/night lighting and vehicle lights.
5. Reverse/brake once and confirm the flipping skull-coin sprite is no longer used as a skid mark.

### Train reintroduction plan after 18.36 hardware confirmation

Do NOT restore the full 18.34 runtime at once. Reintroduce the train in isolated layers:
1. static original TRAINCAB + three TRAIN sprites on one known rail segment, no movement/audio/network/collision/popout;
2. hardware boot validation;
3. route movement only;
4. station stop/dwell logic;
5. second line / second consist;
6. audio;
7. Quest elevated popout;
8. collisions;
9. multiplayer synchronization;
10. boarding/hijacking/passenger behavior.

This staged approach must preserve an always-known-good Quest boot checkpoint after every layer.

