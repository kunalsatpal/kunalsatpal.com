# GPU planet surfaces — 11 October 2026

The three major planets previously moved surface, cloud and city-light CSS backgrounds beneath separate SVG displacement filters every animation frame. Their backgrounds now render in one small WebGL pass per visible planet, using the same `sphere.png` displacement map, original textures, spin speeds, independent cloud motion, sRGB screen blending, opacities and night-light mask. The CSS shade, atmosphere, rings, moons, previews, text and scene motion remain in place.

Each planet initializes lazily with the existing nearby-scene asset loading. Textures are decoded and uploaded once. The canvas keeps full device-pixel resolution and only becomes visible after its first complete frame. The existing frame loop draws painted planets; settled Toon mode and suspended/hidden scenes do not draw. There is no new autonomous animation loop or full-screen canvas. Resizing reuses textures and the program.

The SVG/CSS path remains available for unavailable WebGL, setup/texture failures and context loss. On context loss its current texture offsets are restored before revealing it. A restored context rebuilds GPU resources and hands back only after rendering.

## Verification

Nine fixed-time comparisons covered all three planets at 0, 23 and 67.5 seconds, including Gojek's storm and Hinge's night lights. At desktop DPR 2, the average absolute RGB difference ranged from 0.33 to 0.46 on a 0–255 scale; the 95th percentile channel difference was 2. The paired screenshots were also visually inspected. Minor sampling differences remain; this is not a claim of bit-identical pixels.

Real WebGL context loss restored the CSS path, and restoration rebuilt the GPU path. A focused live browser pass confirmed trusted wheel forward/reverse pagination, no settled hidden-planet draws, no draws in settled Toon mode, selected-page jumps, the 46px landing logo, mobile resizing at DPR 3, and return to desktop sizing. No uncaught exceptions occurred.

`scripts/check-universe-planets.py` reproduces the visual/context checks with the local preview server and isolated Chrome described in `universe-performance.md`. Existing gesture behavior and timing were not changed. No repeated FPS benchmark was run: assess the improvement with actual desktop Chrome trackpad input, especially successive planet flights and quick return to the landing view.

The change removes repeated CSS background painting and three displacement/blending surfaces from the normal major-planet path. It still uses GPU work, retains the existing sky effects and transition blur, and does not prove perfect frame delivery on every device.
