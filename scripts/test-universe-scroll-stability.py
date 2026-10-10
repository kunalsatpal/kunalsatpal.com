"""Scroll/preview regressions in an isolated Chrome tab.

Use the local browser/server setup in docs/universe-performance.md. Browser
suites must run sequentially. --url accepts a separately served baseline page;
--only previews is useful for reproducing unnecessary stationary layout work.
These checks retain the real CSS animations and use actual hover/focus state.
"""
import argparse
import json
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from browser_tools import Browser


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:8765/universe.html')
parser.add_argument('--only', choices=('all', 'previews', 'startup', 'dynamics'), default='all')
parser.add_argument('--widths', type=int, nargs='+', default=[390, 1440])
parser.add_argument('--themes', nargs='+', choices=('real', 'toon'), default=['real', 'toon'])
parser.add_argument('--output', default='/private/tmp/universe-scroll-stability.json')
args = parser.parse_args()
checks, failures, samples = [], [], {}
b = Browser(new_tab=True)


def check(condition, label, detail=None):
    result = {'check': label, 'passed': bool(condition)}
    if detail is not None:
        result['detail'] = detail
    checks.append(result)
    if not condition:
        failures.append(label)
    print(('PASS ' if condition else 'FAIL ') + label, flush=True)
    if not condition and detail is not None:
        print(json.dumps(detail, separators=(',', ':')), flush=True)


def wait(expression, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if b.js(expression):
            return
        time.sleep(.05)
    raise AssertionError('Timed out: ' + expression)


def url(**params):
    parts = urlsplit(args.url)
    query = dict(parse_qsl(parts.query))
    # A baseline URL may contain a pinned scene. Every test controls its own route.
    for key in ('at', 'scene', 'from', 'moon', 'theme'):
        query.pop(key, None)
    query.update({'perf': '', **params})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))


def viewport(width, height=None):
    height = height or (844 if width < 600 else 900)
    b.call('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': height, 'deviceScaleFactor': 3 if width < 600 else 1,
        'mobile': width < 600,
    })
    # Keep a mouse available even on the narrow layout to exercise hover and
    # keyboard affordances. Touch pagination has separate existing coverage.
    b.call('Emulation.setTouchEmulationEnabled', {'enabled': False})
    return height


def load(scene='hero', theme='real'):
    b.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 1, 'y': 1})
    origin = urlunsplit((*urlsplit(args.url)[:2], '', '', ''))
    b.js(f"if(location.origin==={json.dumps(origin)}) localStorage.setItem('universeTheme',{json.dumps(theme)})")
    b.navigate(url(**({'scene': scene} if scene != 'hero' else {}), theme=theme))
    wait('!!window.universePerformance')
    wait("universePerformance().snap.phase==='idle' && "
         f"document.querySelector('[data-scene={scene}]').classList.contains('active')")
    wait('document.fonts.status === "loaded"')
    assert b.js("document.documentElement.classList.contains('theme-toon')") == (theme == 'toon'), f'Expected {theme} theme'


def tip_box(selector):
    return b.js('''(() => {
      const anchor = document.querySelector(SELECTOR), tip = anchor.querySelector('.tip');
      const r = tip.getBoundingClientRect(), view = visualViewport;
      const x = view?.offsetLeft || 0, y = view?.offsetTop || 0;
      return {left:r.left, top:r.top, right:r.right, bottom:r.bottom,
        width:r.width, height:r.height, opacity:Number(getComputedStyle(tip).opacity),
        hovered:anchor.matches(':hover'), focused:anchor.matches(':focus-visible'),
        bounds:[x+12, y+12, x+(view?.width || innerWidth)-12, y+(view?.height || innerHeight)-12]};
    })()'''.replace('SELECTOR', json.dumps(selector)))


def contained(box, tolerance=1.5):
    left, top, right, bottom = box['bounds']
    return (box['width'] > 0 and box['height'] > 0 and
            box['left'] >= left - tolerance and box['top'] >= top - tolerance and
            box['right'] <= right + tolerance and box['bottom'] <= bottom + tolerance)


