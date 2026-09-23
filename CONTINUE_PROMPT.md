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
