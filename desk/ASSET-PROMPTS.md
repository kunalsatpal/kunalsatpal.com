# Desk hero: images to regenerate

Make these in the same image tool you used for the reference, so the look stays consistent.
Attach the matching reference image (light or dark) to every prompt for style.

## Rules for every image
- **Size:** 2048 px on the long edge minimum. 4K is better for the two desk plates.
- **Camera:** straight top-down (flat lay), no perspective tilt.
- **Light:** soft daylight from the **top right**, the same for every image. Objects cast shadows down and to the left.
- **Style:** photoreal product photography, no text, no logos, no watermark.

## 1. Empty desk plates (2 images, 16:9, ideally 3840×2160)

**Light, save as `desk/light/plate.jpg`:**
> Top-down photograph of an empty light oak desk surface, fine natural wood grain running horizontally, soft daylight from a window at the top right, dappled shadow of leaves and branches falling across the top-right corner, gentle vignette toward the left edge, nothing on the desk, photoreal, 16:9, 4K.

**Dark, save as `desk/dark/plate.jpg`:**
> Same composition: top-down photograph of an empty dark walnut desk surface, near black with subtle warm grain running horizontally, soft warm light from the top right, the same dappled leaf shadow across the top-right corner, deep vignette to the left, nothing on the desk, photoreal, 16:9, 4K.

## 2. Objects (one image per object per theme)

Generate each on a **plain flat background close to the desk colour**: light grey-beige `#D9C8B0` for light mode, near black `#2E2B27` for dark mode. I'll cut them out cleanly.
Save as `desk/light/<name>-src.png` and `desk/dark/<name>-src.png`.

Prompt template (swap in the object):
> Top-down product photograph of [OBJECT], centred, filling about 70% of the frame, on a plain flat [beige / near-black] background, soft daylight from the top right, subtle soft contact shadow only, photoreal, sharp focus, 2048×2048.

| name | [OBJECT] |
|---|---|
| plant | a small succulent (echeveria) in a round textured ceramic pot |
| controller1 | a matte dark grey PlayStation 5 DualSense controller, rotated about 20° clockwise |
| controller2 | a matte dark grey PlayStation 5 DualSense controller, rotated about 30° anticlockwise |
| notebook | an open blank notebook with faint pencil wireframe sketches on the right page and a black fountain pen lying diagonally across it |
| keyboard | a compact 65% mechanical keyboard with cream and warm grey keycaps (light mode) / cream keycaps on a black case (dark mode) |
| glasses | thin metal round reading glasses, folded, lenses facing up |
| pen | a slim silver metal ballpoint pen lying diagonally, tip to bottom right |
| clip | a single silver paperclip |
| coffee | an espresso in a ceramic cup on a saucer with a small spoon, seen from directly above |
| book | the paperback book "Atomic Habits" by James Clear lying slightly rotated, with a second book peeking underneath |

## When they're ready
Drop the files into `~/chrome-logo/desk/light/` and `~/chrome-logo/desk/dark/` and tell me. I'll then:
1. cut out each object
2. match its scale and colour to the plate
3. place it in the composition
4. tune the shadows to the top-right light

The page switches to the real plates automatically as soon as both `plate.jpg` files exist.
