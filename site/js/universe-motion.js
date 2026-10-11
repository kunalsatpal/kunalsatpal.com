// Give Chrome a complete flight rather than rewriting its layers every RAF.
// Lenis still owns the scroll position, pagination, and completion callback.
export function createSceneMotion({ nodes, scenes, range, loadAssets, disabled }) {
  let flight = null
  const byScene = new Map(nodes.map(node => [node.scene, node]))
  const demotions = new Map()

  function clear(freeze = false) {
    const previous = flight
    if (!previous) return
    flight = null
    for (const { animation, element, end, properties } of previous.layers) {
      if (freeze) {
        try {
          animation.commitStyles()
        } catch {
          // Older browsers can still hand the current presentation to the renderer.
          const style = getComputedStyle(element)
          for (const property of properties) element.style[property] = style[property]
        }
      } else {
        // Apply the landing pose before removing fill:both. In particular, a
        // jump finishes after the renderer has run, so cancellation alone would
        // expose its old invisible inline pose for one frame.
        for (const property of properties) element.style[property] = end[property]
        if (properties.includes('filter') && end.filter === 'blur(0px)') element.style.filter = 'none'
      }
      animation.cancel()
    }
    for (const node of previous.owned) {
      clearTimeout(demotions.get(node))
      // Keep the landing layer through the wheel momentum lock, avoiding a
      // promotion/demotion burst when a visitor immediately changes direction.
      demotions.set(node, setTimeout(() => {
        if (!flight?.owned.has(node)) node.scene.classList.remove('motion-layer')
        demotions.delete(node)
      }, 320))
    }
  }

  function start({ indices, duration, offsetAt, easing, startTime = null }) {
    clear(true)
    if (disabled || typeof Element.prototype.animate !== 'function' || duration <= 0) return false
    const layers = [], owned = new Set(), opacity = new Map()
    // Sample the existing nonlinear depth curves once per gesture. The browser
    // interpolates between them at the display's refresh rate, independently of
    // the page's JavaScript callbacks.
    const samples = Math.max(2, Math.ceil(duration * .12))
    const add = (element, keyframes) => {
      const animation = element.animate(keyframes, { duration, easing: 'linear', fill: 'both' })
      // Hold the initial pose until the renderer aligns this flight with Lenis.
      // Destination-only arrivals already have their presentation epoch.
      animation.pause()
      animation.currentTime = 0
      layers.push({ animation, element, end: keyframes.at(-1),
        properties: Object.keys(keyframes[0]).filter(key => key !== 'offset') })
    }
    try {
      for (const index of new Set(indices)) {
        const node = nodes[index]
        const frames = [], blurFrames = [], floatFrames = node.floats.map(() => [])
        let initialOpacity = 0
        for (let sample = 0; sample <= samples; sample++) {
          const offset = sample / samples
          let z = offsetAt(index, easing(offset))
          if (index === 0 && z < 0) z = 0
          if (index === scenes.length - 1 && z > 0) z = 0
          const approach = z < 0 ? range(-z, .12, .8) : 0
          const pass = z > 0 ? range(z, .12, .8) : 0
          const alpha = (1 - approach) * (1 - pass)
          if (sample === 0) initialOpacity = alpha
          const frame = { offset, opacity: alpha,
            transform: `scale(${1 - approach * .55 + pass * .9})` }
          // Keep filter in its own effect. A costly filter must not make the
          // scene's transform/opacity animation depend on main-thread updates.
          // Non-hero filters use content bounds instead of the entire viewport.
          // The browser interpolates none using the neutral blur as needed.
          // The existing !important Toon travel rule still suppresses this blur,
          // including when the visitor changes theme halfway through a flight.
          frames.push(frame)
          blurFrames.push({ offset, filter: alpha > .98 ? 'none' : `blur(${(approach * 10 + pass * 14).toFixed(1)}px)` })
          node.floats.forEach(({ depth }, i) => {
            const a = z < 0 ? range(-z + depth, .12, .8) : 0
            floatFrames[i].push({ offset, translate: `0 ${a * 40}px`, opacity: 1 - a })
          })
        }
        loadAssets(node.scene)
        clearTimeout(demotions.get(node))
        demotions.delete(node)
        node.scene.classList.add('motion-layer')
        add(node.scene, frames)
        add(node.blur, blurFrames)
        node.floats.forEach(({ el }, i) => add(el, floatFrames[i]))
        owned.add(node)
        opacity.set(node.scene, initialOpacity)
        node.hidden = false
        node.scene.style.visibility = 'visible'
      }
    } catch {
      // Keep the original renderer usable if this browser rejects an animation.
      for (const { animation } of layers) animation.cancel()
      for (const index of indices) nodes[index].scene.classList.remove('motion-layer')
      return false
    }
    flight = { layers, owned, opacity, samples, aligned: false }
    if (startTime !== null) align(startTime)
    return true
  }

  function align(startTime) {
    if (!flight || flight.aligned) return
    for (const { animation } of flight.layers) {
      animation.play()
      animation.startTime = startTime
    }
    flight.aligned = true
  }

  return {
    start, clear, align,
    owns: node => !!flight?.owned.has(node),
    updateOpacity(node, opacity) { if (flight?.owned.has(node)) flight.opacity.set(node.scene, opacity) },
    isPainted(scene) {
      return scene.style.visibility !== 'hidden' && (flight?.opacity.get(scene) ?? 1) >= .01
    },
    isMoving(scene) { return !!flight?.owned.has(byScene.get(scene)) },
    needsAlignment: () => !!flight && !flight.aligned,
    status: () => flight ? { active: true, aligned: flight.aligned, samples: flight.samples,
      scenes: [...flight.owned].map(node => node.scene.dataset.scene) } : { active: false },
  }
}
