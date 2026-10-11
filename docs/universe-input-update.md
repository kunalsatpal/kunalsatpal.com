# Gesture response update — 11 October 2026

This checkpoint addresses the remaining delay between finger input and page movement after the sky optimization. It changes input acceptance and when flight keyframes are built. The scene curves, blur, duration, image depth, planet rendering, sky effects and selected-page jump appearance remain the same.

## Changes

The previous controller rejected all input for 320 ms after landing. Wheel input now owns a gesture until its momentum ends. A 160 ms quiet gap or a deliberate reversal identifies fresh input, allowing it to start after landing without waiting for that fixed cooldown. Tiny reverse noise remains part of the previous gesture. Event timestamps identify gaps in the input stream independently of delayed JavaScript dispatch. An active page flight still consumes input, and its momentum cannot replay as an extra page afterward.

Touch pagination commits once vertical movement crosses the existing 36 CSS px threshold, instead of waiting until the finger lifts. A held finger cannot commit again, even if the flight completes before release. Horizontal gestures remain available. A new touch after landing is explicit fresh input and can start immediately.

`universe-motion.js` caches the existing adjacent flight keyframes. The page prepares forward and backward neighbors in an idle callback at a settled stop. A gesture then creates its browser animations from those prepared arrays instead of recalculating every sample inside the input handler. The cache holds at most 64 poses, adds no live layers during preparation, and preserves a cold fallback. Interrupted positions and resize remaps still sample their actual curves.

## Verification

Controller checks passed for first-delta response, momentum continuing beyond the old cooldown, small reverse noise, intentional reversal, fresh input after landing, input consumed during travel, horizontal touch, touch threshold response and one-view-per-gesture behavior.

Browser animation checks confirmed that preparation starts no animations, a warmed adjacent flight reuses its samples, prepared and cold keyframes match exactly, and interrupted flights calculate their actual starting positions.

One focused live pass checked Gojek → Cult.fit → Gojek, fresh reversal during the former cooldown, a quick Hero return with the original logo size, and Hinge → Gojek touch movement beginning before release. Continuing the swipe after landing and then releasing advanced no additional view. Remaining return/touch checks were resumed after correcting the test's SVG click helper; the passed wheel/cache cases were not repeatedly run.

Use the isolated server/Chrome setup in [universe-performance.md](./universe-performance.md), then run:

```sh
/tmp/universe-tools/bin/python scripts/check-universe-input.py
```

No repeated performance benchmark was run. Check the perceived response with actual trackpad input and phone swipes, particularly successive gestures on planet screens.
