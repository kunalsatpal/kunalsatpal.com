// Full-quality shaders, initialized only when needed and paused by scene visibility.
// Keep the vendor renderer's resolution, timing and quality defaults unchanged.
export function createUniverseShaders(loadLibrary = () => import('../../vendor/shaders.bundle.js')) {
  const entries = new Map()
  let library, gpu, loading, draining = false, unavailable = false, generation = 0, recoveries = 0

  async function prepare() {
    if (!loading) loading = (async () => {
      library = await loadLibrary()
      const support = await library.getWebGPUSupport()
      if (!support.supported) { unavailable = true; return }
      gpu = await library.createSharedDevice()
      if (gpu) {
        const deviceGeneration = generation
        gpu.device.lost.then(() => {
          if (deviceGeneration !== generation) return
          generation++
          for (const entry of entries.values()) {
            entry.handle?.destroy()
            entry.handle = null
            entry.running = false
            entry.ready = false
            entry.failed = false
            entry.onReady?.(false)
          }
          gpu = null
          loading = null
          // Acquire a fresh device, rather than rebuilding against a lost shared device.
          if (++recoveries <= 2) void drain()
          else unavailable = true
        })
      }
    })().catch(error => {
      unavailable = true
      console.warn('[universe shaders]', error)
    })
    await loading
  }

  function apply(entry) {
    if (!entry.handle || entry.running === entry.wanted) return
    entry.running = entry.wanted
    if (entry.running) entry.handle.resume()
    else entry.handle.pause()
  }

  async function drain() {
    if (draining || unavailable) return
    draining = true
    try {
      await prepare()
      if (unavailable) return
      // One compilation at a time. Yield to input and painting between effects.
      for (const entry of entries.values()) {
        if (!entry.wanted || entry.handle || entry.failed) continue
        const currentGeneration = generation
        try {
          const handle = await library.createShader(entry.canvas, entry.definition, {
            gpu: gpu || undefined,
            onReady: () => {
              if (generation !== currentGeneration) return
              entry.ready = true
              entry.onReady?.(true)
            },
            onError: () => {
              entry.ready = false
              entry.onReady?.(false)
            },
          })
          if (generation !== currentGeneration) { handle.destroy(); continue }
          entry.handle = handle
          entry.running = true
          apply(entry) // Visibility may have changed while compilation was in flight.
        } catch (error) {
          entry.failed = true
          entry.onReady?.(false)
          console.warn(`[universe ${entry.name}]`, error)
        }
        await new Promise(resolve => setTimeout(resolve, 0))
      }
    } finally {
      draining = false
      if (!unavailable && [...entries.values()].some(e => e.wanted && !e.handle && !e.failed)) void drain()
    }
  }

  return {
    register(name, canvas, definition, onReady) {
      entries.set(name, { name, canvas, definition, onReady, wanted: false, handle: null, running: false, ready: false })
    },
    setActive(activeNames) {
      const active = new Set(activeNames)
      for (const entry of entries.values()) {
        entry.wanted = active.has(entry.name)
        apply(entry)
      }
      if ([...entries.values()].some(e => e.wanted && !e.handle && !e.failed)) void drain()
    },
    // Used by local regression checks; no UI or telemetry is added.
    status() {
      return Object.fromEntries([...entries].map(([name, e]) => [name, {
        wanted: e.wanted, initialized: !!e.handle, running: e.running, ready: e.ready,
      }]))
    },
  }
}
