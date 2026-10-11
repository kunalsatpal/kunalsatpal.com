# Goku hobby media — 11 October 2026

The gym hobby uses the two references supplied by the user:

- Flying Nimbus sticker: [Tenor, Goku Dragon Ball](https://tenor.com/view/goku-dragon-ball-flying-cloud-gif-1884678497519529846). Source animation: `https://media.tenor.com/Gie5G6h373YAAAAj/goku-dragon-ball.gif`.
- Expanded power-up: [Pinterest pin](https://www.pinterest.com/pin/606086062388700507/), whose original link points to [Tenor, Dragon Ball Z Goku](https://tenor.com/view/dragon-ball-z-goku-goes-super-saiyan-against-android-gif-12485392). Local video source: `https://media.tenor.com/2bA7sWAS0c4AAAPo/dragon-ball-z-goku.mp4`. Poster source: `https://i.pinimg.com/736x/16/17/6f/16176f55be135618e54fad1b7e7a50fc.jpg`.

`site/img/goku-nimbus-sprite.webp` stores the seven original transparent 192×200 frames horizontally, losslessly, in 13,410 bytes. CSS steps move the strip at the original 60ms-per-frame timing (420ms total), without continuous GIF decoding. The existing offscreen and suspended-scene rules pause it. Reduced motion shows one frame.

Goku has no circular badge, shading overlay, border or glow in either theme. The existing hobby orbit places him around the center logo, with a somewhat faster individual orbit and a horizontal turn at the ends to keep Nimbus's trail behind him. Other hobbies retain their previous paths and speeds. Hover/focus still holds the system for reading.

`site/img/goku-power-up.mp4` is a local muted 640×384 video (141,239 bytes), with a local poster (25,588 bytes). It loads on demand when expanded, retains its DOM node when the same hobby is focused/clicked again, and pauses when the card closes, the scene leaves view, the page is hidden/suspended, the preview is hidden below 901px, or reduced motion is enabled.

One focused browser pass verified sprite dimensions, center-logo size, playback, video reuse, close-to-pause behavior, both themes, live reduced-motion changes, mobile preview pausing and offscreen pausing, with no uncaught exceptions. After removing the badge, a smaller check verified actual orbit movement, no circle/border/shadow in either theme including the active hobby, and the expanded video. Screenshots were visually inspected. No repeated scroll-performance benchmark was run.
