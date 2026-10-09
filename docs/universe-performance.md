Full-quality performance changes to `universe.html`, assessed on 9 October 2026.

The page retains the original particle count, shader definitions, renderer resolution defaults, blur radii, planet rotation, textures, both themes and scrolling journey. No quality tiers, automatic visual downgrade or frame-rate cap were added.

**Implementation**

- Moved content shared by the page and asset generator into `site/js/universe-data.js`.
- Generated the original 15 surface, cloud, light and displacement textures offline. The files total 659,123 bytes and can be cached. All 15 match the original Canvas output byte-for-byte in the same Chrome browser. Generation retains the original dimensions, seeds, palettes and image encodings. Runtime texture pixel loops and image encoding are removed.
- Added `site/js/universe-shaders.js`: lazy module loading, serialized shader initialization, a shared GPU device when available, explicit pause/resume, fallback preservation, compilation-race protection and bounded recovery after shared-device loss. The mark initializes only when its hero scene becomes visible. Realistic sky shaders initialize only when that theme needs them. The vendor bundle is unchanged.
- Paused CSS and SVG animations in hidden scenes and inactive theme layers. SVG timelines catch up before becoming visible. The opaque overview, hidden document and pagehide pause rendering. Translucent modals keep their visible background moving.
- Combined Lenis and scene updates into one page-owned animation scheduler, updating scroll before scene positioning. Static scenes release that loop while CSS and GPU effects continue independently. Scroll, pointer movement, resize and navigation wake it. The scroll clock avoids a large time jump after idle or background suspension.
- Replaced the desktop-only one-shot snap timer with full-page wheel and touch pagination. One wheel gesture or vertical swipe advances exactly one scene regardless of input strength or momentum, then lands on the fully presented scene position. Momentum is consumed while the transition is active; navigation controls can still jump directly to any scene. Layout changes, modal/overview suspension and browser restoration resynchronize the active stop.
- Batched resize/font measurements, removed an arbitrary delayed remeasurement, cached map nodes, and avoided repeated unchanged style/HUD writes. Pointer and constellation interpolation now use elapsed time. Fixed constellation resizing when only viewport height changes.
- Added opt-in diagnostics at `universe.html?perf` through `window.universePerformance()`, plus setup performance marks. No diagnostics UI or new telemetry is added.

**Measured results**

These are local headless Chrome measurements on the host Mac GPU, with a 390 × 844 viewport, DPR 3 and touch emulation. They are not physical-phone results. Asset transfer used a local server; these results do not measure production network loading.

The baseline is repository commit `ca9b986`. After a six-second warmup, the planet scene was sampled three times for three seconds each. The complete route was sampled once over twelve seconds. See `universe-benchmark.json` for raw measurements.

| Measurement | Baseline | Optimized |
| --- | ---: | ---: |
| Planet test startup long tasks | 318 ms | None ≥ 50 ms |
| Scroll test startup long tasks | 286 ms | None ≥ 50 ms |
| Main-thread task time, planet samples | 988 ms | 829 ms |
| Main-thread task time, full route | 1,906 ms | 1,415 ms |
| Layout time, full route | 208 ms | 21 ms |
| Style recalculation, full route | 347 ms | 162 ms |
| Planet frame interval, p95 | 16.7–16.8 ms | 16.7–16.8 ms |
| Full-route frame interval, p95 | 33.4 ms | 33.4 ms |

Main-thread work fell approximately 16% for the stationary planet and 26% for the full route in this run. Scrolling still missed some frame deadlines: this is an improvement in work performed, not proof of perfect animation on every device. An earlier planet run showed approximately 27% less main-thread work, illustrating ordinary run-to-run variation.

**Visual and functional verification**

- Eight deterministic screenshot comparisons: hero, Hinge planet, transition and galaxy, each in realistic and cartoon themes. All compared pixels matched. Shader output was excluded from this deterministic comparison because it changes over time; actual WebGPU readiness, canvas dimensions and lifecycle were tested separately at full quality. The images and comparison report can be reproduced with the commands below.
- Browser checks cover mobile and desktop dimensions, all nine scenes, both themes, shader reuse, hidden-scene animation suspension, overview suspension, idle wakeup, exact scroll settling, one-page wheel/touch pagination under strong input, direct route navigation, height-only resizing, lifecycle restoration, direct cartoon entry, texture requests, case-study navigation/back, full-width project imagery, company-logo safe areas and hover-card viewport bounds.
- Controller tests exercise hiding during asynchronous compilation, duplicate initialization prevention, GPU unavailability, renderer reuse and shared-device recovery.
- Python syntax checks and `git diff --check` pass. Browser result details are in `universe-browser-results.json`; screenshot differences are in `universe-visual-results.json`.

**Experiments and boundaries**

A repeated-texture translation prototype retained the fixed SVG sphere filter but did not improve performance: main-thread work rose from approximately 704 ms to 742 ms over the comparison window. It was discarded. Original planet rendering, fullscreen blur and constellation gradients remain, preserving their appearance. No reduced-resolution or lower-frame-rate workaround was introduced.

The shader bundle registers the full component catalog, making unused components reachable. A smaller custom build would require a maintained upstream build path rather than editing minified vendor code. Lazy loading removes this bundle entirely from a direct non-hero cartoon visit; no dependency rewrite was introduced without a measured need.

The vendor's `pause()` stops its continuous loop; its own resize or input invalidations can still request an isolated repaint. No vendor internals were patched. Physical Android and iPhone/Safari profiling, battery/thermal measurements and prolonged low-end GPU testing remain external validation work. No performance guarantee is inferred from desktop emulation.

**Reproduce locally**

From the repository root, create a development environment and start a server:

```sh
python3 -m venv /tmp/universe-tools
/tmp/universe-tools/bin/pip install -r scripts/requirements-browser.txt
python3 -m http.server 8765 --bind 127.0.0.1
```

In another terminal, start an isolated Chrome instance (adjust the executable path for your installation):

```sh
"/Applications/Google Chrome 2.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9222 \
  --remote-allow-origins=http://localhost:9222 \
  --user-data-dir=/tmp/universe-chrome-profile \
  --no-first-run --no-default-browser-check about:blank
```

Run checks, or regenerate assets after changing their source data:

```sh
/tmp/universe-tools/bin/python scripts/test-universe.py
/tmp/universe-tools/bin/python scripts/generate-universe-textures.py
```

To compare with the original version, temporarily serve its HTML beside the same assets:

```sh
git show ca9b986:universe.html > .universe-baseline.html
/tmp/universe-tools/bin/python scripts/test-universe.py --baseline http://127.0.0.1:8765/.universe-baseline.html
/tmp/universe-tools/bin/python scripts/compare-universe.py --baseline http://127.0.0.1:8765/.universe-baseline.html
/tmp/universe-tools/bin/python scripts/benchmark-universe.py --baseline http://127.0.0.1:8765/.universe-baseline.html
```

Run browser scripts sequentially: they share the isolated browser tab. Remove the temporary baseline HTML after comparison. Generated textures are committed assets; visitors require no Python tooling, package installation or build step.
