"""Cold mobile startup checks; use the browser/server setup in docs/universe-performance.md."""
import argparse
import json
import time
from pathlib import Path
from browser_tools import Browser

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', help='Optional before-change URL')
parser.add_argument('--output', default='/tmp/universe-startup-checks')
args = parser.parse_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
b = Browser(new_tab=True)
base = 'http://127.0.0.1:8765/universe.html?perf'
checks = []

def check(value, label):
    assert value, label
    checks.append(label)
    print(label, flush=True)

def wait(expression, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if b.js(expression):
            return
        time.sleep(.1)
    raise AssertionError('Timed out: ' + expression)

b.call('Emulation.setDeviceMetricsOverride', {'width':390, 'height':844, 'deviceScaleFactor':3, 'mobile':True})
b.call('Emulation.setTouchEmulationEnabled', {'enabled':True})
b.call('Emulation.setEmulatedMedia', {'features':[]})
b.call('Storage.clearDataForOrigin', {'origin':'http://127.0.0.1:8765', 'storageTypes':'local_storage'})
b.call('Page.addScriptToEvaluateOnNewDocument', {'source': '''
(() => {
window.startupProbe = {heroVisibleAt:null, shifts:[], longTasks:[], frames:[], errors:[]};
addEventListener('error', e => startupProbe.errors.push(e.message || 'resource failed'), true);
new PerformanceObserver(list => list.getEntries().forEach(e => {
  if (!e.hadRecentInput) startupProbe.shifts.push({at:e.startTime, value:e.value});
})).observe({type:'layout-shift', buffered:true});
new PerformanceObserver(list => list.getEntries().forEach(e => {
  startupProbe.longTasks.push({at:e.startTime, duration:e.duration});
})).observe({type:'longtask', buffered:true});
let last, sampleStart;
function sample(t) {
  sampleStart ??= t;
  if (last && t-sampleStart < 5000) startupProbe.frames.push(t-last);
  last=t;
  if (!startupProbe.heroVisibleAt) {
    const h=document.querySelector('h1');
    if (h) {
      let opacity=1;
      for(let el=h;el;el=el.parentElement) opacity*=Number(getComputedStyle(el).opacity);
      if(opacity>.5 && h.getBoundingClientRect().height>0) startupProbe.heroVisibleAt=t;
    }
  }
  if(t-sampleStart<10000) requestAnimationFrame(sample);
}
requestAnimationFrame(sample);
})();
'''})

def measure(url, name):
    b.call('Network.clearBrowserCache')
    b.call('Page.navigate', {'url':url})
    wait('location.href === '+json.dumps(url))
    wait('!!window.universePerformance')
    wait('startupProbe.heroVisibleAt !== null')
    wait('performance.now() > 10000', 30)
    b.screenshot(str(output / (name+'.png')))
    data = b.js('''(()=>{
      const frames=startupProbe.frames.slice().sort((a,b)=>a-b);
      return {...startupProbe,
        frameP95:frames[Math.floor(frames.length*.95)],
        paints:performance.getEntriesByType('paint').map(e=>({name:e.name,at:e.startTime})),
        resources:performance.getEntriesByType('resource').map(e=>({name:e.name,start:e.startTime,bytes:e.transferSize})),
        shiftsTotal:startupProbe.shifts.reduce((s,e)=>s+e.value,0),
        images:[...document.querySelectorAll('.proof img')].map(e=>({loaded:e.complete&&e.naturalWidth>0,width:e.width,height:e.height})),
        shaders:universePerformance().shaders,
      };
    })()''')
    (output / (name+'.json')).write_text(json.dumps(data, indent=2))
    print(json.dumps({'sample':name,'heroVisibleMs':data['heroVisibleAt'],'layoutShift':data['shiftsTotal'],'frameP95Ms':data.get('frameP95'),'requests':len(data['resources'])}),flush=True)
    return data

b.call('Network.emulateNetworkConditions', {'offline':False,'latency':150,'downloadThroughput':200000,'uploadThroughput':75000,'connectionType':'cellular4g'})
b.call('Emulation.setCPUThrottlingRate', {'rate':4})
results = {}
if args.baseline:
    results['before'] = measure(args.baseline, 'before')
results['after'] = measure(base, 'after')
after = results['after']
check(all(i['loaded'] for i in after['images']), 'Cold mobile load: no broken hero images')
check(not any('/site/img/proof_' in r['name'] for r in after['resources']), 'Cold mobile load: hidden desktop artwork is not downloaded')
check(not after['errors'], 'Cold mobile load: no JavaScript or asset errors')
check(not any('/textures/universe/' in r['name'] or '/cases/media/phone_' in r['name'] for r in after['resources']), 'Cold mobile load: distant textures and moon previews are not requested')
check(after['shiftsTotal'] < .05, 'Cold mobile load: no material layout or font jumps')
check(b.js("document.querySelectorAll('[data-scene=hero]').length===1 && document.querySelectorAll('#object').length===1"), 'Static hero is reused without duplicate markup')

# Static markup must remain readable if the application module cannot start.
b.call('Network.setBlockedURLs', {'urls':['*universe-data.js*']})
b.call('Page.navigate', {'url':base})
wait("!!document.querySelector('h1') && getComputedStyle(document.querySelector('h1')).opacity==='1'")
check(b.js("document.querySelector('h1').textContent.includes('Crafting') && getComputedStyle(document.querySelector('[data-scene=hero]')).opacity==='1' && getComputedStyle(document.querySelector('.fallback')).opacity==='1'"), 'Blocked application module: hero and logo remain visible')
b.screenshot(str(output / 'static-hero.png'))
b.js('scrollTo(0,200)')
check(b.js('scrollY>0'), 'Before application startup: native scrolling remains available')
b.call('Page.navigate', {'url':base+'&scene=cult'})
wait("!!document.querySelector('[data-scene=hero]')")
check(b.js("getComputedStyle(document.querySelector('[data-scene=hero]')).opacity==='0'"), 'Direct scene startup does not flash the static hero')
b.call('Network.setBlockedURLs', {'urls':[]})

# Scroll while GPU effects are still loading; never hold input behind the intro.
b.call('Network.clearBrowserCache')
b.call('Page.navigate', {'url':base})
wait('!!window.universePerformance')
start = b.js('performance.now()')
b.call('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':195,'y':650,'id':1}]})
b.call('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':195,'y':200,'id':1}]})
b.call('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
wait("universePerformance().snap.settledIndex===1 && universePerformance().snap.phase==='idle'")
check(b.js('scrollY>0'), 'Immediate mobile swipe reaches About during startup')
results['immediateSwipeMs'] = b.js('performance.now()')-start
# Approaching Gojek loads its assets, while the farther galaxy stays deferred.
b.js("document.querySelector('.stop[data-i=\"3\"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
wait("universePerformance().snap.settledIndex===3 && universePerformance().snap.phase==='idle'")
wait("[...document.querySelectorAll('[data-scene=gojek] .tip img')].every(i=>i.complete&&i.naturalWidth>0)")
check(b.js("!!document.querySelector('[data-planet=gojek] .surface').style.backgroundImage && document.querySelector('.msurf').style.backgroundImage===''") ,'Approaching a planet loads its textures and preview, leaving distant galaxy assets deferred')

# A GPU failure must leave the original logo intact.
b.call('Emulation.setCPUThrottlingRate', {'rate':1})
b.call('Network.emulateNetworkConditions', {'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
b.call('Network.setBlockedURLs', {'urls':['*shaders.bundle.js*']})
b.call('Page.navigate', {'url':base})
wait('!!window.universePerformance')
time.sleep(1.5)
check(b.js("getComputedStyle(document.querySelector('.fallback')).opacity==='1' && !document.querySelector('#object').classList.contains('live')"), 'Unavailable shader: fallback logo stays visible')
b.call('Network.setBlockedURLs', {'urls':[]})
# Also check a direct scene entry and both themes.
for query in ['scene=cult', 'scene=gojek&theme=toon']:
    b.call('Page.navigate', {'url':base+'&'+query})
    wait('!!window.universePerformance')
    wait("!!document.querySelector('.scene.active .system .surface')?.style.backgroundImage")
    check(True, 'Direct scene entry hydrates destination assets: '+query)
b.call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
b.call('Page.navigate', {'url':base})
wait('!!window.universePerformance')
check(b.js("getComputedStyle(document.querySelector('h1')).animationName==='none' && getComputedStyle(document.querySelector('.proof')).animationName==='none'"), 'Reduced motion skips the entrance animations')
b.call('Emulation.setEmulatedMedia', {'features':[]})
# Desktop artwork is eager, and the real renderer takes over only after readiness.
b.call('Emulation.setDeviceMetricsOverride', {'width':1440,'height':900,'deviceScaleFactor':1,'mobile':False})
b.call('Emulation.setTouchEmulationEnabled', {'enabled':False})
b.call('Page.navigate', {'url':base})
wait('!!window.universePerformance')
wait("[...document.querySelectorAll('.proof img')].every(i=>i.complete&&i.naturalWidth>1)")
wait("[...document.querySelectorAll('.proof')].every(c=>c.classList.contains('image-ready')&&getComputedStyle(c).opacity==='1')")
check(b.js("[...document.querySelectorAll('.proof img')].every(i=>i.currentSrc.includes('/site/img/proof_'))"), 'Desktop hero: all four original artwork images load')
supported = b.js('navigator.gpu?.requestAdapter().then(a=>!!a) ?? false')
if supported:
    wait('universePerformance().shaders.mark.ready', 30)
    wait("getComputedStyle(document.querySelector('#object canvas')).opacity==='1' && getComputedStyle(document.querySelector('.fallback')).opacity==='0'")
    check(b.js("getComputedStyle(document.querySelector('.fallback')).opacity==='0'"), 'Rendered shader crossfades in and replaces the fallback logo')
b.screenshot(str(output / 'desktop-hero.png'))
# The renderer may measure the mark while the hero scene is zoomed during travel.
# Repeated returns must keep the painted canvas at its 46px layout size.
for cycle in range(3):
    for stop in (1, 0):
        b.js(f"document.querySelector('.stop[data-i=\"{stop}\"]').dispatchEvent(new MouseEvent('click',{{bubbles:true}}))")
        wait(f"universePerformance().snap.settledIndex==={stop} && universePerformance().snap.phase==='idle'")
    check(b.js("(()=>{const mark=document.querySelector('#object'), canvas=mark.querySelector('canvas'); return Math.abs(mark.getBoundingClientRect().width-46)<.2 && Math.abs(canvas.getBoundingClientRect().width-46)<.2})()"), f'Hero logo keeps its size after return {cycle + 1}')
print(b.js("import('/scripts/test-universe-shaders.mjs').then(m=>m.testShaderLifecycle())"), flush=True)
(output / 'results.json').write_text(json.dumps({'checks':checks,'samples':results}, indent=2))
print('Passed '+str(len(checks))+' startup checks', flush=True)

b.close()