def hover(selector):
    point = b.js('''(() => {
      const anchor=document.querySelector(SELECTOR);
      const candidates=[anchor.querySelector('i'),anchor.querySelector('em'),anchor.querySelector('b'),anchor].filter(Boolean);
      for(const el of candidates) {
        const r=el.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
        if(x<1 || y<1 || x>=innerWidth || y>=innerHeight) continue;
        if(anchor.contains(document.elementFromPoint(x,y))) return {x,y};
      }
      return null;
    })()'''.replace('SELECTOR', json.dumps(selector)))
    if point is None:
        return False  # A moon can legitimately be behind its planet right now.
    b.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', **point})
    wait(f"document.querySelector({json.dumps(selector)}).matches(':hover')")
    time.sleep(.65)
    return True


def focus(selector):
    b.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 1, 'y': 1})
    # A real keyboard event establishes :focus-visible modality; focus() then
    # moves the actual focused element without synthesizing pointer events.
    b.call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
    b.call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
    b.js(f"document.querySelector({json.dumps(selector)}).focus({{preventScroll:true}})")
    wait(f"document.querySelector({json.dumps(selector)}).matches(':focus-visible')")
    time.sleep(.35)


def sample_tip(selector, duration=450):
    return b.js('''new Promise(resolve => {
      const anchor=document.querySelector(SELECTOR), tip=anchor.querySelector('.tip'), scene=anchor.closest('.scene');
      const values=[]; let start;
      function sample(t) {
        start ??= t;
        const r=tip.getBoundingClientRect(), view=visualViewport, s=getComputedStyle(scene);
        if(s.visibility!=='hidden' && Number(s.opacity)>.15 && Number(getComputedStyle(tip).opacity)>.5) {
          const x=view?.offsetLeft || 0, y=view?.offsetTop || 0;
          values.push({left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height,
            scale:new DOMMatrix(s.transform).a,
            bounds:[x+12,y+12,x+(view?.width || innerWidth)-12,y+(view?.height || innerHeight)-12]});
        }
        if(t-start<DURATION) requestAnimationFrame(sample); else resolve(values);
      }
      requestAnimationFrame(sample);
    })'''.replace('SELECTOR', json.dumps(selector)).replace('DURATION', str(duration)))


def dimension_writes(selector):
    return b.js('''new Promise(resolve => {
      const tip=document.querySelector(SELECTOR).querySelector('.tip'), records=[];
      const observer=new MutationObserver(list=>records.push(...list.map(r=>r.oldValue || '')));
      observer.observe(tip,{attributes:true,attributeFilter:['style'],attributeOldValue:true});
      setTimeout(()=>{
        observer.disconnect();
        const styles=records.concat(tip.getAttribute('style') || '').map(css=>{
          const el=document.createElement('span');el.style.cssText=css;
          return [el.style.width,el.style.maxHeight];
        });
        let dimensionWrites=0;
        for(let i=1;i<styles.length;i++)
          if(styles[i].some((v,j)=>v!==styles[i-1][j])) dimensionWrites++;
        resolve({styleMutations:records.length,dimensionWrites});
      },650);
    })'''.replace('SELECTOR', json.dumps(selector)))


def wheel(delta, width, height):
    b.call('Input.dispatchMouseEvent', {
        'type': 'mouseWheel', 'x': width / 2, 'y': height / 2,
        'deltaX': 0, 'deltaY': delta,
    })


