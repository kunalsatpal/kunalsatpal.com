"""One functional pass for browser-managed flights; no FPS benchmarking.

Requires the isolated Chrome/CDP and local server in universe-performance.md.
"""
import argparse
import json
import time
from browser_tools import Browser

parser = argparse.ArgumentParser()
parser.add_argument('--resume-at-cancellation', action='store_true', help='Resume after the backward and quick-return checks')
parser.add_argument('--check-sky', action='store_true', help='Also verify actual WebGPU clipping and visible pixel preservation')
args = parser.parse_args()
b = Browser(new_tab=True)
checks = []


def wait(expression, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if b.js(expression):
            return
        time.sleep(.05)
    raise AssertionError('Timed out: ' + expression)


def check(expression, message):
    assert b.js(expression), message
    checks.append(message)
    print(message, flush=True)


def settled(index):
    wait(f"universePerformance().snap.phase==='idle' && universePerformance().snap.settledIndex==={index} && !universePerformance().compositor.active")
    check(f"Math.abs(scrollY-({index}/8)*(document.querySelector('#journey').offsetHeight-innerHeight))<2", f'Exact landing at scene {index}')


def wheel(direction):
    b.call('Input.dispatchMouseEvent', {'type': 'mouseWheel', 'x': 720, 'y': 450,
                                      'deltaX': 0, 'deltaY': direction * 1400})


def go(index):
    b.js(f"document.querySelector('.stop[data-i=\"{index}\"]').dispatchEvent(new MouseEvent('click',{{bubbles:true}}))")


def sky_bounds():
    check("""(()=>{
      const stage=document.querySelector('#stage').getBoundingClientRect(),stats=universePerformance().skyCulling;
      return ['aurora','far'].every(name=>{
        const rect=document.querySelector('#'+name+'C').getBoundingClientRect(),s=stats[name];
        if(!s.sourceRect||!s.textureSize)return false;
        const [x,y,w,h]=s.sourceRect,[tw,th]=s.textureSize;
        const left=(Math.max(rect.left,stage.left)-rect.left)/rect.width*tw;
        const right=(Math.min(rect.right,stage.right)-rect.left)/rect.width*tw;
        const top=(Math.max(rect.top,stage.top)-rect.top)/rect.height*th;
        const bottom=(Math.min(rect.bottom,stage.bottom)-rect.top)/rect.height*th;
        return x<=left && y<=top && x+w>=right && y+h>=bottom &&
          left-x<4 && top-y<4 && x+w-right<4 && y+h-bottom<4;
      });
    })()""", 'GPU clipping covers every visible sky pixel with only an edge sampling margin')


try:
    b.call('Emulation.setFocusEmulationEnabled', {'enabled': True})
    b.call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 2, 'mobile': False})
    b.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'no-preference'}]})
    initial = 'hero' if args.resume_at_cancellation else 'gojek'
    b.navigate('http://127.0.0.1:8765/universe.html?perf&scene=' + initial)
    wait("typeof universePerformance==='function'")
    b.js("localStorage.removeItem('universeTheme')")
    if b.js("document.documentElement.classList.contains('theme-toon')"):
        b.js("document.querySelector('#styleToggle').click()")
    settled(0 if args.resume_at_cancellation else 3)
    time.sleep(.4)

    if args.check_sky:
        print(b.js("import('/scripts/test-universe-sky.mjs').then(m=>m.testSkyCulling())"), flush=True)
        print(b.js("import('/scripts/test-universe-shaders.mjs').then(m=>m.testShaderLifecycle())"), flush=True)
        pixels = b.js("import('/scripts/test-universe-sky.mjs').then(m=>m.testSkyPixels())")
        assert pixels['visiblePixelDifferences'] == 0, pixels
        checks.append('Full-detail Aurora matches every visible pixel when clipping is enabled')
        print(json.dumps(pixels), flush=True)
        wait("Object.values(universePerformance().shaders).every(s=>s.ready&&s.running) && Object.values(universePerformance().skyCulling).every(s=>s.passes>0)", 30)
        sky_bounds()

    if not args.resume_at_cancellation:
        wheel(-1)
        wait("universePerformance().compositor.aligned")
        check("universePerformance().compositor.scenes.sort().join(',')==='gojek,hinge'", 'Backward wheel owns only the departure and destination')
        check("""(()=>{
          const scene=document.querySelector('[data-scene=hinge]'),inner=scene.querySelector('.inner');
          const props=a=>Object.keys(a.effect.getKeyframes()[0]);
          const movement=scene.getAnimations().find(a=>props(a).includes('transform'));
          const blur=inner.getAnimations().find(a=>props(a).includes('filter'));
          return !!movement && !props(movement).includes('filter') && !!blur &&
            !props(blur).includes('transform') && inner.offsetWidth<scene.offsetWidth &&
            getComputedStyle(scene).filter==='none';
        })()""", 'Scene movement is independent of blur on the smaller content layer')
        poses = b.js("""new Promise(resolve=>{
          const scene=document.querySelector('[data-scene=hinge]');
          const read=()=>({computed:getComputedStyle(scene).transform,inline:scene.style.transform});
          const first=read();setTimeout(()=>resolve({first,last:read()}),120);
        })""")
        assert poses['first']['inline'] == poses['last']['inline'] and poses['first']['computed'] != poses['last']['computed'], poses
        checks.append('Chrome advances the flight without per-frame inline transform writes')
        print(checks[-1], flush=True)
        settled(2)
        check("getComputedStyle(document.querySelector('[data-scene=hinge]')).opacity==='1' && getComputedStyle(document.querySelector('[data-scene=hinge] > .inner')).filter==='none'", 'Completion retains the opaque, unblurred landing pose')
        time.sleep(.4)

        wheel(1)
        wait("universePerformance().compositor.active")
        time.sleep(.12)
        go(0)
        wait("universePerformance().compositor.active && universePerformance().compositor.scenes.join(',')==='hero'")
        check("document.querySelector('#stage').classList.contains('travel-backward') && new DOMMatrix(getComputedStyle(document.querySelector('[data-scene=hero]')).transform).a>1", 'Quick return gives only the hero its backward arrival')
        check("document.querySelector('.streaks').parentElement===document.querySelector('#stage')", 'Travel lines remain outside the fading camera')
        settled(0)
        wait("document.querySelector('#object').classList.contains('logo-ready')")
        check("(()=>{const image=document.querySelector('#object img.logo'),r=image.getBoundingClientRect();return image.naturalWidth>0&&Math.abs(r.width-46)<.2&&Math.abs(r.height-46)<.2&&!document.querySelector('#object canvas')})()", 'Returning hero keeps its decoded 46px PNG logo')
        time.sleep(.4)
        if args.check_sky:
            sky_bounds()

    b.js("dispatchEvent(new WheelEvent('wheel',{deltaY:1400,bubbles:true,cancelable:true}));document.querySelector('.stop[data-i=\"0\"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    time.sleep(.35)
    check("universePerformance().snap.phase==='idle' && !universePerformance().compositor.active && scrollY<1", 'Same-task wheel cancellation leaves no stale forward animation')

    b.js("document.querySelector('#styleToggle').click()")
    time.sleep(.9)
    go(8)
    wait("universePerformance().compositor.active && universePerformance().compositor.scenes.join(',')==='hello'")
    check("getComputedStyle(document.querySelector('[data-scene=hello]')).filter==='none' && getComputedStyle(document.querySelector('[data-scene=hello] > .inner')).filter==='none'", 'Toon multi-page arrival keeps crisp styling')
    b.js("document.querySelector('#styleToggle').click()")
    check("universePerformance().compositor.active && !document.documentElement.classList.contains('theme-toon')", 'Theme switching keeps the current flight alive')
    settled(8)
    time.sleep(.4)
    if args.check_sky:
        sky_bounds()
        check("universePerformance().skyCulling.aurora.drawnFraction<.56 && universePerformance().skyCulling.far.drawnFraction<.35", 'Enlarged sky skips invisible fragments without changing canvas resolution')
        before_dive = b.js("document.querySelector('#camera').classList.add('diving');Object.values(universePerformance().skyCulling).map(s=>s.passes)")
        time.sleep(.3)
        assert before_dive == b.js("Object.values(universePerformance().skyCulling).map(s=>s.passes)"), 'Camera dive must keep the full sky source'
        checks.append('Camera dive keeps the full sky source')
        print(checks[-1], flush=True)
        b.js("document.querySelector('#camera').classList.remove('diving')")
        wait("Object.values(universePerformance().skyCulling).every((s,i)=>s.passes>" + json.dumps(before_dive) + "[i])")
        checks.append('Camera return resumes clipping after the zoom settles')
        print(checks[-1], flush=True)

    wheel(-1)
    wait("universePerformance().compositor.active")
    b.call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 800, 'deviceScaleFactor': 2, 'mobile': False})
    settled(7)
    time.sleep(.4)
    if args.check_sky:
        sky_bounds()
    wheel(-1)
    wait("universePerformance().compositor.aligned")
    time.sleep(.12)
    b.js("document.querySelector('#skipBtn').click()")
    check("universePerformance().suspended && !universePerformance().compositor.active && !universePerformance().framePending", 'Opening the overview cancels and suspends the flight')
    b.js("document.querySelector('#backToFlight').click()")
    # Resume deliberately waits 80 ms before settling to the nearest stop. Idle
    # during that grace period does not establish a completed restoration.
    wait("!universePerformance().suspended && universePerformance().snap.phase==='idle' && Math.abs(scrollY-(universePerformance().snap.settledIndex/8)*(document.querySelector('#journey').offsetHeight-innerHeight))<2")
    current = b.js('universePerformance().snap.settledIndex')
    settled(current)
    time.sleep(.4)

    b.call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 3, 'mobile': True})
    b.call('Emulation.setTouchEmulationEnabled', {'enabled': True})
    wait("universePerformance().viewport.width===390 && universePerformance().snap.phase==='idle'")
    time.sleep(.4)
    b.call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': 195, 'y': 650}]})
    b.call('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': 195, 'y': 150}]})
    b.call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    settled(min(8, current + 1))
    check("document.documentElement.scrollWidth===innerWidth", 'Mobile swipe remains paginated without horizontal overflow')
    check("!document.querySelectorAll('.scene.active')[1]", 'Only one scene accepts input at rest')

    b.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
    b.navigate('http://127.0.0.1:8765/universe.html?perf&scene=hinge')
    wait("typeof universePerformance==='function' && universePerformance().visibleScenes.includes('hinge')")
    # Initial native scroll restores the direct-entry scene asynchronously.
    # Wait for that stop's own settlement before timing its momentum unlock.
    settled(2)
    time.sleep(.4)
    b.js("dispatchEvent(new WheelEvent('wheel',{deltaY:1400,bubbles:true,cancelable:true}))")
    settled(3)
    check("!universePerformance().compositor.active", 'Reduced motion uses the immediate renderer')

    b.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'no-preference'}]})
    b.js("history.replaceState({universeScene:'gojek'},'',location.pathname+'?perf')")
    b.call('Page.addScriptToEvaluateOnNewDocument', {'source': """addEventListener('DOMContentLoaded',()=>{
      window.__reloadEntrance={type:performance.getEntriesByType('navigation')[0].type,
        flight:document.documentElement.classList.contains('first-flight'),
        names:[...document.querySelectorAll('.title .object,.title .name,.title h1')].map(el=>getComputedStyle(el).animationName)};
    })"""})
    b.call('Page.reload', {'ignoreCache': True})
    wait('!!window.__reloadEntrance')
    check("__reloadEntrance.type==='reload' && __reloadEntrance.flight && __reloadEntrance.names.includes('hero-mark-in') && __reloadEntrance.names.includes('hero-rise')", 'Hard refresh restores headline and logo entrance despite saved moon state')
    errors = [event for event in b.events if event.get('method') == 'Runtime.exceptionThrown']
    assert not errors, errors
    if args.check_sky:
        gpu_errors = [event for event in b.events if event.get('method') == 'Runtime.consoleAPICalled' and
                      any('[gpu]' in str(arg.get('value', '')) and ('error' in str(arg.get('value', '')).lower() or 'failed' in str(arg.get('value', '')).lower()) for arg in event['params']['args'])]
        assert not gpu_errors, gpu_errors
    print(json.dumps({'passed': len(checks), 'checks': checks, 'uncaughtErrors': len(errors)}), flush=True)
finally:
    b.close()
