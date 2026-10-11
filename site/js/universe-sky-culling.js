// Keep the original shader coordinates, resolution and simulation. Scissor only
// the final canvas pass: CSS enlarges these layers beyond the stage's clip, so
// shading pixels outside that clip cannot contribute to the displayed image.
export function createSkyCulling(canCull = () => true) {
  const entries = new Map(), views = new WeakMap(), contexts = new WeakSet()
  const devices = new WeakSet(), textures = new WeakSet()

  function register(name, canvas) {
    const entry = { name, bounds: null, passes: 0, fraction: 1, rect: null, size: null }
    entries.set(name, entry)
    const getContext = canvas.getContext.bind(canvas)
    // Adapt only these two canvas instances and our shared device. Never change
    // WebGPU prototypes or the vendor bundle. All returned GPU objects stay real
    // native objects, including the device passed to canvas.configure().
    try {
      canvas.getContext = (...args) => {
        const context = getContext(...args)
        if (args[0] !== 'webgpu' || !context || contexts.has(context)) return context
        contexts.add(context)
        const getTexture = context.getCurrentTexture.bind(context)
        const clippedTexture = () => {
          const texture = getTexture()
          if (!textures.has(texture)) {
            textures.add(texture)
            const createView = texture.createView.bind(texture)
            const taggedView = (...options) => {
              const view = createView(...options)
              views.set(view, { entry, width: texture.width, height: texture.height })
              return view
            }
            try { texture.createView = taggedView } catch { /* Full draw on immutable native objects. */ }
          }
          return texture
        }
        try { context.getCurrentTexture = clippedTexture } catch { /* Full draw on immutable native objects. */ }
        return context
      }
    } catch {
      // Browsers that disallow instance adapters keep the original full draw.
    }
  }

  function attach(device) {
    if (!device || devices.has(device)) return
    devices.add(device)
    const createEncoder = device.createCommandEncoder.bind(device)
    try {
      device.createCommandEncoder = (...options) => {
        const encoder = createEncoder(...options)
        const beginPass = encoder.beginRenderPass.bind(encoder)
        try {
          encoder.beginRenderPass = descriptor => {
            const pass = beginPass(descriptor)
            // Intermediate particle textures and compute passes must remain
            // complete. Clip only a sole, directly presented canvas attachment.
            const attachments = descriptor.colorAttachments?.filter(Boolean)
            const target = attachments?.length === 1 && views.get(attachments[0].view)
            if (!target || !canCull() || !target.entry.bounds || !pass.setScissorRect) return pass
            const { entry, width, height } = target
            const [left, top, right, bottom] = entry.bounds
            // Outward rounding plus two source pixels protects bilinear sampling
            // at viewport edges. Read dimensions from this frame's GPU texture,
            // not a potentially stale canvas size during resize.
            const x = Math.max(0, Math.floor(left * width) - 2)
            const y = Math.max(0, Math.floor(top * height) - 2)
            const endX = Math.min(width, Math.ceil(right * width) + 2)
            const endY = Math.min(height, Math.ceil(bottom * height) + 2)
            pass.setScissorRect(x, y, Math.max(0, endX - x), Math.max(0, endY - y))
            entry.passes++
            entry.fraction = (endX - x) * (endY - y) / (width * height)
            entry.rect = [x, y, endX - x, endY - y]
            entry.size = [width, height]
            return pass
          }
        } catch {
          // No adapter support on this encoder: use the untouched full pass.
        }
        return encoder
      }
    } catch {
      // No adapter support on this device: render at the original full quality.
    }
  }

  function setBounds(name, { width, height, scale, x, y }) {
    const entry = entries.get(name)
    if (!entry) return
    if (![width, height, scale, x, y].every(Number.isFinite) || width <= 0 || height <= 0 || scale < 1) {
      entry.bounds = null
      return
    }
    // .layer uses inset:-4%, centred scaling, then translation. The stage and
    // its sky wrapper share these untransformed bounds. No layout reads per RAF.
    const w = width * 1.08 * scale, h = height * 1.08 * scale
    const left = (width - w) / 2 + x, top = (height - h) / 2 + y
    const clamp = value => Math.max(0, Math.min(1, value))
    entry.bounds = [clamp(-left / w), clamp(-top / h), clamp((width - left) / w), clamp((height - top) / h)]
  }

  return { register, attach, setBounds,
    invalidate() { for (const entry of entries.values()) entry.bounds = null },
    // Diagnostics measure fragment area skipped, not GPU timing or frame rate.
    status: () => Object.fromEntries([...entries].map(([name, entry]) => [name, {
      passes: entry.passes, drawnFraction: entry.fraction, sourceRect: entry.rect, textureSize: entry.size,
    }])),
  }
}
