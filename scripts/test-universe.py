"""Browser regression checks. See docs/universe-performance.md for setup.

Optional --baseline URL compares the generated textures byte-for-byte with the
original page's Canvas output in the same browser.
"""
import argparse
import base64
import hashlib
import json
import time
from pathlib import Path
from browser_tools import Browser

parser = argparse.ArgumentParser()
parser.add_argument('--baseline')
parser.add_argument('--output', default='/private/tmp/universe-checks')
args = parser.parse_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[1]
b = Browser()
b.call('Storage.clearDataForOrigin', {'origin':'http://127.0.0.1:8765', 'storageTypes':'local_storage'})
base = 'http://127.0.0.1:8765/universe.html'
checks = []

def check(condition, message):
    assert condition, message
    checks.append(message)

def wait_for(expression, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if b.js(expression):
            return
        time.sleep(.1)
    raise AssertionError('Timed out: ' + expression)

if args.baseline:
    b.navigate(args.baseline)
    urls = b.js("[...document.querySelectorAll('.surface,.clouds,.lights,.msurf')].map(e=>e.style.backgroundImage.slice(5,-2)).concat(document.querySelector('#sphere feImage').getAttribute('href'))")
    expected = {hashlib.sha256(base64.b64decode(url.split(',', 1)[1])).hexdigest() for url in urls}
    manifest = json.loads((root / 'site/textures/universe/manifest.json').read_text())
    actual = {hashlib.sha256((root / 'site/textures/universe' / name).read_bytes()).hexdigest() for name in manifest}
    check(len(urls) == 15 and expected == actual, 'All 15 textures exactly match the original browser-generated files')
    print(checks[-1], flush=True)

b.navigate(base + '?perf')
print(b.js("import('/scripts/test-universe-shaders.mjs').then(m=>m.testShaderLifecycle())"), flush=True)
for width, height, mobile in [(390, 844, True), (1440, 900, False)]:
    b.call('Emulation.setDeviceMetricsOverride', {'width':width, 'height':height, 'deviceScaleFactor':3 if mobile else 1, 'mobile':mobile})
    b.call('Emulation.setTouchEmulationEnabled', {'enabled':mobile})
    b.js("localStorage.removeItem('universeTheme')")
    b.navigate(base + '?perf')
    time.sleep(3)
    supported = b.js('navigator.gpu?.requestAdapter().then(a=>!!a) ?? false')
    if supported:
        wait_for("Object.values(universePerformance().shaders).every(s=>s.ready)")
        check(b.js('universePerformance().shaders.mark.running'), f'{width}: hero shader renders at full quality')
    b.screenshot(str(output / f'{width}-hero.png'))
    for index, key in enumerate(['hero','about','hinge','gojek','cult','galaxy','writing','life','hello']):
        b.js(f"scrollTo(0,({index}/8)*(document.getElementById('journey').offsetHeight-innerHeight))")
        wait_for(f"universePerformance().visibleScenes.includes('{key}')")
        check(b.js("[...document.querySelectorAll('.scene')].filter(e=>e.style.visibility==='hidden').every(e=>e.classList.contains('render-paused'))"), f'{width}: hidden animations pause at {key}')
        if key in ['hinge', 'galaxy']:
            b.screenshot(str(output / f'{width}-{key}.png'))
    if supported:
        check(b.js('!universePerformance().shaders.mark.running'), f'{width}: hero shader pauses after leaving hero')
    wait_for('!universePerformance().framePending')
    check(True, f'{width}: stationary contact scene releases the page animation loop')
    # An arbitrary resting position must resolve to a scene's exact presentation point.
    b.js("scrollTo(0,(2.42/8)*(document.getElementById('journey').offsetHeight-innerHeight))")
    wait_for("universePerformance().snap.phase === 'idle' && universePerformance().snap.settledIndex === 2")
    check(b.js("Math.abs(scrollY-(2/8)*(document.getElementById('journey').offsetHeight-innerHeight)) <= 2"), f'{width}: an in-between position settles exactly on Hinge Health')
    # Any wheel strength advances exactly one page; momentum events are swallowed.
    time.sleep(.4)
    b.call('Input.dispatchMouseEvent', {'type':'mouseWheel','x':width/2,'y':height/2,'deltaX':0,'deltaY':1400})
    for _ in range(5):
        b.call('Input.dispatchMouseEvent', {'type':'mouseWheel','x':width/2,'y':height/2,'deltaX':0,'deltaY':1400})
    wait_for("universePerformance().snap.phase === 'idle' && universePerformance().snap.settledIndex === 3")
    check(b.js("Math.abs(scrollY-(3/8)*(document.getElementById('journey').offsetHeight-innerHeight)) <= 2"), f'{width}: hard wheel momentum advances exactly one scene')
    # Route navigation can still jump directly to a requested scene.
    b.js("document.querySelector('.stop[data-i=\"7\"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    wait_for("universePerformance().snap.phase === 'idle' && universePerformance().snap.settledIndex === 7")
    check(b.js("Math.abs(scrollY-(7/8)*(document.getElementById('journey').offsetHeight-innerHeight)) <= 2"), f'{width}: route navigation lands on its exact requested scene')
    if mobile:
        # A strong swipe is also consumed and paginated by one scene.
        b.js("scrollTo(0,(3/8)*(document.getElementById('journey').offsetHeight-innerHeight))")
        wait_for("universePerformance().snap.phase === 'idle' && universePerformance().snap.settledIndex === 3")
        time.sleep(.4)
        b.call('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':width/2,'y':height*.7,'id':1}]})
        b.call('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':width/2,'y':height*.15,'id':1}]})
        b.call('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        wait_for("universePerformance().snap.phase === 'idle' && universePerformance().snap.settledIndex === 4")
        check(b.js("Math.abs(scrollY-(4/8)*(document.getElementById('journey').offsetHeight-innerHeight)) <= 2"), 'A hard mobile swipe advances exactly one scene')
    b.js("document.getElementById('styleToggle').click()")
    time.sleep(1)
    check(b.js("document.documentElement.classList.contains('theme-toon') && document.documentElement.classList.contains('settled')"), f'{width}: cartoon transition completes')
    check(b.js("!universePerformance().shaders.aurora.running && !universePerformance().shaders.far.running"), f'{width}: hidden realistic sky stops in cartoon theme')
    b.js("document.getElementById('skipBtn').click()")
    check(b.js('universePerformance().suspended && !universePerformance().framePending'), f'{width}: opaque overview stops page frame loop')
    check(b.js('Object.values(universePerformance().shaders).every(s=>!s.running)'), f'{width}: overview pauses all shaders')
    b.js("document.getElementById('backToFlight').click()")
    wait_for('!universePerformance().suspended')
    b.js("document.getElementById('styleToggle').click()")
    time.sleep(1)
    if supported:
        check(b.js('universePerformance().shaders.aurora.running && universePerformance().shaders.far.running'), f'{width}: realistic sky resumes after theme switch')
    b.js("document.querySelector('nav [data-go=\"about\"]').click()")
    wait_for("universePerformance().visibleScenes.includes('about')")
    time.sleep(3)
    b.call('Emulation.setDeviceMetricsOverride', {'width':width, 'height':height-100, 'deviceScaleFactor':3 if mobile else 1, 'mobile':mobile})
    time.sleep(.3)
    check(b.js("(()=>{const c=document.getElementById('hatcanvas');return c.height===Math.round(c.offsetHeight*Math.min(2,devicePixelRatio))})()"), f'{width}: constellation canvas follows height-only resize')
    # Exercise the page lifecycle used for pagehide/pageshow and BFCache restoration.
    b.js("dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}))")
    check(b.js('universePerformance().suspended'), f'{width}: pagehide pauses rendering')
    b.js("dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
    wait_for('!universePerformance().suspended')
    errors = [e for e in b.events if e.get('method') == 'Runtime.exceptionThrown']
    check(not errors, f'{width}: no uncaught browser errors')
    print(f'Passed viewport {width}x{height}', flush=True)

b.js("localStorage.removeItem('universeTheme')")
b.navigate(base + '?scene=hinge&theme=toon&perf')
wait_for("universePerformance().visibleScenes.includes('hinge')")
time.sleep(.5)
check(b.js('Object.values(universePerformance().shaders).every(s=>!s.initialized)'), 'Direct cartoon scene does not initialize invisible shaders')
check(b.js("!performance.getEntriesByType('resource').some(r=>r.name.includes('shaders.bundle.js'))"), 'Direct cartoon scene skips the unused shader bundle')
b.js("document.getElementById('styleToggle').click()")
if supported:
    wait_for('universePerformance().shaders.aurora.ready && universePerformance().shaders.far.ready')
check(b.js("!document.documentElement.classList.contains('theme-toon')"), 'Realistic theme can initialize lazily after a direct cartoon entry')
assets = b.js("performance.getEntriesByType('resource').filter(r=>r.name.includes('/site/textures/')).map(r=>({name:r.name,status:r.responseStatus}))")
check(all(a['status'] in (200,304) for a in assets), 'Generated texture requests succeed')
b.js("localStorage.removeItem('universeTheme')")
b.navigate(base + '?scene=gojek&perf')
wait_for("universePerformance().visibleScenes.includes('gojek')")
b.js("document.querySelector('[data-scene=gojek] .moon.open').click()")
time.sleep(1.5)
wait_for("location.pathname.endsWith('/case.html')")
history = b.call('Page.getNavigationHistory')
entry = history['entries'][history['currentIndex'] - 1]
b.call('Page.navigateToHistoryEntry', {'entryId':entry['id']})
time.sleep(1)
wait_for("!!window.universePerformance && !universePerformance().suspended && universePerformance().visibleScenes.includes('gojek')")
check(b.js("document.body.style.opacity !== '0' && document.getElementById('camera').style.filter === ''"), 'Actual case-study navigation and browser Back restore the flight')

# Project previews keep the complete image prominent and strip redundant badge copy.
preview = b.js("""(() => {
  const tip = document.querySelector('[data-scene=gojek] .moon.open .tip.big')
  const image = tip.querySelector('img')
  const ir = image.getBoundingClientRect()
  return { imageWidth: image.offsetWidth, tipWidth: tip.clientWidth, renderedRatio: ir.width / ir.height,
    naturalRatio: image.naturalWidth / image.naturalHeight,
    result: tip.querySelector('.tip-result')?.textContent,
    redundantTags: tip.querySelectorAll('.tip-k,.tip-go').length }
})()""")
check(preview['imageWidth'] == preview['tipWidth'], 'Hover preview image spans the full card content width')
check(abs(preview['renderedRatio'] - preview['naturalRatio']) < .02, 'Hover preview shows the complete image without cropping')
check(preview['result'] == '+4% conversions · 5× ad revenue', 'Hover preview includes the final result numbers without a label')
check(preview['redundantTags'] == 0, 'Hover preview omits redundant company and action tags')

b.call('Page.navigate', {'url':'http://127.0.0.1:8765/case.html?c=promo'})
wait_for("document.querySelectorAll('.nextmoon').length === 2")
cards = b.js("""[...document.querySelectorAll('.nextmoon')].map(card => {
  const image = card.querySelector('.nm-cover')
  return { imageWidth: image.offsetWidth, cardWidth: card.clientWidth, src: image.getAttribute('src'),
    redundantTags: card.querySelectorAll('.nm-k,.nm-go,.nm-planet').length }
})""")
check(all(abs(card['imageWidth'] - card['cardWidth']) < 1 for card in cards), 'Case-study footer images span the full card width')
check(all(card['redundantTags'] == 0 for card in cards), 'Case-study footer cards omit decorative tags')

b.call('Emulation.setDeviceMetricsOverride', {'width':390, 'height':844, 'deviceScaleFactor':3, 'mobile':True})
clamped = []
for scene in ('gojek', 'cult'):
    b.navigate(base + f'?scene={scene}&perf')
    wait_for("[...document.querySelectorAll('.moon.open .tip-img img')].every(image => image.complete)")
    clamped += b.js("""(async () => {
      const results = []
      for (const moon of document.querySelectorAll('.moon.open')) {
        moon.dispatchEvent(new PointerEvent('pointerenter'))
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
        const r = moon.querySelector('.tip.big').getBoundingClientRect()
        results.push({ left:r.left, top:r.top, right:r.right, bottom:r.bottom })
        moon.dispatchEvent(new PointerEvent('pointerleave'))
      }
      return results
    })()""")
check(all(r['left'] >= 11 and r['top'] >= 11 and r['right'] <= 379 and r['bottom'] <= 833 for r in clamped), 'Phone hover previews stay inside every viewport edge')

b.navigate(base + '?scene=galaxy&perf')
wait_for("[...document.querySelectorAll('.mbadge img')].every(image => image.complete)")
badges = b.js("""[...document.querySelectorAll('.mbadge')].map(badge => {
  const image = badge.querySelector('img'), b = badge.getBoundingClientRect(), i = image.getBoundingClientRect()
  return i.left >= b.left && i.top >= b.top && i.right <= b.right && i.bottom <= b.bottom && getComputedStyle(image).objectFit === 'contain'
})""")
check(len(badges) == 7 and all(badges), 'Every company logo fits inside its badge safe area')

b.navigate(base + '?scene=writing&perf')
wait_for("document.querySelectorAll('.log').length === 4")
notes = b.js("""[...document.querySelectorAll('.log')].map(note => ({
  fresh: !!note.querySelector('.log-new'),
  icon: note.querySelector('.patch img').getAttribute('src'),
  fit: getComputedStyle(note.querySelector('.patch img')).objectFit,
  background: getComputedStyle(note.querySelector('.patch')).backgroundColor,
  filter: getComputedStyle(note.querySelector('.patch img')).filter
}))""")
check(notes[0]['fresh'] and notes[0]['icon'] == './mark.svg' and notes[0]['fit'] == 'contain', 'First field note carries the Kunal Satpal mark and New tag')
check(notes[2]['icon'] == './site/img/marks/pibit.png' and notes[2]['fit'] == 'contain' and notes[2]['background'] == 'rgb(76, 99, 239)' and notes[2]['filter'] == 'brightness(0) invert(1)', 'Pibit field note uses the white mark on a blue badge')

# Legacy incoming URLs may still carry the old home parameter; every return action is canonicalized to Universe.
b.call('Page.navigate', {'url':'http://127.0.0.1:8765/case.html?c=promo&home=cinematic-proof'})
wait_for("document.readyState === 'complete' && document.querySelectorAll('.nextmoon').length === 2")
b.js("document.getElementById('back').click()")
wait_for("location.pathname.endsWith('/universe.html') && !!document.querySelector('[data-scene=\"gojek\"]') && document.querySelector('[data-scene=\"gojek\"]').style.visibility !== 'hidden'")
check(True, 'Case-study Back to orbit returns to the matching Universe scene')

b.call('Page.navigate', {'url':'http://127.0.0.1:8765/blog.html?c=Pibit&home=cinematic-proof'})
wait_for("document.readyState === 'complete' && document.getElementById('title').textContent.length > 0")
b.js("document.getElementById('back').click()")
wait_for("location.pathname.endsWith('/universe.html') && !!document.querySelector('[data-scene=\"writing\"]') && document.querySelector('[data-scene=\"writing\"]').style.visibility !== 'hidden'")
check(True, 'Field-note Back to orbit returns to the Universe writing scene')
(output / 'results.json').write_text(json.dumps({'checks':checks,'assets':assets}, indent=2) + '\n')
print(f'Passed {len(checks)} browser checks. Screenshots and report: {output}', flush=True)
