import { createSceneSnap } from '../site/js/universe-scroll.js'
import { createSceneMotion } from '../site/js/universe-motion.js'

export async function testGestureResponse() {
  const assert = (value, message) => { if (!value) throw Error(message) }
  const events = new EventTarget(), moves = []
  let position = 1000, complete, timestamp = 100
  const snap = createSceneSnap({
    getStops: () => [0, 1000, 2000, 3000], getPosition: () => position,
    animateTo: (target, options) => { moves.push(target); complete = () => { position = target; options.onComplete() } },
    stopAnimation() {}, enabled: () => true, ignoreInput: () => false, eventTarget: events,
  })
  const wheel = (delta, gap = 16) => {
    timestamp += gap
    const event = new WheelEvent('wheel', { deltaY: delta, cancelable: true })
    Object.defineProperty(event, 'timeStamp', { value: timestamp })
    events.dispatchEvent(event)
  }
  const touch = (type, x, y) => {
    const event = new Event(type, { cancelable: true })
    Object.defineProperty(event, 'touches', { value: type === 'touchend' ? [] : [{ clientX: x, clientY: y }] })
    events.dispatchEvent(event)
  }
  try {
    wheel(6)
    assert(moves.length === 1, 'The first trackpad delta must start one flight')
    wheel(4); wheel(3)
    complete()
    // A long momentum tail must remain owned even after the old 320ms cooldown.
    await new Promise(resolve => setTimeout(resolve, 340))
    for (let i = 0; i < 30; i++) wheel(1)
    assert(moves.length === 1, 'Continuous momentum must not advance a second page')
    wheel(-.5); wheel(-.5)
    assert(moves.length === 1, 'Tiny reverse noise must not create another gesture')
    wheel(-5); wheel(-6)
    assert(moves.length === 2 && moves[1] === 1000, 'Intentional trackpad reversal starts a backward flight')
    complete()
    wheel(10, 170)
    assert(moves.length === 3 && snap.state().phase === 'snapping', 'A fresh gesture must bypass the landing cooldown')
    // New input during an active flight stays consumed, including its tail.
    wheel(10, 170)
    complete(); wheel(4)
    assert(moves.length === 3, 'A gesture during travel must not replay later as momentum')
    touch('touchstart', 100, 200)
    touch('touchmove', 160, 190)
    assert(moves.length === 3, 'Horizontal touch movement must not page')
    touch('touchmove', 100, 155)
    assert(moves.length === 4, 'A vertical swipe starts at its threshold while the finger is down')
    complete()
    touch('touchmove', 100, 100)
    touch('touchend')
    assert(moves.length === 4, 'A held finger and touchend must never commit a second page')
    touch('touchstart', 100, 100)
    touch('touchmove', 100, 155)
    assert(moves.length === 5 && moves[4] === 2000, 'A fresh opposite touch starts immediately after landing')
    return 'Passed: immediate wheel input, long momentum ownership, reverse noise, fresh gestures, threshold touch response and one view per gesture'
  } finally { snap.destroy() }
}

export function testPreparedFlight() {
  const assert = (value, message) => { if (!value) throw Error(message) }
  const scenes = [0, 1].map(u => ({ u })), elements = []
  const nodes = scenes.map(() => {
    const scene = document.createElement('section'), blur = document.createElement('div')
    scene.appendChild(blur); document.body.appendChild(scene)
    scene.style.cssText = 'position:fixed;left:-5000px;top:0;width:100px;height:100px'
    elements.push(scene)
    return { scene, blur, floats: [] }
  })
  const smooth = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x)
  const motion = createSceneMotion({ nodes, scenes, range: (x, a, b) => smooth((x - a) / (b - a)), loadAssets() {}, disabled: false })
  const easing = x => 1 - (1 - x) ** 4
  let samples = 0
  const offsetAt = (i, value) => { samples++; return value - i }
  try {
    motion.prepare({ indices: [0, 1], duration: 1050, offsetAt, easing })
    assert(motion.status().cachedPoses === 2 && !nodes.some(node => node.scene.getAnimations().length), 'Preparation must cache poses without starting animations')
    samples = 0
    motion.start({ indices: [0, 1], duration: 1050, offsetAt, easing })
    assert(samples === 4, 'An adjacent gesture must reuse its prepared samples')
    const prepared = nodes.map(node => node.scene.getAnimations()[0].effect.getKeyframes())
    motion.clear()
    const cold = createSceneMotion({ nodes, scenes, range: (x, a, b) => smooth((x - a) / (b - a)), loadAssets() {}, disabled: false })
    cold.start({ indices: [0, 1], duration: 1050, offsetAt, easing })
    assert(JSON.stringify(prepared) === JSON.stringify(nodes.map(node => node.scene.getAnimations()[0].effect.getKeyframes())), 'Prepared and cold flight curves must match exactly')
    cold.clear()
    samples = 0
    motion.start({ indices: [0, 1], duration: 700, offsetAt: (i, value) => { samples++; return .4 + .6 * value - i }, easing })
    assert(samples > 4, 'An interrupted flight must sample its actual starting position')
    return 'Passed: idle preparation, no early animation, cached gesture startup, exact curve equality and interrupted flight handling'
  } finally {
    motion.clear()
    elements.forEach(element => element.remove())
  }
}
