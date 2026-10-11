// Full-page scene pagination: one wheel gesture or swipe moves one scene.
export function nearestStop(stops, position) {
  return stops.reduce((best, value, index) => Math.abs(value - position) < Math.abs(stops[best] - position) ? index : best, 0)
}

export function createSceneSnap({ getStops, getPosition, animateTo, resizeAnimation, stopAnimation, enabled, ignoreInput, eventTarget = window }) {
  let phase = 'idle', targetIndex = null, settledIndex = nearestStop(getStops(), getPosition())
  let token = 0, unlockAt = 0, settleTimer = 0, touch = null
  let lastWheelAt = -Infinity, wheelOwned = false, wheelDirection = 0, reversal = 0
  const listeners = []
  const listen = (name, fn, options) => {
    eventTarget.addEventListener(name, fn, options)
    listeners.push(() => eventTarget.removeEventListener(name, fn, options))
  }
  const clearSettle = () => { clearTimeout(settleTimer); settleTimer = 0 }
  const allowed = event => enabled() && !ignoreInput(event)

  function cancel() {
    clearSettle()
    token++
    const owned = phase === 'snapping' || phase === 'navigating'
    phase = 'idle'; targetIndex = null; touch = null; unlockAt = 0
    wheelOwned = false; lastWheelAt = -Infinity; reversal = 0
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

  function page(direction, fresh = false) {
    if (!direction || phase !== 'idle' || (!fresh && performance.now() < unlockAt)) return false
    const current = nearestStop(getStops(), getPosition())
    move(current + Math.sign(direction))
    return true
  }

  // Consume wheel momentum so one gesture cannot cross additional scenes.
  listen('wheel', event => {
    if (!allowed(event) || event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY) || !event.deltaY) return
    event.preventDefault()
    event.stopImmediatePropagation()
    const now = event.timeStamp > 0 ? event.timeStamp : performance.now(), direction = Math.sign(event.deltaY)
    const newBurst = now - lastWheelAt >= 160
    lastWheelAt = now
    const pixels = Math.abs(event.deltaY) * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1)
    reversal = !newBurst && wheelOwned && direction !== wheelDirection ? reversal + pixels : 0
    // A quiet gap or deliberate reversal marks new finger input. Small reverse
    // noise stays part of the old momentum tail. Never retarget an active flight.
    const reverseGesture = phase === 'idle' && reversal >= 12
    if (newBurst || reverseGesture) wheelOwned = false
    if (wheelOwned) return
    if (page(direction, newBurst || reverseGesture) || phase !== 'idle') {
      wheelOwned = true
      wheelDirection = direction
      reversal = 0
    }
  }, { passive: false, capture: true })

  // Consume vertical touch movement; only an idle, unlocked swipe advances a scene.
  listen('touchstart', event => {
    if (!allowed(event) || event.touches.length !== 1) {
      touch = null
      return
    }
    const point = event.touches[0]
    touch = {
      x: point.clientX,
      y: point.clientY,
      dy: 0,
      canPage: phase === 'idle',
      started: false,
    }
  }, { passive: true, capture: true })
  listen('touchmove', event => {
    if (!touch || !allowed(event) || event.touches.length !== 1) return
    const point = event.touches[0]
    const dx = point.clientX - touch.x, dy = point.clientY - touch.y
    if (Math.abs(dy) <= Math.abs(dx)) return
    touch.dy = dy
    event.preventDefault()
    event.stopImmediatePropagation()
    // Respond when vertical intent crosses the existing 36px threshold, rather
    // than waiting for the finger to lift. This touch can commit only one page.
    if (touch.canPage && !touch.started && Math.abs(dy) >= 36) touch.started = page(-dy, true)
  }, { passive: false, capture: true })
  const endTouch = () => {
    if (!touch) return
    const { dy, canPage, started } = touch
    touch = null
    if (canPage && !started && Math.abs(dy) >= 36) page(-dy, true)
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
    layoutChanged({ previousIndex } = {}) {
      if (!enabled()) return
      const index = targetIndex ?? previousIndex ?? nearestStop(getStops(), getPosition())
      // A renderer can remap its active motion without changing ownership or easing.
      if (phase !== 'idle' && resizeAnimation?.(index) === true) return
      if (phase !== 'idle') { cancel(); move(index, 'navigate') }
      else move(index, 'resize')
    },
    state: () => ({ phase, targetIndex, settledIndex, touchActive: !!touch }),
    destroy() { cancel(); listeners.forEach(remove => remove()) },
  }
}
