# Universe flight rendering update — 11 October 2026

The desktop Chrome report still showed backward frame drops after the earlier geometry and clock fixes. Repeated JavaScript callback measurements did not establish smooth presented frames. This checkpoint changes the transition renderer, with manual Chrome verification requested by the user instead of another benchmark campaign.

## Changes

- `site/js/universe-motion.js` prepares scene scale, opacity, blur, and floating content depth as Web Animations keyframes. The existing quartic easing, depth formulas, timings, and one-view-per-gesture controller remain. Chrome advances the scene flight without rewriting those inline styles each JavaScript frame.
- Adjacent flights prepare the departure and destination, including a partially visible neighbor when interrupted. Distant jumps animate only their selected destination, retaining the 240 ms preparation and speed-line tail.
- After manual feedback, multi-page speed lines now fade during the first half of the arrival. The existing tail retains its cleanup/gesture timing while the lines stay invisible, so full-speed streaks no longer linger over the settled destination. Single-page movement is unchanged by this follow-up.
- Layer hints apply to active/prepared scenes, rather than all nine scenes. Prepared layers retain their hint through the 320 ms momentum lock. Their CSS/SMIL children are ready before they appear.
- Following the remaining stutter report, scene transform/opacity and blur use separate animation effects. Non-hero blur applies to the content wrapper instead of the full viewport; hero blur retains the original bounds so it still covers its surrounding cards. The depth, easing, and blur amounts stay the same, and Toon travel suppresses both blur targets. This reduces filter surface bounds and allows movement to be scheduled independently from filtering; it is not a guarantee of GPU compositing on every device.
- SVG playback synchronization now runs only when visibility, suspension, or theme state changes, avoiding repeated ancestor checks for all scene SVGs during a flight.
- Cancellation synchronizes an already-presented flight before handing it back to the renderer. A cancellation before the first frame holds the original position. Completion applies the final pose before removing animation effects, avoiding an invisible handoff frame.
- Lenis now handles programmatic movement only. `sceneSnap` owns raw wheel/swipe pagination; a competing Lenis wheel tween cannot start. Resize, overview suspension, reduced motion, and the original Toon travel CSS remain supported.
- Moon previews keep tracking viewport bounds while their ancestor moves through a browser animation.
- The landing logo is the 46 px static metallic PNG captured from the original shader. Its parent retains a depth/fade entrance. Saved moon history suppresses that entrance only on Back/Forward restoration, so hard refresh at the landing URL plays the headline and logo animations again.

Planet textures, SVG spherical displacement, lighting, orbit motion, sky shader definitions, resolution, and particle counts remain at their existing quality. A translated texture strip was reviewed but retained only as a temporary proposal: its filtered parent can still require painting, and an earlier version of this experiment did not improve performance.

## Validation and next check

A focused functional pass checked backward wheel movement, actual browser animation versus unchanged inline scene transforms, exact landing/completion, quick Hero retargeting, logo sizing, immediate cancellation, Toon travel/theme changes, resize, overview restoration, a mobile swipe, reduced motion, and hard refresh with saved moon state. Checks resumed at the affected step after fixing the competing wheel handler and correcting the test's early overview-resume assertion; passed routes were not repeatedly benchmarked. No uncaught browser errors occurred in the final remaining checks.

Earlier committed checkpoints passed preview/startup/stability checks, including 30 startup checks at `5f3782e`. Those historical results are not a claim that every prior suite was rerun against this renderer. No new FPS or GPU presentation claim is made here.

The split-filter follow-up passed all 23 checks in one functional run, with no uncaught browser errors, including an assertion that movement has no filter keyframes, blur targets the smaller inner wrapper, and both targets remain crisp during Toon travel. No repeated scroll performance benchmark was run; smoothness still needs the manual desktop Chrome check below.

For one functional pass, use the isolated Chrome/server setup in [universe-performance.md](./universe-performance.md), then run `scripts/check-universe-motion.py`. Existing performance tooling includes trusted quick-Hero returns, Retina desktop settings, same-document repetition, and event-based geometry sampling if profiling becomes necessary later.

Manual acceptance: hard refresh in desktop Chrome, scroll forward several scenes, scroll backward, then interrupt a forward move with a Hero map click. Confirm the text/logo entrance, one-page pagination, continuous return motion, and no disappearance at landing. Try both Real and Toon. The user-visible result on the actual display determines whether the remaining frame-drop issue is resolved.
