import { createPlanetSurfaces } from '../site/js/universe-planets.js?v=1'
import { MAJOR } from '../site/js/universe-data.js'

// Fixed-time visual fixtures compare the original SVG/CSS path with the GPU
// path, including cloudy surfaces and Hinge's masked, colored night lights.
export async function planetFixtures() {
  const html = await (await fetch('/universe.html')).text()
  document.head.insertAdjacentHTML('beforeend', html.match(/<style>[\s\S]*?<\/style>/)[0])
  document.body.innerHTML = `<svg width="0" height="0" style="position:absolute"><filter id="sphere" primitiveUnits="objectBoundingBox" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB"><feImage href="/site/textures/universe/sphere.png" x="0" y="0" width="1" height="1" preserveAspectRatio="none" result="map"/><feDisplacementMap in="SourceGraphic" in2="map" scale="0.5" xChannelSelector="R" yChannelSelector="G"/></filter></svg>`
  document.documentElement.className = ''
  document.body.style.cssText = 'margin:0;min-height:900px;background:#050710;overflow:visible'
  const texture = name => `/site/textures/universe/${name}`
  const renderer = createPlanetSurfaces({ sphereURL: texture('sphere.png') })
  const boxes = [], fixtures = []
  for (const [row, pl] of MAJOR.entries()) {
    for (const [column, time] of [0, 23000, 67500].entries()) {
      const pair = document.createElement('div')
      pair.style.cssText = `position:absolute;left:${20 + column * 450}px;top:${20 + row * 280}px;width:440px;height:250px;--glow:${pl.glow}`
      const surfaceURL = texture(`${pl.key}-surface.jpg`), cloudURL = texture(`${pl.key}-clouds.png`)
      const lightURL = pl.lights ? texture(`${pl.key}-lights.png`) : null
      for (const url of [surfaceURL, cloudURL, lightURL].filter(Boolean)) {
        const img = new Image(); img.src = url; await img.decode()
      }
      const make = left => {
        const planet = document.createElement('div')
        planet.className = 'planet'
        planet.style.cssText = `inset:auto;left:${left}px;top:0;width:210px;height:210px;box-shadow:none`
        planet.innerHTML = `<div class="surface" style="background-image:url(${surfaceURL})"></div><div class="clouds" style="background-image:url(${cloudURL})"></div>${lightURL ? `<div class="lights" style="background-image:url(${lightURL})"></div>` : ''}<div class="shade"></div>`
        pair.append(planet)
        const offset = -(time / 1000 * pl.spin) % 420
        planet.querySelector('.surface').style.backgroundPositionX = `${offset}px`
        if (lightURL) planet.querySelector('.lights').style.backgroundPositionX = `${offset}px`
        planet.querySelector('.clouds').style.backgroundPositionX = `${-(time / 1000 * pl.spin * 1.45) % 420}px`
        return planet
      }
      const native = make(0), gpuPlanet = make(225)
      document.body.append(pair)
      const gpu = renderer.register({ planet: gpuPlanet, surfaceURL, cloudURL, lightURL, spin: pl.spin })
      gpu.resize(210); await gpu.load(); gpu.render(time)
      if (!gpuPlanet.classList.contains('gpu-ready')) throw new Error('GPU fixture did not render')
      const a = native.getBoundingClientRect(), b = gpuPlanet.getBoundingClientRect()
      boxes.push({ key: pl.key, time, native: [a.x, a.y, a.right, a.bottom], gpu: [b.x, b.y, b.right, b.bottom] })
      fixtures.push({ gpu, planet: gpuPlanet, time })
    }
  }
  // Wait for SVG feImage to paint, then retain a fixed GPU frame for capture.
  await new Promise(resolve => setTimeout(resolve, 150))
  for (const f of fixtures) f.gpu.render(f.time)
  window.planetFixtureState = { renderer, fixtures }
  return boxes
}

export async function testPlanetFallback() {
  const { fixtures } = window.planetFixtureState
  const f = fixtures.find(f => f.planet.querySelector('.lights'))
  const canvas = f.planet.querySelector('canvas')
  const gl = canvas.getContext('webgl'), extension = gl.getExtension('WEBGL_lose_context')
  if (!extension) throw new Error('Cannot test context recovery')
  extension.loseContext()
  await new Promise(resolve => setTimeout(resolve, 100))
  if (f.gpu.render(f.time) || f.planet.classList.contains('gpu-ready')) throw new Error('Context loss did not restore CSS')
  extension.restoreContext()
  for (let i = 0; i < 100 && !f.planet.classList.contains('gpu-ready'); i++) {
    await new Promise(resolve => setTimeout(resolve, 30))
  }
  if (!f.planet.classList.contains('gpu-ready')) throw new Error('GPU context did not recover')
  return { fallback: 'CSS restored', recovery: 'GPU restored' }
}
