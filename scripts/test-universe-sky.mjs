import { createSkyCulling } from '../site/js/universe-sky-culling.js'

export function testSkyCulling() {
  const assert = (value, message) => { if (!value) throw Error(message) }
  let enabled = true
  const scissors = []
  const texture = { width: 2000, height: 1200, createView: () => ({}) }
  const context = { getCurrentTexture: () => texture }
  const canvas = { getContext: () => context }
  const device = { createCommandEncoder: () => ({
    beginRenderPass: () => ({ setScissorRect: (...rect) => scissors.push(rect) }),
  }) }
  const culling = createSkyCulling(() => enabled)
  culling.register('sky', canvas)
  culling.attach(device)
  culling.attach(device)
  const view = canvas.getContext('webgpu').getCurrentTexture().createView()
  const draw = v => device.createCommandEncoder().beginRenderPass({ colorAttachments: [{ view: v }] })
  culling.setBounds('sky', { width: 1000, height: 600, scale: 1.6, x: 15, y: -20 })
  draw(view)
  const [x, y, w, h] = scissors[0]
  assert(scissors.length === 1 && x > 0 && y > 0 && x + w <= 2000 && y + h <= 1200, 'Scissor is bounded by the actual native attachment')
  assert(culling.status().sky.drawnFraction < .35, 'A magnified sky shades only its visible source area')
  draw({})
  assert(scissors.length === 1, 'Intermediate simulation and render-to-texture passes stay complete')
  enabled = false
  draw(view)
  assert(scissors.length === 1, 'Camera transitions keep the full sky source')
  enabled = true
  culling.invalidate()
  draw(view)
  assert(scissors.length === 1, 'Resize waits for newly measured bounds')
  culling.setBounds('sky', { width: 0, height: 600, scale: 1, x: 0, y: 0 })
  draw(view)
  assert(scissors.length === 1, 'Unknown bounds keep the original draw')
  const immutableTexture = Object.freeze({ width: 50, height: 50, createView: () => ({}) })
  const immutableContext = Object.freeze({ getCurrentTexture: () => immutableTexture })
  const fallback = { getContext: () => immutableContext }
  culling.register('fallback', fallback)
  assert(!!fallback.getContext('webgpu').getCurrentTexture().createView(), 'Immutable browser objects retain working full-quality rendering')
  const ctx = { getCurrentTexture: () => immutableTexture }
  const c = { getContext: () => ctx }
  culling.register('immutableTexture', c)
  assert(!!c.getContext('webgpu').getCurrentTexture().createView(), 'Immutable texture views retain working rendering')
  culling.attach(Object.freeze({ createCommandEncoder: device.createCommandEncoder }))
  return 'Passed: visible bounds, texture dimensions, simulation isolation, camera transitions, resize and native-object fallbacks'
}

