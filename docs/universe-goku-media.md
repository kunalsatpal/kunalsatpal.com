# Goku hobby media — 11 October 2026

The orbit uses paired Real/Toon Goku/Nimbus illustrations generated with the imagegen skill; the expanded view retains the user's second animation reference. References:

- Flying Nimbus sticker: [Tenor, Goku Dragon Ball](https://tenor.com/view/goku-dragon-ball-flying-cloud-gif-1884678497519529846). Source animation: `https://media.tenor.com/Gie5G6h373YAAAAj/goku-dragon-ball.gif`.
- Expanded power-up: [Pinterest pin](https://www.pinterest.com/pin/606086062388700507/), whose original link points to [Tenor, Dragon Ball Z Goku](https://tenor.com/view/dragon-ball-z-goku-goes-super-saiyan-against-android-gif-12485392). Local video source: `https://media.tenor.com/2bA7sWAS0c4AAAPo/dragon-ball-z-goku.mp4`. Poster source: `https://i.pinimg.com/736x/16/17/6f/16176f55be135618e54fad1b7e7a50fc.jpg`.

`site/img/goku-nimbus-3d.webp` is a transparent 384×256 cutout, 24,460 bytes. The generated art depicts adult Goku with spiky black hair, orange gi and blue accessories, seated on a rounded, softly shaded golden Nimbus facing right. It is compressed from the generated PNG with alpha preserved. The previous pixel-art sprite is no longer referenced by the page.

`site/img/goku-nimbus-toon.webp` is the matching 384×256 Toon variant, 27,388 bytes. It preserves the pose, framing and orientation while using dark navy outlines, saturated colors and flat cel shading. Both small assets load through the existing nearby-scene loader. Theme changes fade only their opacity over 300ms; they share one orbit, size and float. The Real art remains visible until the Toon image has decoded, avoiding an empty theme switch. Reduced motion disables the fade. The Toon trail is slightly thicker with a subtler halo to suit its graphic style.

The character box is 72px, reduced from 104px, with no circular badge, border or CSS glow in either theme. Its label sits below the cloud. A gentle CSS float gives it motion and pauses with the existing scene controls; reduced motion removes the float. The existing hobby orbit places him around the center logo and flips the artwork at the ends to face his direction of travel.

Nimbus leaves a short, fading golden trail along the preceding section of the same orbit. Two simple SVG strokes and a gradient provide depth without filters, particles or a new rendering loop. Their geometry updates with the existing hobby loop, only while the scene is painted and only when the path changes. Hover/focus still holds the system and trail for reading. Other hobbies retain their previous paths and speeds.

`site/img/goku-power-up.mp4` is a local muted 640×384 video (141,239 bytes), with a local poster (25,588 bytes). It loads on demand when expanded, retains its DOM node when the same hobby is focused/clicked again, and pauses when the card closes, the scene leaves view, the page is hidden/suspended, the preview is hidden below 901px, or reduced motion is enabled.

The current focused browser pass verified the 72px box and loaded artwork, moving trail with its endpoint within 2px of the character's orbit anchor, hover holding, expanded video playback, both themes, reduced motion, no mobile horizontal overflow, offscreen animation pausing and no offscreen trail updates. No uncaught exceptions occurred. Earlier checks covered video reuse, close-to-pause behavior and hidden mobile preview pausing. Screenshots were visually inspected. No repeated scroll-performance benchmark was run.

The subsequent paired-art check verified both image dimensions, correct image opacity for each theme, a crossfade whose combined opacity remained approximately one, the undecoded-Toon fallback, a cold load using the saved Toon preference, fixed 72px sizing, mobile overflow and reduced-motion behavior. No uncaught exceptions occurred. The Toon screenshot was visually inspected; no performance benchmark was repeated.