def preview_checks():
    for width in args.widths:
        height = viewport(width)
        for theme in args.themes:
            for scene, kind in [('gojek', '.moon'), ('cult', '.moon'), ('galaxy', '.mini')]:
                load(scene, theme)
                count = b.js(f"document.querySelectorAll('[data-scene={scene}] {kind}').length")
                for index in range(count):
                    # Planet decorations share tag names with moons. Mark the
                    # actual candidate instead of relying on nth-of-type.
                    b.js(f"document.querySelectorAll('[data-scene={scene}] {kind}')[{index}].setAttribute('data-regression-preview','active')")
                    selector = '[data-regression-preview="active"]'
                    pointed = hover(selector)
                    if not pointed:
                        focusable = b.js(f"document.querySelector({json.dumps(selector)}).matches('a,button,[tabindex]')")
                        if not focusable:
                            b.js("document.querySelector('[data-regression-preview]').removeAttribute('data-regression-preview')")
                            continue
                        focus(selector)
                    box = tip_box(selector)
                    check((box['hovered'] if pointed else box['focused']) and box['opacity'] > .95 and contained(box),
                          f'{width}/{theme}/{scene} preview {index + 1}: real {"hover" if pointed else "focus"} stays inside viewport', box)
                    if scene != 'galaxy' and index == 0:
                        mutations = dimension_writes(selector)
                        samples[f'{width}/{theme}/{scene}/stationary'] = mutations
                        check(mutations['dimensionWrites'] <= 2,
                              f'{width}/{theme}/{scene}: settled hover avoids repeated dimension writes', mutations)
                    b.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 1, 'y': 1})
                    b.js("document.activeElement?.blur()")
                    b.js("document.querySelector('[data-regression-preview]').removeAttribute('data-regression-preview')")

                # Only product elements that are actually keyboard reachable
                # participate in a focus test. Current galaxy entries may all
                # be informational divs; their real pointer hovers were checked
                # above without changing product semantics for this suite.
                selector = f'[data-scene={scene}] ' + ('.mini:is(a,button,[tabindex])' if scene == 'galaxy' else '.moon.open')
                if not b.js(f"!!document.querySelector({json.dumps(selector)})"):
                    samples[f'{width}/{theme}/{scene}/focus'] = {'available': False}
                    print(f'SKIP {width}/{theme}/{scene}: no keyboard-reachable preview; pointer hovers covered', flush=True)
                    continue
                focus(selector)
                box = tip_box(selector)
                check(box['focused'] and box['opacity'] > .95 and contained(box),
                      f'{width}/{theme}/{scene}: keyboard preview stays inside viewport', box)

                # Keep the actual focused preview open while the scene scales
                # away. The test samples painted bounds throughout the motion.
                # Realistic runs enlarge departing scenes; cartoon runs also
                # cover shrinking scenes during backward movement.
                time.sleep(.35)
                wheel(-1100 if theme == 'toon' else 1100, width, height)
                positions = sample_tip(selector, 1000)
                scales = [p['scale'] for p in positions]
                check(len(positions) > 4 and max(scales, default=0) - min(scales, default=0) > .02,
                      f'{width}/{theme}/{scene}: preview tested through real scene scaling')
                outside = [p for p in positions if not contained(p, 2)]
                check(not outside, f'{width}/{theme}/{scene}: moving preview remains clamped', outside[:3])
                wait("universePerformance().snap.phase==='idle'")

            # Reflow an already open rich preview through narrow and wide layouts.
            load('gojek', theme)
            selector = '[data-scene=gojek] .moon.open'
            focus(selector)
            for resized in (320, 1440, width):
                viewport(resized)
                wait("universePerformance().snap.phase==='idle' && document.querySelector('[data-scene=gojek]').classList.contains('active')")
                time.sleep(.35)
                box = tip_box(selector)
                check(box['focused'] and contained(box),
                      f'{width}/{theme}: open preview reclamps at {resized}px', box)
            if width < 600:
                # Pinch zoom changes visualViewport without changing the route's
                # layout dimensions. Clamping must use the visible viewport.
                b.call('Emulation.setPageScaleFactor', {'pageScaleFactor': 1.5})
                time.sleep(.35)
                box = tip_box(selector)
                check(contained(box), f'{width}/{theme}: pinch viewport reclamps the open preview', box)
                b.call('Emulation.setPageScaleFactor', {'pageScaleFactor': 1})
                time.sleep(.35)
                box = tip_box(selector)
                check(contained(box), f'{width}/{theme}: zoom reset restores preview bounds', box)
            # A local image arriving after the preview is open changes its content
            # height. Its box must remain in bounds, including scrolling when tall.
            b.js('''(() => {
              const img=document.createElement('img'); img.id='preview-regression-image';
              img.style.cssText='display:block;width:100%;height:220px;object-fit:cover';
              img.src='./site/img/book_1.jpg';
              document.querySelector('[data-scene=gojek] .moon.open .tip').appendChild(img);
            })()''')
            wait("document.querySelector('#preview-regression-image').complete && document.querySelector('#preview-regression-image').naturalWidth>0")
            time.sleep(.35)
            box = tip_box(selector)
            check(contained(box), f'{width}/{theme}: late local image invalidates preview sizing', box)

            b.js('''(async () => {
              const face=new FontFace('PreviewRegression','url(./site/fonts/inter-tight-normal-latin.woff2)');
              document.fonts.add(face);
              const tip=document.querySelector('[data-scene=gojek] .moon.open .tip');
              tip.style.fontFamily='PreviewRegression, serif';
              await face.load(); await document.fonts.ready;
            })()''')
            time.sleep(.35)
            box = tip_box(selector)
            check(contained(box), f'{width}/{theme}: completed local font keeps preview in bounds', box)

            b.js("document.querySelector('#styleToggle').click()")
            time.sleep(1.15)
            positions = sample_tip(selector, 350)
            check(len(positions) > 4 and all(contained(p, 2) for p in positions),
                  f'{width}/{theme}: focused preview survives theme change', positions[-1:] or positions)


