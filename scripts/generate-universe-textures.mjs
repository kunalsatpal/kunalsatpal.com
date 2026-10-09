// Run with scripts/generate-universe-textures.py against the local preview server.
// These are the original browser Canvas algorithms, seeds, dimensions and encodings.
import { MAJOR, STOPS } from '../site/js/universe-data.js'
  function noise2(seed) {
    const p = new Uint8Array(512); let r = seed; for (let i = 0; i < 256; i++) p[i] = i
    for (let i = 255; i > 0; i--) { r = (r * 16807) % 2147483647; const j = r % (i + 1); [p[i], p[j]] = [p[j], p[i]] }
    for (let i = 0; i < 256; i++) p[i + 256] = p[i]
    const h = (x, y) => p[p[x & 255] + (y & 255)] / 255, f = t => t * t * (3 - 2 * t)
    return (x, y) => { const xi = Math.floor(x), yi = Math.floor(y), xf = f(x - xi), yf = f(y - yi)
      const a = h(xi, yi), b = h(xi + 1, yi), c = h(xi, yi + 1), d = h(xi + 1, yi + 1)
      return a + (b - a) * xf + (c - a) * yf + (a - b - c + d) * xf * yf }
  }
  const hex = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16))
  function surface(pl, seed) {
    const W = 512, H = 256, cv = document.createElement('canvas'); cv.width = W; cv.height = H
    const ctx = cv.getContext('2d'), img = ctx.createImageData(W, H), n = noise2(seed), pal = pl.palette.map(hex)
    const fbm = (x, y) => { let v = 0, a = .5, fx = 1; for (let o = 0; o < 4; o++) { v += a * n(x * fx, y * fx); a *= .5; fx *= 2 } return v }
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const u = x / W, wx = Math.cos(u * Math.PI * 2) * 6, wy = Math.sin(u * Math.PI * 2) * 6   // wraps seamlessly
      const turb = fbm(wx + 20, y / 18 + wy * .4)
      let v = 0.5 + 0.5 * Math.sin(y / H * Math.PI * 9 + turb * 5.5)
      v = Math.min(.999, Math.max(0, v * 0.75 + fbm(wx * 2 + 9, y / 9 + wy) * 0.35))
      const k = v * (pal.length - 1), i0 = Math.floor(k), t = k - i0, c0 = pal[i0], c1 = pal[Math.min(pal.length - 1, i0 + 1)], o = (y * W + x) * 4
      img.data[o] = c0[0] + (c1[0] - c0[0]) * t; img.data[o + 1] = c0[1] + (c1[1] - c0[1]) * t; img.data[o + 2] = c0[2] + (c1[2] - c0[2]) * t; img.data[o + 3] = 255
    }
    ctx.putImageData(img, 0, 0)
    if (pl.spot) for (const sx of [0.22, 0.72]) {  // GoFood's red storm, twice so one always faces you
      ctx.save(); ctx.translate(W * sx, H * .64); ctx.scale(2, 1)
      const g = ctx.createRadialGradient(0, 0, 1, 0, 0, 22); g.addColorStop(0, '#ffd1d6'); g.addColorStop(.25, pl.spot); g.addColorStop(.75, pl.spot + 'cc'); g.addColorStop(1, pl.spot + '00')
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, 22, 0, 7); ctx.fill(); ctx.restore()
    }
    return cv.toDataURL('image/jpeg', .9)
  }

  // Sphere wrap: a displacement map that bends a flat texture around a ball (orthographic projection).
  function sphereTexture() {
    const N = 256, cv = document.createElement('canvas'); cv.width = cv.height = N
    const ctx = cv.getContext('2d'), img = ctx.createImageData(N, N), SCALE = 0.5
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      const nx = (x + .5) / N * 2 - 1, ny = (y + .5) / N * 2 - 1, r2 = nx * nx + ny * ny, o = (y * N + x) * 4
      let dx = 0, dy = 0
      if (r2 < 1) { const nz = Math.sqrt(1 - r2), lon = Math.atan2(nx, nz) / (Math.PI / 2), lat = Math.asin(ny) / (Math.PI / 2)
        dx = (lon - nx) * 0.5 / SCALE; dy = (lat - ny) * 0.5 / SCALE }
      img.data[o] = 128 + dx * 255; img.data[o + 1] = 128 + dy * 255; img.data[o + 2] = 128; img.data[o + 3] = 255
    }
    ctx.putImageData(img, 0, 0)
    return cv.toDataURL('image/png')
  }

  // Clouds: soft white wisps with transparency, seamless horizontally.
  function cloudTexture(seed, density) {
    const W = 512, H = 256, cv = document.createElement('canvas'); cv.width = W; cv.height = H
    const ctx = cv.getContext('2d'), img = ctx.createImageData(W, H), n = noise2(seed)
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const u = x / W, wx = Math.cos(u * Math.PI * 2) * 5, wy = Math.sin(u * Math.PI * 2) * 5
      let v = 0, a = .5, f = 1; for (let o = 0; o < 5; o++) { v += a * n(wx * f + 40, (y / 22 + wy * .5) * f); a *= .5; f *= 2 }
      const al = Math.max(0, Math.min(1, (v - (1 - density)) * 3.2)), o = (y * W + x) * 4
      img.data[o] = img.data[o + 1] = img.data[o + 2] = 255; img.data[o + 3] = al * 255 * Math.sin(Math.PI * y / H)
    }
    ctx.putImageData(img, 0, 0); return cv.toDataURL('image/png')
  }
  // City lights for the night side: clustered warm points.
  function lightsTexture(seed, color) {
    const W = 512, H = 256, cv = document.createElement('canvas'); cv.width = W; cv.height = H
    const ctx = cv.getContext('2d'), n = noise2(seed); let r = seed
    const rnd = () => (r = (r * 16807) % 2147483647) / 2147483647
    for (let i = 0; i < 1400; i++) {
      const x = rnd() * W, y = H * (.15 + rnd() * .7), u = x / W
      if (n(Math.cos(u * 6.283) * 4 + 9, y / 26 + Math.sin(u * 6.283) * 2) < .55) continue
      const sz = .6 + rnd() * 1.3, g = ctx.createRadialGradient(x, y, 0, x, y, sz * 2.4)
      g.addColorStop(0, '#fffbe8'); g.addColorStop(.35, color); g.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = g; ctx.fillRect(x - sz * 3, y - sz * 3, sz * 6, sz * 6)
    }
    return cv.toDataURL('image/png')
  }

export function generateTextures() {
  const files = { 'sphere.png': sphereTexture() }
  MAJOR.forEach((pl, i) => {
    files[`${pl.key}-surface.jpg`] = surface(pl, 31 + i * 57)
    files[`${pl.key}-clouds.png`] = cloudTexture(77 + i * 13, pl.clouds ?? .42)
    if (pl.lights) files[`${pl.key}-lights.png`] = lightsTexture(5 + i, pl.lights)
  })
  STOPS.forEach((st, i) => {
    const base = hex(st.c), mix = (a, b, t) => '#' + a.map((v, k) => Math.round(v + (b[k] - v) * t).toString(16).padStart(2, '0')).join('')
    const palette = [mix(base, [4, 5, 12], .82), mix(base, [4, 5, 12], .55), st.c, mix(base, [255, 255, 255], .35), mix(base, [255, 255, 255], .75)]
    files[`mini-${st.mark}.jpg`] = surface({ palette }, 101 + i * 29)
  })
  return files
}
