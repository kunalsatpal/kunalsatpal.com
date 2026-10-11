// Replace three repeatedly painted SVG-filtered backgrounds with one small GPU
// pass. The original displacement map and CSS shade/atmosphere remain intact.
const vertex = `
attribute vec2 position;
varying vec2 uv;
void main() {
  uv = vec2(position.x * .5 + .5, .5 - position.y * .5);
  gl_Position = vec4(position, 0., 1.);
}`
const fragment = `
precision highp float;
varying vec2 uv;
uniform sampler2D sphereMap, surfaceMap, cloudMap, lightMap;
uniform vec2 phase;
uniform float hasLights;
void main() {
  vec2 source = uv + .5 * (texture2D(sphereMap, uv).rg - .5);
  // SVG SourceGraphic ends at the element boundary even though its background
  // repeats. Keep that boundary rather than wrapping displaced edge pixels.
  if (any(lessThan(source, vec2(0.))) || any(greaterThan(source, vec2(1.)))) {
    gl_FragColor = vec4(0.); return;
  }
  vec2 st = vec2(source.x * .5 + phase.x, source.y);
  vec3 color = texture2D(surfaceMap, st).rgb;
  vec4 cloud = texture2D(cloudMap, vec2(source.x * .5 + phase.y, source.y));
  // CSS screen blend in sRGB, including each layer's original opacity.
  color += (1. - color) * cloud.rgb * cloud.a * .55;
  vec4 lights = texture2D(lightMap, st);
  float night = clamp((length(uv - vec2(.28, .24)) / length(vec2(.72, .76)) - .46) / .28, 0., 1.);
  color += (1. - color) * lights.rgb * lights.a * .95 * night * hasLights;
  gl_FragColor = vec4(color, 1.);
}`

export function createPlanetSurfaces({ sphereURL, wake = () => {} }) {
  const images = new Map(), entries = []
  const image = url => {
    if (!images.has(url)) {
      const img = new Image()
      img.decoding = 'async'
      img.src = url
      images.set(url, img.decode().then(() => img))
    }
    return images.get(url)
  }

  function register({ planet, surfaceURL, cloudURL, lightURL, spin }) {
    const canvas = document.createElement('canvas')
    canvas.className = 'planet-surface'
    canvas.setAttribute('aria-hidden', 'true')
    planet.insertBefore(canvas, planet.querySelector('.shade'))
    const entry = { planet, canvas, ready: false, failed: false, loading: null,
      gl: null, program: null, buffer: null, textures: [], size: 0, width: 0,
      draws: 0, lastTime: 0, generation: 0 }
    entries.push(entry)
    let phaseLocation, lightsLocation
    const release = () => {
      const gl = entry.gl
      if (!gl || gl.isContextLost()) return
      entry.textures.forEach(texture => gl.deleteTexture(texture))
      if (entry.buffer) gl.deleteBuffer(entry.buffer)
      if (entry.program) gl.deleteProgram(entry.program)
      entry.textures = []; entry.buffer = null; entry.program = null
    }
    const fallback = () => {
      entry.ready = false
      if (entry.width) {
        const period = entry.width * 2
        const offset = `${-(entry.lastTime / 1000 * spin) % period}px`
        planet.querySelector('.surface').style.backgroundPositionX = offset
        const lights = planet.querySelector('.lights')
        if (lights) lights.style.backgroundPositionX = offset
        planet.querySelector('.clouds').style.backgroundPositionX = `${-(entry.lastTime / 1000 * spin * 1.45) % period}px`
      }
      planet.classList.remove('gpu-ready')
      wake()
    }
    const shader = (gl, type, source) => {
      const value = gl.createShader(type)
      gl.shaderSource(value, source); gl.compileShader(value)
      if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) {
        gl.deleteShader(value); throw new Error('Planet shader compilation failed')
      }
      return value
    }
    function load() {
      if (entry.loading || entry.ready || entry.failed) return entry.loading
      const generation = entry.generation
      entry.loading = (async () => {
        try {
          const assets = await Promise.all([image(sphereURL), image(surfaceURL), image(cloudURL),
            lightURL ? image(lightURL) : null])
          if (generation !== entry.generation) return
          const gl = entry.gl || canvas.getContext('webgl', { alpha: true, antialias: false,
            depth: false, stencil: false, premultipliedAlpha: true })
          if (!gl || gl.isContextLost()) throw new Error('Planet GPU unavailable')
          entry.gl = gl
          const vs = shader(gl, gl.VERTEX_SHADER, vertex), fs = shader(gl, gl.FRAGMENT_SHADER, fragment)
          const program = gl.createProgram()
          entry.program = program
          gl.attachShader(program, vs); gl.attachShader(program, fs); gl.linkProgram(program)
          gl.deleteShader(vs); gl.deleteShader(fs)
          if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Planet GPU link failed')
          gl.useProgram(program)
          const buffer = gl.createBuffer(); entry.buffer = buffer
          gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
          const position = gl.getAttribLocation(program, 'position')
          gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)
          gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE)
          for (let i = 0; i < assets.length; i++) {
            const texture = gl.createTexture(); entry.textures.push(texture)
            gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, texture)
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, i ? gl.REPEAT : gl.CLAMP_TO_EDGE)
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
            if (assets[i]) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, assets[i])
            else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4))
            gl.uniform1i(gl.getUniformLocation(program, ['sphereMap', 'surfaceMap', 'cloudMap', 'lightMap'][i]), i)
          }
          phaseLocation = gl.getUniformLocation(program, 'phase')
          lightsLocation = gl.getUniformLocation(program, 'hasLights')
          gl.uniform1f(lightsLocation, lightURL ? 1 : 0)
          if (gl.getError() !== gl.NO_ERROR) throw new Error('Planet texture upload failed')
          entry.ready = true
          // Hand off only after a complete frame exists; no blank canvas flash.
          render(entry.lastTime)
          wake()
        } catch {
          entry.failed = true; release(); fallback()
        } finally {
          if (generation === entry.generation) entry.loading = null
        }
      })()
      return entry.loading
    }
    function resize(width) {
      entry.width = width
      const size = Math.max(1, Math.ceil(width * devicePixelRatio))
      if (size === entry.size) return
      entry.size = size
      canvas.width = canvas.height = size
      if (entry.ready) render(entry.lastTime)
    }
    function render(time) {
      entry.lastTime = time
      if (!entry.ready || !entry.width) return false
      const gl = entry.gl
      gl.viewport(0, 0, canvas.width, canvas.height)
      const period = entry.width * 2
      const offset = (time / 1000 * spin) % period / period
      const cloudOffset = (time / 1000 * spin * 1.45) % period / period
      gl.uniform2f(phaseLocation, offset, cloudOffset)
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
      entry.draws++
      if (!planet.classList.contains('gpu-ready')) planet.classList.add('gpu-ready')
      return true
    }
    canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault()
      entry.generation++; entry.loading = null
      entry.textures = []; entry.program = null; entry.buffer = null
      fallback()
    })
    canvas.addEventListener('webglcontextrestored', () => {
      entry.failed = false
      load()
    })
    return { load, resize, render }
  }
  return { register, status: () => entries.map(e => ({ key: e.planet.closest('[data-planet]')?.dataset.planet,
    ready: e.ready, failed: e.failed, draws: e.draws, size: e.size })) }
}