STARTUP_PROBE = '''(() => {
  window.scrollStabilityStartup={samples:[],errors:[],done:false};
  addEventListener('error',event=>scrollStabilityStartup.errors.push(event.message || 'resource failed'),true);
  const selectors=['.title .name','.title .rolechip','.title h1','.title .cue','.proof.p1','.proof.p2','.proof.p3','.proof.p4'];
  let readyAt;
  function sample(t) {
    if(window.universePerformance) readyAt ??= t;
    const values=selectors.map(selector=>{
      const el=document.querySelector(selector);
      if(!el || !el.getBoundingClientRect().width || getComputedStyle(el).display==='none') return null;
      let opacity=1;
      for(let node=el;node;node=node.parentElement) opacity*=Number(getComputedStyle(node).opacity);
      const matrix=new DOMMatrix(getComputedStyle(el).transform);
      return {opacity,depth:matrix.m43};
    });
    scrollStabilityStartup.samples.push(values);
    if(readyAt && t-readyAt>4200) scrollStabilityStartup.done=true;
    else requestAnimationFrame(sample);
  }
  requestAnimationFrame(sample);
})();'''


def startup_checks():
    script = b.call('Page.addScriptToEvaluateOnNewDocument', {'source': STARTUP_PROBE})['identifier']
    try:
        for width in args.widths:
            viewport(width)
            for theme in args.themes:
                b.call('Network.clearBrowserCache')
                load('hero', theme)
                wait('scrollStabilityStartup.done', 35)
                data = b.js('scrollStabilityStartup')
                sequences = [[s[i] for s in data['samples'] if s[i] is not None] for i in range(8)]
                labels = ['name', 'role', 'headline', 'scroll cue', 'card 1', 'card 2', 'card 3', 'card 4']
                for label, seq in zip(labels, sequences):
                    if not seq:
                        continue  # Desktop artwork is deliberately absent on phones.
                    drops = [{'before': a['opacity'], 'after': c['opacity']}
                             for a, c in zip(seq, seq[1:]) if c['opacity'] < a['opacity'] - .025]
                    check(not drops and seq[-1]['opacity'] > .99,
                          f'{width}/{theme}: {label} entrance never flashes away', drops[:3])
                check(not data['errors'], f'{width}/{theme}: cold entrance has no resource/script errors', data['errors'])
                text = [v for seq in sequences[:4] for v in seq]
                check(any(v['depth'] < -60 for v in text), f'{width}/{theme}: text still arrives from depth')
                if width >= 600:
                    card_values = [v for seq in sequences[4:] for v in seq]
                    check(any(v['depth'] < -100 for v in card_values), f'{width}/{theme}: cards still arrive from depth')
                samples[f'{width}/{theme}/startup'] = {'frames': len(data['samples'])}
        b.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
        load('hero')
        check(b.js("[...document.querySelectorAll('.title .name,.title .rolechip,.title h1,.title .cue')].every(e=>getComputedStyle(e).animationName==='none'&&getComputedStyle(e).opacity==='1')"),
              'Reduced motion: text remains immediately visible without entrance animation')
    finally:
        b.call('Page.removeScriptToEvaluateOnNewDocument', {'identifier': script})
        b.call('Emulation.setEmulatedMedia', {'features': []})


