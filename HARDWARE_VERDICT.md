# Hardware verdict — v0.6.18.5 rebuild

**Date:** 2026-09-22  
**Tester:** project owner, Meta Quest (same headset as the original GPT APK)  
**Verdict:** **PASS — running build**

This is the first confirmed reproduction of the last working Quest APK
after the 0.6.18.6 black-screen line.

## What was tested

A fresh GitHub Actions rebuild of the frozen stable commit, with **no**
post-18.5 patches (no shock-channel, no GTA2 audio upgrade, no XR rewrite).

| Item | Value |
|---|---|
| Stable commit | `053bec3d92b897656e6dec7464a2dbf1e9988b23` |
| Tag | `v0.6.18.5-stable` |
| Rebuild branch | `continue-from-v0.6.18.5` / `rebuild-v0.6.18.5` |
| Rebuild run | `35761046953` |
| Rebuild artifact | `10710570092` / `ViceQuest-v0.6.18.5-Blue-ShockArc` |
| Rebuild APK SHA256 | `5bd00058de186b09d50ada48745835c830c3ae56cfd80c126fea3d57c3715bc5` |
| Original oracle SHA256 | `fb4669624f20dfefa556de3b2fdae16c2d2cea7ae6f277a7849a275955a6507d` |
| Original run | `35656574036` / artifact `10665256550` |

Native libs, OpenXR vendors and `AndroidManifest.xml` matched the oracle
byte-for-byte. Only `assets/assets.sparsepck` differed (same size, Godot
export stamp). The headset result is what counts: **the picture is back.**

## What this means

- CI can reproduce 18.5 behaviour on real Quest hardware.
- `053bec3` is the engineering baseline. Do not start from `main` 18.6–18.11.
- 18.6+ remains the black-screen line and stays experimental.
- XR presentation stays frozen: SubViewport board + UI overlay + filtered popout.

## Next version (only one change)

**v0.6.18.12 — Downtown roofs / interiors / slopes.**

Do not reintroduce shock-channel or audio until this roof pass is
hardware-good. Do not touch `presentation_rig.gd` in 18.12.
