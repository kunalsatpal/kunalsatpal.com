# Sky rendering update — 11 October 2026

The Real theme retains its original Aurora and FloatingParticles shaders, two canvases, particle count, color settings, CSS saturation/screen blending, resolution, animation rate, cursor response, and parallax transforms. Planet and card rendering are unchanged by this checkpoint.

## Change

The sky canvases extend beyond the viewport and enlarge further along the journey. The renderer previously shaded the complete canvas even though the stage clips most of its enlarged edges. `site/js/universe-sky-culling.js` applies a WebGPU scissor rectangle to each final canvas pass, skipping fragments outside the stage's visible source region. This follows the GPU's [scissor rasterization behavior](https://developer.mozilla.org/en-US/docs/Web/API/GPURenderPassEncoder/setScissorRect).

Coordinates, texture dimensions, uniforms, and shader formulas remain identical. Bounds are computed from the existing layer transforms and cached stage dimensions, with outward rounding and two source pixels of padding for edge sampling. There are no per-frame DOM geometry reads. Intermediate textures and particle compute/simulation passes remain complete, preserving state as particles move into view.

At the last scene in a 1440 × 900, DPR 2 Chrome check, the final Aurora pass drew about 55% of its canvas and the star pass about 34%. This is a reduction in the fragment area of those final passes, **not** a claim that total GPU time, total frame time, or dropped frames fell by those percentages. The original 2880 × 1800 canvas dimensions remained.

First-load camera motion and case-study camera zoom use full draws. A camera attribute change disables clipping through the transition; resize invalidates bounds until the next measurement. Both sky effects retain their existing Toon, overview, pagehide and device-loss lifecycle. Unsupported instance adapters or an unavailable shared device retain full rendering.

The adapter wraps only this controller's GPU device, canvas contexts, texture view creation and command encoders. It does not modify WebGPU prototypes or the vendor bundle. Keeping this adapter separate allows vendor upgrades to be checked against a small integration surface; unrecognized attachments use full draws.

## Verification

- An actual GPU texture readback compared the original full-detail Aurora at a fixed time with clipping disabled and enabled. All visible source pixels matched exactly; 1,723,724 invisible pixels changed because they were no longer shaded. Ordinary canvas snapshots returned empty images in this headless setup, so the check requires nonempty GPU readback and actual outside-region differences.
- Live geometry checks verified that both scissors cover the visible viewport with only the edge sampling margin, including quick Hero return, a distant jump, and height resize.
- Focused navigation checks passed for backward scrolling, cancellation, Toon/theme changes, overview restoration, mobile pagination, reduced motion and hard-refresh entrance. After a startup timing race in the test's reduced-motion entry, only the remaining checks were resumed after waiting for initial scene settlement. Passed routes were not repeatedly run.
- Direct camera-dive/return checks confirmed clipping stays off during zoom and resumes after it settles. Controller tests cover native-object fallbacks, intermediate pass isolation, shader reuse, initialization races and shared-device recovery.

Run the focused verification with the isolated local server/Chrome setup in [universe-performance.md](./universe-performance.md):

```sh
/tmp/universe-tools/bin/python scripts/check-universe-motion.py --check-sky
```

No FPS benchmark campaign was run. Manual desktop Chrome acceptance remains forward/backward pagination and a quick return to the landing view, checking both sky appearance and motion continuity.