def dynamics_checks():
    for width in args.widths:
        height = viewport(width)
        load('gojek')
        time.sleep(.4)
        wheel(1200, width, height)
        data = b.js('''new Promise(resolve => {
          const started=performance.now(), samples=[];let count=0;
          const timer=setInterval(()=>{
            dispatchEvent(new Event('resize')); count++;
            if(count===6) clearInterval(timer);
          },45);
          function sample() {
            const state=universePerformance().snap;
            samples.push({...state,y:scrollY});
            if(state.phase==='idle' || performance.now()-started>2200)
              resolve({elapsed:performance.now()-started,samples});
            else requestAnimationFrame(sample);
          }
          requestAnimationFrame(sample);
        })''')
        states = data['samples']
        check(all(s['phase'] in ('snapping', 'idle') for s in states),
              f'{width}: unchanged resize does not restart a wheel snap', sorted({s['phase'] for s in states}))
        check(states[-1]['phase'] == 'idle' and states[-1]['settledIndex'] == 4 and data['elapsed'] < 1400,
              f'{width}: resize notifications preserve the original snap duration', {'elapsed': data['elapsed'], 'final': states[-1]})

        load('hello')
        wait('!universePerformance().framePending')
        time.sleep(1.1)
        b.js('''window.idleWakePositions=[]; window.idleWakeStop=false;
          function sampleIdleWake(t) {
            idleWakePositions.push({at:t,y:scrollY,phase:universePerformance().snap.phase});
            if(!idleWakeStop) requestAnimationFrame(sampleIdleWake);
          }
          requestAnimationFrame(sampleIdleWake);''')
        wheel(-1100, width, height)
        wait("universePerformance().snap.phase==='idle' && universePerformance().snap.settledIndex===7")
        positions = b.js('idleWakeStop=true; idleWakePositions')
        total = abs(positions[-1]['y'] - positions[0]['y'])
        steps = [abs(c['y'] - a['y']) for a, c in zip(positions, positions[1:])]
        check(total > height and len(positions) > 8 and max(steps, default=total) < total * .3,
              f'{width}: first movement after idle has no single-frame scroll jump',
              {'frames': len(positions), 'largestStep': max(steps, default=0), 'distance': total})
        check(b.js("document.querySelector('[data-scene=life]').classList.contains('active') && getComputedStyle(document.querySelector('#camera')).opacity==='1'"),
              f'{width}: idle wake lands on a fully visible destination')


try:
    b.call('Emulation.setFocusEmulationEnabled', {'enabled': True})
    b.call('Emulation.setCPUThrottlingRate', {'rate': 1})
    b.call('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
    origin = urlunsplit((*urlsplit(args.url)[:2], '', '', ''))
    b.call('Storage.clearDataForOrigin', {'origin': origin, 'storageTypes': 'local_storage'})
    if args.only in ('all', 'startup'):
        startup_checks()
    if args.only in ('all', 'previews'):
        preview_checks()
    if args.only in ('all', 'dynamics'):
        dynamics_checks()
    exceptions = [e for e in b.events if e.get('method') == 'Runtime.exceptionThrown']
    check(not exceptions, 'No uncaught browser errors during scroll regressions', exceptions[:3])
finally:
    b.close()
    Path(args.output).write_text(json.dumps({'url': args.url, 'checks': checks, 'samples': samples, 'failures': failures}, indent=2))

print(f'{len(checks) - len(failures)}/{len(checks)} scroll stability checks passed', flush=True)
if failures:
    raise SystemExit(1)