export async function testSkyPixels() {
  const assert = (value, message) => { if (!value) throw Error(message) }
  const library = await import('../vendor/shaders.bundle.js')
  const gpu = await library.createSharedDevice()
  assert(!!gpu, 'Actual WebGPU is required for the pixel comparison')
  let enabled = false, handle, ready
  const culling = createSkyCulling(() => enabled)
  const fixture = document.createElement('div')
  fixture.style.cssText = 'position:fixed;left:0;top:0;width:1000px;height:600px;overflow:hidden;pointer-events:none;z-index:1000'
  const canvas = document.createElement('canvas')
  // Exact .layer bounds and CSS scaling used in the production scene. Force
  // the layout dimensions so vendor initialization cannot freeze scaled sizes.
  canvas.style.cssText = 'position:absolute;left:-4%;top:-4%;width:1080px!important;height:648px!important;transform:translate(15px,-20px) scale(1.6)'
  fixture.appendChild(canvas)
  document.body.appendChild(fixture)
  culling.register('aurora', canvas)
  culling.attach(gpu.device)
  culling.setBounds('aurora', { width: 1000, height: 600, scale: 1.6, x: 15, y: -20 })
  // Read the submitted texture itself. WebGPU presentation can discard the
  // backing image before ordinary drawImage()/toDataURL() snapshots read it.
  const context = canvas.getContext('webgpu'), targets = new WeakMap(), tagged = new WeakSet()
  const configure = context.configure.bind(context)
  context.configure = options => configure({ ...options, usage: (options.usage ?? GPUTextureUsage.RENDER_ATTACHMENT) | GPUTextureUsage.COPY_SRC })
  const getTexture = context.getCurrentTexture.bind(context)
  context.getCurrentTexture = () => {
    const texture = getTexture()
    if (!tagged.has(texture)) {
      tagged.add(texture)
      const createView = texture.createView.bind(texture)
      texture.createView = (...options) => { const view = createView(...options); targets.set(view, texture); return view }
    }
    return texture
  }
  let snapshot = null
  const nextPixels = () => new Promise((resolve, reject) => { snapshot = { resolve, reject } })
  const createEncoder = gpu.device.createCommandEncoder.bind(gpu.device)
  gpu.device.createCommandEncoder = (...options) => {
    const encoder = createEncoder(...options), beginPass = encoder.beginRenderPass.bind(encoder)
    encoder.beginRenderPass = descriptor => {
      const pass = beginPass(descriptor), texture = targets.get(descriptor.colorAttachments?.[0]?.view)
      if (!snapshot || !texture) return pass
      const request = snapshot; snapshot = null
      const width = texture.width, height = texture.height, bytesPerRow = Math.ceil(width * 4 / 256) * 256
      const buffer = gpu.device.createBuffer({ size: bytesPerRow * height, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ })
      const end = pass.end.bind(pass)
      pass.end = () => {
        end()
        encoder.copyTextureToBuffer({ texture }, { buffer, bytesPerRow }, [width, height])
        setTimeout(async () => {
          try {
            await buffer.mapAsync(GPUMapMode.READ)
            const source = new Uint8Array(buffer.getMappedRange()), pixels = new Uint8Array(width * height * 4)
            for (let row = 0; row < height; row++) pixels.set(source.subarray(row * bytesPerRow, row * bytesPerRow + width * 4), row * width * 4)
            request.resolve({ pixels, width, height })
          } catch (error) { request.reject(error) }
          finally { buffer.destroy() }
        }, 0)
      }
      return pass
    }
    return encoder
  }
  try {
    const presented = new Promise(resolve => { ready = resolve })
    handle = await library.createShader(canvas, { components: [{ type: 'Aurora', id: 'sky', props: {
      colorA: '#5a6bc4', colorB: '#8fdcc4', colorC: '#6f9fd6', balance: 50, intensity: 70, curtainCount: 4,
      speed: 0, waviness: 50, rayDensity: 22, height: 140, seed: 7,
    } }] }, { gpu, onReady: ready, disableTelemetry: true })
    await presented
    const baseline = await nextPixels(), full = baseline.pixels
    handle.pause()
    enabled = true
    const clippedPixels = nextPixels()
    handle.resume()
    const clipped = (await clippedPixels).pixels
    handle.pause()
    const { sourceRect, drawnFraction, passes } = culling.status().aurora
    assert(passes > 0, 'Actual GPU canvas pass must be clipped')
    const [x, y, w, h] = sourceRect
    let differences = 0, outsideDifferences = 0
    for (let row = 0; row < baseline.height; row++) for (let col = 0; col < baseline.width; col++) {
      const inside = col >= x && col < x + w && row >= y && row < y + h
      const p = (row * baseline.width + col) * 4
      const changed = full[p] !== clipped[p] || full[p + 1] !== clipped[p + 1] || full[p + 2] !== clipped[p + 2] || full[p + 3] !== clipped[p + 3]
      if (changed) { if (inside) differences++; else outsideDifferences++ }
    }
    assert(differences === 0 && outsideDifferences > 0, `Visible pixels must match; only invisible pixels can change (${differences}, ${outsideDifferences})`)
    return { visiblePixelDifferences: differences, skippedPixelChanges: outsideDifferences, drawnFraction }
  } finally {
    handle?.destroy()
    gpu.device.destroy()
    fixture.remove()
  }
}
