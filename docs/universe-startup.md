# Universe first-load behavior

The hero is now part of `universe.html`, with a 360 ms opacity entrance that starts from readable text. JavaScript reuses that section. The surrounding artwork fades in after image decoding, and decorative motion eases in after the copy. The initial star rush and cards flying from the centre are removed.

Desktop artwork uses eager, high-priority picture sources. On screens up to 900 px, where those cards are hidden, the real artwork is not downloaded. Image dimensions reserve its layout. The existing font families are served locally with licenses in `site/fonts`; `font-display: optional` retains the fallback for that load when a font arrives too late, avoiding a late text shift.

Later scenes start with deferred image and texture URLs. Assets are activated within 1.5 scene intervals of the current route position, including direct scene entry. The shader bundle starts after the brief entrance and an idle opportunity. The existing SVG logo remains visible until the renderer reports readiness, then crossfades over 300 ms. GPU failure preserves the fallback. Initialization yields between scene-building tasks, and browser history remembers the destination even when a cached document cannot be restored.

## Validation

Use the local server and isolated debugging browser described in `universe-performance.md`, then run:

```sh
/tmp/universe-tools/bin/python scripts/test-universe-startup.py
```

The startup script creates its own test tab. It covers cold 390 × 844 mobile loads at DPR 3, 4× CPU throttling, 150 ms latency, 200,000 bytes/s download throughput, blocked application and shader modules, native scrolling before startup, an immediate swipe during startup, approaching-scene asset loading, direct scene entry, reduced motion, desktop artwork, and real shader readiness where WebGPU is available. Screenshots and detailed samples go to `/tmp/universe-startup-checks` by default. An optional `--baseline URL` measures an earlier version served beside the same assets.

Cold mobile samples showed no measured layout shifts, no broken hero images, and no requests for distant textures, moon previews, or hidden desktop artwork. Desktop/tablet/mobile scene checks and the navigation regression tail were also exercised. Throttled frame timing varies with the host and shader compilation still produces some long tasks; this is not a claim of uninterrupted 60 fps or a physical-phone benchmark.
