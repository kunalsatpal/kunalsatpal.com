// Full-page scene pagination: one wheel gesture or swipe moves one scene.
export function nearestStop(stops, position) {
  return stops.reduce((best, value, index) => Math.abs(value - position) < Math.abs(stops[best] - position) ? index : best, 0)
}

export function createSceneSnap({ getStops, getPosition, animateTo, stopAnimation, enabled, ignoreInput }) {
  let phase = 'idle', targetIndex = null, settledIndex = nearestStop(getStops(), getPosition())
  let token = 0, unlockAt = 0, settleTimer = 0, touch = null
  const listeners = []
  const listen = (name, fn, options) => {
    window.addEventListener(name, fn, options)
    listeners.push(() => window.removeEventListener(name, fn, options))
  }
  const clearSettle = () => { clearTimeout(settleTimer); settleTimer = 0 }
  const allowed = event => enabled() && !ignoreInput(event)

  function cancel() {
    clearSettle()
    token++
    const owned = phase === 'snapping' || phase === 'navigating'
    phase = 'idle'; targetIndex = null; touch = null; unlockAt = 0
    if (owned) stopAnimation()
    settledIndex = nearestStop(getStops(), getPosition())
  }

  function move(index, kind = 'snap') {
    clearSettle()
    const stops = getStops()
    index = Math.max(0, Math.min(stops.length - 1, index))
    const target = stops[index], distance = Math.abs(target - getPosition())
    const current = ++token
    targetIndex = index
    phase = kind === 'navigate' ? 'navigating' : 'snapping'
    if (distance <= 1) {
      phase = 'idle'; targetIndex = null; settledIndex = index; unlockAt = performance.now() + 220
      return
    }
    const duration = kind === 'resize' ? 0 : kind === 'navigate' ? undefined : .95
    animateTo(target, { kind, duration, onComplete: () => {
      if (current !== token) return
      phase = 'idle'; targetIndex = null; settledIndex = index
      // Swallow the tail of the same wheel/trackpad gesture after landing.
      unlockAt = performance.now() + 320
    } })
  }

  function page(direction) {
    if (!direction || phase !== 'idle' || performance.now() < unlockAt) return
    const current = nearestStop(getStops(), getPosition())
    move(current + Math.sign(direction))
  }

  // Consume wheel momentum so one gesture cannot cross additional scenes.
  listen('wheel', event => {
    if (!allowed(event) || event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY) || !event.deltaY) return
    event.preventDefault()
    event.stopImmediatePropagation()
    page(event.deltaY)
  }, { passive: false, capture: true })

  // Hold native touch movement; a completed vertical swipe advances one scene.
  listen('touchstart', event => {
    if (!allowed(event) || event.touches.length !== 1 || phase !== 'idle' || performance.now() < unlockAt) return
    const point = event.touches[0]
    touch = { x: point.clientX, y: point.clientY, dy: 0 }
  }, { passive: true, capture: true })
  listen('touchmove', event => {
    if (!touch || !allowed(event) || event.touches.length !== 1) return
    const point = event.touches[0]
    const dx = point.clientX - touch.x, dy = point.clientY - touch.y
    if (Math.abs(dy) <= Math.abs(dx)) return
    touch.dy = dy
    event.preventDefault()
    event.stopImmediatePropagation()
  }, { passive: false, capture: true })
  const endTouch = () => {
    if (!touch) return
    const dy = touch.dy
    touch = null
    if (Math.abs(dy) >= 36) page(-dy)
  }
  listen('touchend', endTouch, { passive: true, capture: true })
  listen('touchcancel', () => { touch = null }, { passive: true, capture: true })

  // Scrollbar dragging, browser restoration, and scripted scrolls resolve exactly.
  listen('scroll', () => {
    if (!enabled() || phase !== 'idle' || touch) return
    clearSettle()
    settleTimer = setTimeout(() => {
      if (enabled() && phase === 'idle') move(nearestStop(getStops(), getPosition()))
    }, 180)
  }, { passive: true })

  return {
    navigate(index) { cancel(); if (enabled()) move(index, 'navigate') },
    cancel,
    resume() {
      touch = null
      settledIndex = nearestStop(getStops(), getPosition())
      clearSettle()
      settleTimer = setTimeout(() => { if (enabled() && phase === 'idle') move(settledIndex) }, 80)
    },
    layoutChanged() {
      if (!enabled()) return
      const index = targetIndex ?? nearestStop(getStops(), getPosition())
      if (phase !== 'idle') { cancel(); move(index, 'navigate') }
      else move(index, 'resize')
    },
    state: () => ({ phase, targetIndex, settledIndex, touchActive: !!touch }),
    destroy() { cancel(); listeners.forEach(remove => remove()) },
  }
}
