import { createUniverseShaders } from '../site/js/universe-shaders.js'

export async function testShaderLifecycle() {
  const assert = (condition, message) => { if (!condition) throw Error(message) }
  const tick = () => new Promise(resolve => setTimeout(resolve, 10))
  let release, creates = 0, pauses = 0, resumes = 0, loads = 0
  const controller = createUniverseShaders(async () => {
    loads++
    return {
      getWebGPUSupport: async () => ({ supported: true }),
      createSharedDevice: async () => null,
      createShader: async () => {
        creates++
        await new Promise(resolve => { release = resolve })
        return { pause: () => pauses++, resume: () => resumes++, destroy() {} }
      },
    }
  })
  controller.register('mark', {}, {})
  controller.setActive([])
  await tick()
  assert(loads === 0, 'An invisible effect must not load the shader bundle')
  controller.setActive(['mark'])
  controller.setActive(['mark'])
  await tick()
  assert(creates === 1, 'Repeated updates must not start duplicate shader compilations')
  controller.setActive([])
  release()
  await tick()
  assert(pauses === 1 && !controller.status().mark.running, 'Hide during compilation must pause the completed renderer')
  controller.setActive(['mark'])
  controller.setActive(['mark'])
  assert(resumes === 1 && creates === 1, 'Returning to a scene must reuse its renderer')
  controller.setActive([])
  assert(pauses === 2, 'Leaving a visible scene must stop its renderer')

  let unsupportedCreates = 0
  const unsupported = createUniverseShaders(async () => ({
    getWebGPUSupport: async () => ({ supported: false }),
    createShader: () => unsupportedCreates++,
  }))
  unsupported.register('mark', {}, {})
  unsupported.setActive(['mark'])
  await tick()
  assert(unsupportedCreates === 0, 'Unsupported GPU must retain the existing fallback')

  let lost, devices = 0, destroyed = 0, recoverCreates = 0
  const recovered = createUniverseShaders(async () => ({
    getWebGPUSupport: async () => ({ supported: true }),
    createSharedDevice: async () => ({ device: { lost: new Promise(resolve => { lost = resolve; devices++ }) } }),
    createShader: async () => { recoverCreates++; return { pause() {}, resume() {}, destroy() { destroyed++ } } },
  }))
  recovered.register('sky', {}, {})
  recovered.setActive(['sky'])
  await tick()
  lost({ reason: 'unknown' })
  await tick()
  await tick()
  assert(devices === 2 && destroyed === 1 && recoverCreates === 2, 'Device loss must reacquire and rebuild against a fresh device')
  assert(recovered.status().sky.running, 'Visible shader must resume after recovery')
  return 'Passed: lazy loading, compilation races, renderer reuse, GPU fallback and shared-device recovery'
}
