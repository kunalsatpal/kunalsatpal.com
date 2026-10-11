# Universe scroll smoothness plan

Prepared 10 October 2026 against commit `ff6079f`. This is a proposal; no website implementation changes are part of this review.

Execution update, 11 October: preview caching, clock/resize stability, the PNG hero logo, and browser-managed scene flights are now implemented. See [universe-scroll-update.md](./universe-scroll-update.md). The latest user instruction replaces further repeated benchmarking with a focused functional check followed by manual desktop Chrome verification.

The goal is smoother scrolling while retaining the current artwork, textures, sphere projection, lighting, shaders, blur, depth, card entrances, moon orbits, realistic/cartoon themes, and navigation transitions. Preserve existing single-page movement during the first optimization stages. Treat any change to gesture behavior or easing as a separate decision.

## What comparable experiences do

| Reference | Documented approach | Application here |
| --- | --- | --- |
| [14islands: WebGL lens refraction](https://tympanus.net/codrops/2023/10/10/progressively-enhanced-webgl-lens-refraction/) and [scroll-rig source/documentation](https://github.com/14islands/r3f-scroll-rig) | A shared canvas; scroll and DOM/WebGL positions synchronized; cached geometry with observers; rendering requested when necessary. | Keep cached measurements and visibility suspension. Investigate the remaining repeated geometry reads and independent effect scheduling before considering a renderer change. |
| [Codrops: Shaders on Scroll](https://tympanus.net/codrops/2021/07/13/rock-the-stage-with-a-smooth-webgl-shader-transformation-on-scroll/) | Scroll progress drives GPU shader uniforms; overlapping tweens are overwritten; rendering is scheduled around scroll updates. | Preserve one authoritative journey position, avoid competing movement, and consider a GPU equivalent only for a measured paint bottleneck. |
| [Lenis documentation](https://github.com/darkroomengineering/lenis) | Explicit animation-loop integration; separate wheel/touch settings; documented Safari and low-power limitations. | Lenis is already installed. Audit our controller and timing rather than assuming another scrolling library fixes rendering cost. |

These are documented implementation patterns, not a comparative device performance test. Some references lower pixel density or disable mobile WebGL. Those shortcuts are outside this plan's visual-preservation goal. Adopting React, Three.js, or GSAP wholesale is not required to apply these techniques.

## Evidence in this repository

- The previous [performance report](./universe-performance.md) measured roughly 26% less main-thread work over a scripted full route, but p95 JavaScript frame intervals remained around 33.4 ms. That report predates the latest navigation changes and used headless Chrome on the host Mac, not a phone.
- `scripts/benchmark-universe.py:21` measures repeated scripted `scrollTo()` calls. It does not reproduce wheel/swipe handling, distant destination-only jumps, or input reversals. Keep it as a rendering stress test, and add interaction-specific profiling.
- `universe.html:1304` clears preview sizing, reads geometry, writes sizing, reads geometry again, and then writes position. `universe.html:1967` repeats this while a preview is active. This is a concrete read/write pattern to eliminate; its contribution to general scroll jitter still needs attribution.
- `universe.html:1878` changes a scene-sized blur during every transition. `universe.html:146` permanently declares layer hints for every scene. GPU/raster cost and layer memory are suspects, not yet established as the dominant bottleneck.
- `universe.html:1942` updates realistic planet texture background positions each frame under the SVG displacement filter at line 205. This preserves the current sphere rendering but requires repeated paint work. The existing report documents a failed texture-translation experiment; do not repeat that approach without new evidence.
- The stage uses `100svh`, the journey uses `vh`, and route calculations use `innerHeight`. Resize measurement calls `sceneSnap.layoutChanged()`, which can restart active navigation. Mobile toolbar height changes are a plausible source of movement discontinuity; this must be reproduced on a phone.
- `universe.html:1820` caps elapsed time before advancing Lenis, while cards, textures, and jump arrival use the real frame timestamp. Under long stalls, the layers may advance differently. Verify before changing clocks.
- Wheel navigation starts a transition of at least 1.05 seconds, then ignores another gesture for 320 ms. Touch navigation begins on release. This can feel unresponsive independently of frame drops. These behaviors are deliberate pagination rules; keep changes to them separate from rendering optimizations.

Already completed optimizations should be retained: offline texture generation, deferred assets, serialized shader initialization and shared device, hidden-scene animation suspension, cached measurements, guarded style writes, and destination-only rendering for distant jumps.

### Exploratory checks in this review

Short local headless-Chrome checks of desktop wheel transitions in both themes and an emulated mobile swipe produced p95 JavaScript frame intervals of 16.7–16.8 ms. This did not establish a reproduction of the user's ongoing scroll jitter. Each four-second sample included idle time after the transition, and these callback intervals are not a measurement of all presented GPU frames. Physical-device and transition-only traces are still needed.

Two repeated four-second GoJek samples compared a stationary planet with a focused, open case-study preview. Layout time rose from 0.23–0.24 ms without the preview to 33.0–39.7 ms with it. Style recalculation rose from 42.9–44.2 ms to 59.4–69.8 ms. Both sky shaders were initialized, running, and ready in all four samples. The preview-open state was checked explicitly. These exploratory windows include initial opening work and do not attribute every millisecond to the clamp function; they support prioritizing that code without proving it causes all scroll jitter. Invalid trials where the headless document was unfocused and the preview did not open were excluded.

## Execution order and review checkpoints

### 1. Establish an interaction and visual baseline

Record real wheel, trackpad, and swipe journeys, adjacent navigation, forward/backward distant jumps, rapid reversal, an open moon preview, immediate scrolling during a cold load, and a case-study return. Run both themes on desktop Chrome/Safari and physical iPhone/Android, with representative 60 Hz and higher-refresh displays where available. Use emulation and CPU throttling to supplement physical-device tests.

Capture presented/dropped frames, JavaScript frame intervals, input-to-first-motion, time until the next gesture is accepted, long animation frames/tasks, forced layout attribution, paint/raster work, shader readiness, and layer memory. Record the browser, device, display rate, power mode, and cold/warm state. Repeat each representative route at least three times.

Capture matching still frames and short motion recordings. The visual baseline must include intermediate transition frames, blur/glow edges, orbit positions, text/card arrival, and cartoon styling. This prevents a faster but visually weaker implementation from being accepted.

Checkpoint: an attributed list of the worst interactions and which work exceeds the frame budget. Do not choose a large renderer rewrite before this result.

### 2. Remove repeated preview layout work

Cache each preview's natural dimensions; invalidate on content/image/font changes and viewport resize. Compute viewport limits once per invalidation. Reuse the last applied width, height limit, and translation rather than clearing and restoring them every frame. Update positioning when its anchor, ancestor transform/scene scale, or visual viewport offsets change, with geometry reads grouped before writes. Natural dimensions can remain cached while screen-space bounds change during arrival/exit. Keep viewport bounds, keyboard focus, and all preview styling.

Checkpoint: no continuous sizing reflow from a stationary preview; preview bounds remain correct at narrow widths and during arrival/exit. Compare frame and layout cost against stage 1, and commit this independently.

### 3. Stabilize viewport geometry and motion clocks if traces confirm discontinuities

Use a consistent viewport measurement for the stage and route. Distinguish browser toolbar changes from width/orientation/layout changes. Preserve the intended target scene and current progress through a meaningful resize; avoid restarting the whole transition repeatedly during toolbar animation. Preview limits must still respond to `visualViewport` resize/scroll, even if a toolbar change does not trigger route remeasurement.

Compare scrolling, orbit, and arrival clocks during stalls and idle wakeups. If they diverge visibly, define a consistent active-animation clock with explicit suspension/resume handling. Do not merely change easing or add another smoothing pass.

Checkpoint: no jump/restart on mobile toolbar collapse or expansion, orientation remains correct, background restoration is stable, and ordinary single-page motion matches the baseline.

### 4. Reduce layer and paint work while retaining the effects

Profile layers and rasterization with current blur/glow intact. Prototype restricting `will-change` to the visible and approaching scenes, promoting them before use and releasing obsolete hints afterward. Avoid blanket paint containment: it can clip moon previews, glows, and shadows.

If scene blur dominates, investigate separating stable artwork from changing compositing effects while preserving the same blur envelope and depth. Keep only the scenes needed for the visible transition active. Measure a prototype before retaining it; layer promotion and caching are not automatically faster on every GPU.

Checkpoint: unchanged visual references and motion, lower paint/raster or layer cost, and fewer missed frame deadlines across repeated runs. Revert prototypes that fail either the performance or visual gate.

### 5. Replace a costly rendering primitive only if it remains dominant

If realistic sphere repainting is still the limiting work, prototype an equivalent GPU rendering path for the existing textures, displacement projection, cloud/light layers, and shading. Reuse resources and schedule work without duplicating render passes. Validate full texture detail and resolution; retain the existing path until equivalence and device support are established.

This is the highest-cost, highest-risk step. It may be unnecessary after stages 2–4. A full-site framework migration is not proposed.

Checkpoint: fixed-time comparisons of sphere projection, texture seams, lighting, clouds, atmosphere, and rotation; full-route performance improvement on the devices that previously struggled.

### 6. Review interaction feel separately, then release

If frame delivery improves but scrolling still feels delayed, review the 1.05-second transition and 320 ms lock. A candidate is to accept a new deliberate gesture once the destination is visually settled while still consuming the original gesture's momentum. Another is explicit reversal handling. Keep the current visual path and inertia; present any change to single-page gesture behavior separately before implementing it.

Run cold-load, both-theme, single/multi-page, hover-bound, case-study open/back, reduced-motion, browser-history, and repeated-navigation checks. Commit each validated implementation checkpoint. Push the final fix after the planned changes pass visual and performance review, consistent with the user's existing publishing instruction.

## Acceptance gates

- Preserve the current composition, effects, image detail, fonts, projection, motion path, and transitions. Match deterministic screenshots; compare time-varying shaders separately at matched animation times and in recordings.
- On the chosen 60 Hz reference devices, aim for p95 presented-frame intervals near 16.7 ms and fewer than 1% of warm-transition frames exceeding 33.3 ms. On higher-refresh devices, evaluate against their actual refresh interval. These are targets to validate, not current guarantees.
- Report slowest interactions and repeated-run ranges, not just average FPS or aggregate CPU savings. Warm transition windows must be measured separately from idle time.
- No recurring preview sizing reflow, visible blank frames, disappearing text/cards, clipped speed effects, or resize-induced motion restarts.
- Preserve single-page interaction behavior unless the optional stage 6 change is explicitly selected.

## Sources for validation

Google's [animation performance guidance](https://web.dev/articles/animations-and-performance) explains why transform/opacity are preferred and excessive `will-change` can waste resources. Its [layout-thrashing guidance](https://web.dev/articles/avoid-large-complex-layouts-and-layout-thrashing) supports batching reads before writes. Its [rendering pipeline guide](https://web.dev/articles/rendering-performance) explains why JavaScript CPU improvements alone do not prove smooth frame presentation.
