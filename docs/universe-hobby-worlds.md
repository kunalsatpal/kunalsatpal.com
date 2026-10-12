# Off duty hobby worlds

The four hobbies orbit the 44px personal mark alongside Goku. They use the original radii, phases and speeds. All five hobby boxes share Goku's 72px size, including on smaller screens. Small insets on the book, controller and photo group balance their visible artwork against Goku's transparent cutout. Hover/focus holds the system and opens the existing content galleries.

- Books: an open rose-colored hardcover inspired by the user's flying-book reference, with lifted, fanned pages and two halves flapping gently at its spine like butterfly wings. The page stacks and cloth cover keep it recognizable as a physical book.
- Games: a white PS5 DualSense using the user's front-view artwork with a shallow 16-degree pitch, 12-degree yaw, and gentle bank of at most seven degrees. Its face stays readable throughout the orbit. Two short blue plumes fade beneath the grips and share the controller transform. God of War and FIFA remain in the expanded gallery.
- Anime: a physical Naruto collectible on a moon, with gently moving headband ribbons.
- People: a constellation of the actual GoFood, Cult and IIT photos. The frames spread on hover/focus; the original full-size photos remain in the expanded gallery.

The Real theme uses dimensional material shading and the Toon theme uses illustrated outlines and cel shading. Both versions share the same framing. A decoded Real image stays visible until the Toon counterpart is ready. Goku's Real artwork has a new physical collectible finish; the previous Real file is retained.

## Assets and provenance

The built-in imagegen tool generated the illustrations. The exact prompt set and reference paths are in [universe-hobby-worlds-prompts.json](./universe-hobby-worlds-prompts.json). The generated PNG sources remain in Codex's generated-images directory; the compressed final assets are stored in the repository:

- `site/img/hobby-books-real.webp`, `site/img/hobby-books-toon.webp`
- `site/img/hobby-games-real.webp`, `site/img/hobby-games-toon.webp`
- `site/img/hobby-anime-real.webp`, `site/img/hobby-anime-toon.webp`
- `site/img/goku-nimbus-physical.webp`
- `site/img/hobby-people-gofood.webp`, `site/img/hobby-people-cult.webp`, `site/img/hobby-people-iit.webp`

The worlds are transparent 384×384 WebP images. Goku is 384×256. The photo thumbnails are 192px wide, resized and compressed from the existing actual photos; no faces were regenerated.

## Rendering

Assets use the existing nearby-scene loader and do not load on the landing view. New details animate only transforms or opacity in CSS. The book reuses one image per theme for both page halves, with fixed clipping and rotation around the center spine. The controller's two small propulsion plumes share one static local SVG, without blur, flicker, stretching, or changes to path geometry per frame. They become visible only after its image decodes. Orbit updates apply a single combined transform to the artwork and jets. CSS motion pauses during page travel, offscreen, and when the stage is suspended; reduced motion disables it. Orbit positions, flight orientation, and the existing Nimbus trail use the existing rendering loop, with no additional JavaScript animation loop, timer, shader, blur or particle system. Nimbus geometry is skipped when its angle has not changed. Offscreen worlds release their transform promotion. Expanded galleries and the Super Saiyan video reuse the existing lifecycle.

## Current direction

The original orbit is the selected design. The separate logo-ship experiment and its preview server, worktree and local branch have been removed.

Focused browser checks confirmed image decoding in both themes, gallery counts, orbital movement, the final 72px sizes, mobile fit, reduced-motion behavior and offscreen animation pauses, with no runtime exceptions. Final artwork was visually inspected. No repeated scroll-performance benchmark was run; actual trackpad smoothness still needs the user's assessment.
