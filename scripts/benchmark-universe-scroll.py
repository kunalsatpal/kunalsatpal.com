"""Profile actual Universe inputs without mixing transition frames with idle time.

Use the server/isolated Chrome setup in docs/universe-performance.md. Run browser
suites sequentially. Callback intervals are NOT presented-frame measurements;
--trace-dir preserves compositor/raster evidence for review in Chrome DevTools.
Desktop/mobile emulation uses the host's GPU and does not replace phone testing.
"""
import argparse
import base64
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from browser_tools import Browser


SCENES = ['hero', 'about', 'hinge', 'gojek', 'cult', 'galaxy', 'writing', 'life', 'hello']
DEVICES = {
    'desktop': {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False},
    'desktop-retina': {'width': 1440, 'height': 900, 'deviceScaleFactor': 2, 'mobile': False},
    'mobile': {'width': 390, 'height': 844, 'deviceScaleFactor': 3, 'mobile': True},
}
CASES = ['wheel-forward', 'wheel-backward', 'trackpad-burst', 'touch-forward',
         'touch-backward', 'adjacent-nav', 'distant-forward', 'distant-backward',
         'rapid-retarget', 'planet-idle', 'preview-idle', 'resize-scroll',
         'unchanged-resize-scroll', 'stall-scroll', 'cold-wheel', 'quick-hero-return']

# Read only inline scene styles and existing diagnostics while sampling. No layout
# or computed-style reads are introduced into the site's render loop by this probe.
PROBE = r"""
(() => {
  const tasks = [], loaf = [], inputs = [], errors = [], supported =
    PerformanceObserver.supportedEntryTypes || [];
  // Geometry getters can flush the application's pending style writes. Measure
  // only at document initialization and the corresponding browser events.
  let viewport={width:innerWidth,height:innerHeight}, scrollPosition=scrollY;
  addEventListener('resize', () => {
    viewport={width:innerWidth,height:innerHeight};
  }, {passive:true});
  addEventListener('scroll', () => { scrollPosition=scrollY; }, {passive:true});
  const keep = (list, entry) => { list.push(entry); if (list.length > 2000) list.shift(); };
  if (supported.includes('longtask')) new PerformanceObserver(list => {
    for (const e of list.getEntries()) keep(tasks, {
      startTime:e.startTime, duration:e.duration, name:e.name,
      attribution:[...e.attribution].map(a => ({name:a.name, containerType:a.containerType,
        containerName:a.containerName, containerId:a.containerId, containerSrc:a.containerSrc}))
    });
  }).observe({type:'longtask', buffered:true});
  if (supported.includes('long-animation-frame')) new PerformanceObserver(list => {
    for (const e of list.getEntries()) keep(loaf, {
      startTime:e.startTime, duration:e.duration, blockingDuration:e.blockingDuration,
      renderStart:e.renderStart, styleAndLayoutStart:e.styleAndLayoutStart,
      firstUIEventTimestamp:e.firstUIEventTimestamp,
      scripts:[...e.scripts].map(s => ({invoker:s.invoker, invokerType:s.invokerType,
        sourceURL:s.sourceURL, sourceFunctionName:s.sourceFunctionName,
        sourceCharPosition:s.sourceCharPosition, startTime:s.startTime,
        duration:s.duration, executionStart:s.executionStart,
        forcedStyleAndLayoutDuration:s.forcedStyleAndLayoutDuration,
        pauseDuration:s.pauseDuration, windowAttribution:s.windowAttribution}))
    });
  }).observe({type:'long-animation-frame', buffered:true});
  for (const type of ['wheel','touchstart','touchmove','touchend','click']) {
    addEventListener(type, e => {
      const target=e.target, ignored=target.closest?.(
        '.modal, .overview, input, textarea, select, [contenteditable="true"], [data-lenis-prevent]');
      const describe=node => node ? {tag:node.tagName || node.nodeName, id:node.id || '',
        class:node.getAttribute?.('class') || ''} : null;
      const stop=target.closest?.('.stop');
      keep(inputs, {type, at:performance.now(), timestamp:e.timeStamp,
        deltaY:e.deltaY ?? null, trusted:e.isTrusted, target:describe(target),
        stopIndex:stop ? Number(stop.dataset.i) : null,
        ignoredAncestor:describe(ignored), page:{hidden:document.hidden,
          cameraClass:document.getElementById('camera')?.className || '',
          modalClass:document.getElementById('modal')?.className || '',
          overviewClass:document.getElementById('overview')?.className || '',
          firstFlight:document.documentElement.classList.contains('first-flight'),
          snap:window.universePerformance?.().snap || null}});
    }, {capture:true, passive:true});
  }
  addEventListener('error', e => keep(errors, {at:performance.now(),
    message:e.message || 'resource failed', source:e.filename || e.target?.src || ''}), true);
  addEventListener('unhandledrejection', e => keep(errors, {
    at:performance.now(), message:String(e.reason)}));
  let sceneElements=null, stageElement=null, cameraElement=null;
  function snapshot() {
    const p = window.universePerformance?.();
    if (!sceneElements) {
      const found=[...document.querySelectorAll('.scene')];
      if (found.length===9) sceneElements=found;
    }
    stageElement ??= document.getElementById('stage');
    cameraElement ??= document.getElementById('camera');
    return {scrollY:scrollPosition, viewport,
      stageClass:stageElement?.className || '', cameraOpacity:cameraElement?.style.opacity || '',
      transforms:(sceneElements || []).map(e => e.style.transform),
      route:p?.route ?? null, animatedScroll:p?.animatedScroll ?? null,
      snap:p?.snap || null, shaders:p?.shaders || null, visibleScenes:p?.visibleScenes || [],
      firstFlight:document.documentElement.classList.contains('first-flight')};
  }
  function motionKey(s) {
    return JSON.stringify([Math.round(s.scrollY * 100)/100,
      s.stageClass,s.cameraOpacity,s.transforms]);
  }
  let current = null;
  window.__scrollBenchmark = {
    supported, tasks, loaf, inputs, errors, snapshot,
    arm({target, steadyMs=0, timeoutMs=18000}) {
      const initial=snapshot(), at=performance.now();
      current={armedAt:at, target, steadyMs, timeoutMs, initial, initialKey:motionKey(initial),
        firstMotionAt:steadyMs ? at : null, lastFrame:null, intervals:[], frames:[],
        states:[], lastState:'', done:false, stableAt:null, endAt:null};
      requestAnimationFrame(sample);
      return at;
    },
    result() {
      if (!current?.done) return null;
      const c=current, start=c.firstMotionAt ?? c.armedAt, end=c.endAt;
      const overlap=e => e.startTime < end && e.startTime+e.duration > start;
      const events=inputs.filter(e => e.at >= c.armedAt && e.at <= end);
      // Swipe motion starts on release in the site's current pagination model.
      const trigger=events.find(e => ['wheel','touchend','click'].includes(e.type));
      return {...c, initialKey:undefined, lastState:undefined,
        final:snapshot(), longTasks:tasks.filter(overlap), longAnimationFrames:loaf.filter(overlap),
        inputEvents:events, errors:errors.filter(e => e.at >= c.armedAt && e.at <= end),
        motionDurationMs:c.firstMotionAt === null ? null : end-c.firstMotionAt,
        armedToSettledMs:end-c.armedAt,
        inputToSettledMs:trigger ? end-trigger.at : null,
        inputToFirstObservedMotionMs:trigger && c.firstMotionAt !== null && c.firstMotionAt>=trigger.at
          ? c.firstMotionAt-trigger.at : null,
        inputLatencyNote:'Event capture and DOM-motion observation use performance.now(), not the earlier '
          +'rAF frame timestamp. This is callback-observed motion, not input-to-presented-pixel latency.',
        geometrySamplingNote:'Viewport updates only on resize; scroll position updates only on scroll events. '
          +'No geometry getters run in the frame probe. Event-driven scroll samples can trail a '
          +'same-frame Lenis write by one callback; scene transforms also detect motion.'};
    }
  };
  function sample(t) {
    const c=current;
    if (!c || c.done) return;
    const observedAt=performance.now();
    const s=snapshot(), key=motionKey(s);
    const trigger=inputs.find(e => e.at>=c.armedAt && ['wheel','touchend','click'].includes(e.type));
    if (c.firstMotionAt === null && trigger && key !== c.initialKey) {
      c.firstMotionAt=observedAt;
      c.firstMotionFrameTimestamp=t;
    }
    if (c.firstMotionAt !== null) {
      if (c.lastFrame !== null) c.intervals.push(t-c.lastFrame);
      c.lastFrame=t;
      c.frames.push({at:t, observedAt, scrollY:s.scrollY, route:s.route,
        animatedScroll:s.animatedScroll, target:s.snap?.targetIndex,
        settled:s.snap?.settledIndex, phase:s.snap?.phase,
        visibleScenes:s.visibleScenes, viewport:s.viewport,
        stageClass:s.stageClass, cameraOpacity:s.cameraOpacity});
    }
    const state=JSON.stringify([s.snap,s.viewport,s.stageClass]);
    if (state !== c.lastState) { c.states.push({at:observedAt,...s}); c.lastState=state; }
    const atTarget=s.snap?.phase==='idle' && s.snap?.settledIndex===c.target
      && !/\b(?:jumping|traveling)\b/.test(s.stageClass);
    if (c.steadyMs) {
      if (observedAt-c.firstMotionAt >= c.steadyMs) c.done=true;
    } else if (c.firstMotionAt !== null && atTarget) {
      c.stableAt ??= observedAt;
      if (observedAt-c.stableAt >= 50) c.done=true;
    } else c.stableAt=null;
    if (observedAt-c.armedAt >= c.timeoutMs) { c.done=true; c.timedOut=true; }
    if (c.done) c.endAt=observedAt;
    else requestAnimationFrame(sample);
  }
})();
"""


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)], 3)


def csv_list(value):
    return [part.strip() for part in value.split(',') if part.strip()]


def page_url(base, theme, scene):
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key in ['at', 'from', 'moon', 'scene', 'theme']:
        query.pop(key, None)
    query.update({'perf': '', 'theme': theme})
    if scene is not None:
        query['scene'] = SCENES[scene]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))


def metrics(browser):
    return {m['name']: m['value'] for m in browser.call('Performance.getMetrics')['metrics']}


def metric_delta(before, after):
    result = {}
    for name in ['TaskDuration', 'ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration',
                 'LayoutCount', 'RecalcStyleCount', 'JSHeapUsedSize', 'JSHeapTotalSize']:
        if name in before and name in after:
            multiplier = 1000 if name.endswith('Duration') else 1
            result[name + ('Ms' if multiplier == 1000 else '')] = round(
                (after[name] - before[name]) * multiplier, 3)
    return result


def wait_for(browser, expression, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = browser.js(expression)
        if result:
            return result
        time.sleep(.05)
    raise TimeoutError('Timed out: ' + expression)


def click_point(browser, selector):
    return browser.js(f"""(() => {{
      const e=document.querySelector({json.dumps(selector)});
      if (!e) throw new Error('Missing input target');
      // The SVG stop group also contains its text label, so the group bounds'
      // center need not touch its clickable circle.
      const target=e.querySelector('.hit,.dot') || e, r=target.getBoundingClientRect();
      if (!r.width || !r.height) throw new Error('Input target has no visible bounds');
      const x=r.left+r.width/2,y=r.top+r.height/2,hit=document.elementFromPoint(x,y);
      if (!hit || !(hit===e || e.contains(hit) || hit.closest?.('.stop')===e)) {{
        throw new Error('Input target is not hit-testable at its center: '+{json.dumps(selector)});
      }}
      return {{x,y}};
    }})()""")


def click(browser, selector, point=None):
    if point is None:
        point = click_point(browser, selector)
    browser.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', **point})
    for kind in ['mousePressed', 'mouseReleased']:
        browser.call('Input.dispatchMouseEvent', {
            'type': kind, 'button': 'left', 'clickCount': 1, **point})


def wheel(browser, device, direction=1, burst=False):
    # CDP wheel events exercise the real controller. A timed, small-delta burst is
    # a trackpad approximation, not a claim to emulate a physical trackpad driver.
    for delta in ([60, 75, 55, 35, 20] if burst else [1200]):
        browser.call('Input.dispatchMouseEvent', {
            'type': 'mouseWheel', 'x': device['width'] * .5,
            'y': device['height'] * .55, 'deltaX': 0, 'deltaY': delta * direction})
        if burst:
            time.sleep(.012)


def swipe(browser, device, direction=1):
    start, end = (device['height'] * .78, device['height'] * .23)
    if direction < 0:
        start, end = end, start
    point = {'x': device['width'] * .5, 'y': start, 'id': 1}
    browser.call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [point]})
    for step in range(1, 6):
        point['y'] = start + (end - start) * step / 5
        browser.call('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [point]})
        time.sleep(.018)
    browser.call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})


def stop_trace(browser, path):
    browser.call('Tracing.end')
    deadline = time.monotonic() + 20
    complete = None
    while time.monotonic() < deadline:
        complete = next((e for e in browser.events if e.get('method') == 'Tracing.tracingComplete'), None)
        if complete:
            break
        browser.call('Runtime.evaluate', {'expression': '0'})
        time.sleep(.05)
    if not complete:
        raise TimeoutError('Tracing completion was not received')
    handle = complete['params']['stream']
    chunks = []
    try:
        while True:
            part = browser.call('IO.read', {'handle': handle, 'size': 1048576})
            chunks.append(base64.b64decode(part['data']) if part.get('base64Encoded')
                          else part['data'].encode())
            if part.get('eof'):
                break
    finally:
        browser.call('IO.close', {'handle': handle})
    raw = b''.join(chunks)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    trace = json.loads(raw)
    names = ['BeginFrame', 'DrawFrame', 'FramePresented', 'DroppedFrame',
             'Layout', 'UpdateLayoutTree', 'Paint', 'RasterTask', 'CompositeLayers']
    summary = {name: {'events': 0, 'completeEventDurationMs': 0} for name in names}
    for event in trace.get('traceEvents', []):
        name = event.get('name')
        if name in summary:
            summary[name]['events'] += 1
            if event.get('ph') == 'X':
                summary[name]['completeEventDurationMs'] += event.get('dur', 0) / 1000
    return {'path': str(path), 'bytes': len(raw), 'events': summary,
            'note': 'Counts can span processes/threads and are not a presented-FPS estimate. '
                    'Inspect frame tracks and event attribution in DevTools.'}


def hero_return_summary(sample):
    reasons = []
    forward = next((event for event in sample['inputEvents']
                    if event['type'] == 'wheel' and event['trusted'] and event['deltaY'] > 0), None)
    returned = next((event for event in sample['inputEvents']
                     if event['type'] == 'click' and event['trusted'] and event['stopIndex'] == 0), None)
    if forward is None or returned is None:
        reasons.append('Missing trusted forward wheel or Hero map click')
    delay = returned['at'] - forward['at'] if forward and returned else None
    if delay is not None and not 60 <= delay <= 300:
        reasons.append('Hero click missed the quick-retarget window (60–300 ms)')
    departing = returned['page']['snap'] if returned else None
    if not departing or departing['phase'] != 'snapping' or departing['targetIndex'] != 4:
        reasons.append('Hero click did not interrupt the wheel transition toward Cult')
    # Departure may remain staged under the hidden camera during preparation.
    # Once arrival is shown, no intermediate scene may enter the viewport.
    arrival = [frame for frame in sample['frames'] if returned and frame['observedAt'] >= returned['at']
               and 'traveling' in frame['stageClass'].split()
               and 'jumping' not in frame['stageClass'].split()]
    if not arrival or any(scene != 'hero' for frame in arrival for scene in frame['visibleScenes']):
        reasons.append('Hero arrival displayed an intermediate route scene')
    hero = next((frame for frame in arrival if 'hero' in frame['visibleScenes']), None)
    if hero is None or sample['final']['visibleScenes'] != ['hero']:
        reasons.append('Hero did not become the sole visible destination')
    return {
        'requestedClickDelayMs': 120, 'actualClickDelayMs': round(delay, 3) if delay is not None else None,
        'clickToFirstVisibleHeroMs': round(hero['observedAt'] - returned['at'], 3) if hero and returned else None,
        'clickToSettledMs': round(sample['endAt'] - returned['at'], 3) if returned else None,
        'arrivalFrames': len(arrival), 'invalidReasons': reasons,
    }


def case_route(name):
    routes = {
        'wheel-forward': (2, 3), 'wheel-backward': (3, 2),
        'trackpad-burst': (2, 3), 'touch-forward': (2, 3), 'touch-backward': (3, 2),
        'adjacent-nav': (2, 3), 'distant-forward': (2, 8), 'distant-backward': (8, 2),
        'rapid-retarget': (2, 3), 'planet-idle': (3, 3), 'preview-idle': (3, 3),
        'resize-scroll': (2, 3), 'unchanged-resize-scroll': (2, 3),
        'stall-scroll': (2, 3), 'cold-wheel': (0, 1),
        'quick-hero-return': (3, 0),
    }
    return routes[name]


def run_case(browser, args, name, device_name, theme, cpu, repetition):
    device = DEVICES[device_name].copy()
    start, target = case_route(name)
    browser.call('Emulation.setDeviceMetricsOverride', device)
    browser.call('Emulation.setTouchEmulationEnabled', {'enabled': device['mobile']})
    browser.call('Emulation.setCPUThrottlingRate', {'rate': cpu})
    cold = name == 'cold-wheel'
    browser.call('Network.setCacheDisabled', {'cacheDisabled': cold})
    if cold:
        browser.call('Network.clearBrowserCache')
        # Repeated cold trials must not restore the previous trial's About stop.
        browser.js("history.replaceState(null,'',location.href)")
    page_key = (args.url, device_name, theme, cpu)
    reuse = args.reuse_page and not cold and getattr(browser, 'benchmark_page', None) == page_key
    if reuse:
        # Reproduce repeated navigation in the same document/GPU device. Setup
        # movement is excluded from the timed, trusted-input sample below.
        browser.js(f"document.querySelector('.stop[data-i=\"{start}\"]').dispatchEvent(new MouseEvent('click',{{bubbles:true}}))")
    else:
        # Do not let a departing document's ready probe satisfy this wait.
        browser.js('window.__scrollBenchmark = null')
        browser.call('Page.navigate', {'url': page_url(args.url, theme, None if cold else start)})
        browser.benchmark_page = page_key
    wait_for(browser, '!!window.universePerformance && !!window.__scrollBenchmark', args.timeout)
    gpu_supported = browser.js('navigator.gpu?.requestAdapter().then(a=>!!a).catch(()=>false) ?? false')
    if not cold:
        wait_for(browser, f"universePerformance().snap.phase==='idle' && "
                          f"universePerformance().snap.settledIndex==={start}", args.timeout)
        # Warm code/assets and renderers separately from the sample itself.
        time.sleep(args.warmup)
        wait_for(browser, "!document.documentElement.classList.contains('first-flight')", args.timeout)
        if gpu_supported:
            registered = browser.js('universePerformance().shaders')
            expected = (['aurora', 'far'] if theme == 'real' else []) + (
                ['mark'] if start == 0 and 'mark' in registered else [])
            condition = json.dumps(expected) + ".every(name=>{const s=universePerformance().shaders[name];return s?.wanted&&s.ready&&s.running})"
            wait_for(browser, condition, args.timeout)
    shader_check = browser.js('universePerformance().shaders')
    setup = browser.js("""({
      navigation:performance.getEntriesByType('navigation').map(e=>e.toJSON()),
      marks:performance.getEntriesByType('mark').filter(e=>e.name.startsWith('universe:')).map(e=>e.toJSON()),
      measures:performance.getEntriesByType('measure').filter(e=>e.name.startsWith('universe:')).map(e=>e.toJSON()),
      longTasks:__scrollBenchmark.tasks,
      shaderStatus:universePerformance().shaders,
      supportedObservers:__scrollBenchmark.supported,
      focused:document.hasFocus(),visibility:document.visibilityState,
      theme:document.documentElement.classList.contains('theme-toon')?'toon':'real'
    })""")
    if not setup['focused'] or setup['visibility'] != 'visible':
        raise RuntimeError('Invalid trial: document is not visible and focused')
    if setup['theme'] != theme:
        raise RuntimeError('Invalid trial: theme differs from requested theme')
    if cold and not browser.js("document.documentElement.classList.contains('first-flight') && !document.documentElement.classList.contains('scene-entry')"):
        raise RuntimeError('Invalid cold trial: initial entrance ended or was bypassed before input')
    setup['gpuAdapterAvailable'] = gpu_supported
    setup['renderingPath'] = ('startup-not-warmed' if cold else
                              'full-quality-ready' if gpu_supported else 'gpu-unavailable-fallback')
    setup['shaderGate'] = ('Warm wanted effects must be ready and running when a GPU adapter is available. '
                           'Fallback and startup samples must be compared separately.')
    if name == 'preview-idle':
        # Keyboard focus is a normal way to open the preview and remains reliable
        # while the moon moves. Focus emulation avoids an invalid headless trial.
        browser.js("document.querySelector('[data-scene=gojek] .moon.open').focus({preventScroll:true})")
        wait_for(browser, "!!document.querySelector('[data-scene=gojek] .tip-float.on')", args.timeout)
        wait_for(browser, "[...document.querySelectorAll('[data-scene=gojek] .tip-float.on img')].every(i=>i.complete&&i.naturalWidth>0)", args.timeout)
        time.sleep(.65)  # Exclude opening animation/image/font work from steady state.
        setup['preview'] = browser.js("""(() => {
          const tip=document.querySelector('[data-scene=gojek] .tip-float.on');
          const r=tip.getBoundingClientRect();
          return {open:!!tip,opacity:Number(getComputedStyle(tip).opacity),
            rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom},
            viewport:{width:innerWidth,height:innerHeight}};
        })()""")
        if setup['preview']['opacity'] < .9:
            raise RuntimeError('Invalid preview trial: preview is not visibly open')
    # The map stays fixed during this route. Measure its hit target before the
    # timed sample rather than flushing layout while the wheel motion is active.
    hero_point = click_point(browser, '.stop[data-i="0"]') if name == 'quick-hero-return' else None
    browser.events.clear()
    tracing = bool(args.trace_dir)
    trace_path = Path(args.trace_dir) / f'{device_name}-{theme}-cpu{cpu:g}-{name}-{repetition}.json' if tracing else None
    if tracing:
        browser.call('Tracing.start', {
            'categories': 'devtools.timeline,disabled-by-default-devtools.timeline.frame,blink.user_timing,cc,viz,benchmark',
            'transferMode': 'ReturnAsStream'})
    before = metrics(browser)
    cpu_window_start = time.monotonic()
    arm = {'target': target, 'steadyMs': args.steady * 1000 if name.endswith('-idle') else 0,
           'timeoutMs': args.timeout * 1000}
    armed_at = browser.js('__scrollBenchmark.arm(' + json.dumps(arm) + ')')
    trace_result = None
    active_error = None
    try:
        intervention = None
        if name in ['wheel-forward', 'trackpad-burst', 'cold-wheel', 'resize-scroll',
                    'unchanged-resize-scroll', 'stall-scroll']:
            wheel(browser, device, burst=name == 'trackpad-burst')
        elif name == 'wheel-backward':
            wheel(browser, device, direction=-1)
        elif name.startswith('touch-'):
            swipe(browser, device, direction=-1 if name.endswith('backward') else 1)
        elif name in ['adjacent-nav', 'distant-forward', 'distant-backward']:
            click(browser, f'.stop[data-i="{target}"]')
        elif name == 'rapid-retarget':
            click(browser, '.stop[data-i="8"]')
            time.sleep(.35)
            click(browser, '.stop[data-i="3"]')
        elif name == 'quick-hero-return':
            wheel(browser, device)
            elapsed = wait_for(browser, """(() => {
              const e=__scrollBenchmark.inputs.find(e=>e.type==='wheel'&&e.trusted&&e.at>=%s);
              return e ? {at:e.at,elapsed:performance.now()-e.at} : null;
            })()""" % armed_at, args.timeout)
            time.sleep(max(0, (120 - elapsed['elapsed']) / 1000))
            click(browser, '.stop[data-i="0"]', hero_point)
            intervention = {'kind': 'trusted wheel toward Cult, then trusted map click to Hero',
                            'requestedDelayMs': 120, 'wheelAt': elapsed['at']}
        if name == 'resize-scroll':
            time.sleep(.32)
            device['height'] -= 100
            browser.call('Emulation.setDeviceMetricsOverride', device)
            time.sleep(.18)
            device['height'] += 35
            browser.call('Emulation.setDeviceMetricsOverride', device)
        if name in ['unchanged-resize-scroll', 'stall-scroll']:
            time.sleep(.32)
            intervention = browser.js("({at:performance.now(),before:__scrollBenchmark.snapshot()})")
            if name == 'unchanged-resize-scroll':
                browser.js("dispatchEvent(new Event('resize'))")
                intervention['kind'] = 'resize event with unchanged viewport geometry'
            else:
                browser.js(f"""(() => {{
                  const end=performance.now()+{args.stall_ms};
                  while(performance.now()<end) {{}}
                }})()""")
                intervention['kind'] = 'controlled main-thread stall'
                intervention['requestedStallMs'] = args.stall_ms
            intervention['after'] = browser.js("({at:performance.now(),state:__scrollBenchmark.snapshot()})")
        sample = wait_for(browser, '__scrollBenchmark.result()', args.timeout + 3)
        after = metrics(browser)
        cpu_window_ms = (time.monotonic() - cpu_window_start) * 1000
    except Exception as error:
        active_error = error
        raise
    finally:
        if tracing:
            try:
                trace_result = stop_trace(browser, trace_path)
            except Exception as error:
                if active_error is None:
                    raise
                # Preserve the original CDP/input error if Chrome also refuses
                # trace shutdown. The caller records both errors separately.
                active_error.trace_cleanup_error = str(error)
    intervals = sample.pop('intervals')
    summary = {
        'callbacks': len(intervals) + (1 if sample['frames'] else 0),
        'p50Ms': percentile(intervals, .50), 'p95Ms': percentile(intervals, .95),
        'p99Ms': percentile(intervals, .99), 'maxMs': round(max(intervals), 3) if intervals else None,
        'over33_4Ms': sum(x > 33.4 for x in intervals),
        'over50Ms': sum(x > 50 for x in intervals),
        'note': 'JavaScript rAF callback intervals during motion (plus up to 50 ms settle confirmation); '
                'these do not establish GPU frame presentation or actual display refresh rate.',
    }
    sample['callbackIntervalsMs'] = intervals
    sample['callbackSummary'] = summary
    sample['longTaskDurationMs'] = round(sum(t['duration'] for t in sample['longTasks']), 3)
    sample['forcedStyleAndLayoutMs'] = round(sum(
        s.get('forcedStyleAndLayoutDuration', 0)
        for frame in sample['longAnimationFrames'] for s in frame['scripts']), 3)
    sample['forcedStyleAndLayoutCoverage'] = (
        'Browser attribution for scripts in long animation frames only; zero is not proof of no forced layout.')
    result = {
        'case': name, 'device': device_name, 'theme': theme, 'cpuRate': cpu,
        'repetition': repetition, 'viewport': DEVICES[device_name],
        'cache': 'cold (disabled and cleared)' if cold else 'enabled; warm animation sample',
        'warmupSeconds': 0 if cold else args.warmup, 'reusedDocument': reuse,
        'previewWarmupSeconds': .65 if name == 'preview-idle' else None,
        'steadySeconds': args.steady if name.endswith('-idle') else None,
        'setup': setup, 'shaderProbeBeforeInput': shader_check, 'sample': sample,
        'performanceMetrics': {'before': before, 'after': after, 'delta': metric_delta(before, after),
                               'wallWindowMs': round(cpu_window_ms, 3),
                               'note': 'CDP metric window begins just before arming and includes input dispatch, '
                                       'settle confirmation and result retrieval; rAF window is trimmed to motion.'},
        'trace': trace_result, 'presentedFrames': None, 'intervention': intervention,
    }
    result['valid'] = not sample.get('timedOut') and not sample['errors'] and (
        sample['final']['snap']['settledIndex'] == target)
    if name == 'quick-hero-return':
        sample['quickHeroReturn'] = hero_return_summary(sample)
        result['valid'] = result['valid'] and not sample['quickHeroReturn']['invalidReasons']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765/universe.html')
    parser.add_argument('--output', default='/private/tmp/universe-checks/scroll-benchmark.json')
    parser.add_argument('--quick', action='store_true', help='One repetition at CPU 1; omit trackpad/reversal/cold cases')
    parser.add_argument('--devices', default='desktop,mobile', help='Comma-separated desktop,desktop-retina,mobile')
    parser.add_argument('--themes', default='real,toon', help='Comma-separated real,toon')
    parser.add_argument('--cpu', help='Comma-separated CPU slowdown factors; default 1,4 (quick: 1)')
    parser.add_argument('--cases', help='Comma-separated cases: ' + ','.join(CASES))
    parser.add_argument('--repeats', type=int, help='Default 3; quick: 1')
    parser.add_argument('--warmup', type=float, default=3.5, help='Warmup before each interaction in seconds')
    parser.add_argument('--reuse-page', action='store_true', help='Reuse the document and GPU device between matching warm trials')
    parser.add_argument('--steady', type=float, default=2, help='Steady planet/preview sample duration in seconds')
    parser.add_argument('--timeout', type=float, default=25)
    parser.add_argument('--stall-ms', type=float, default=200, help='Controlled blocking duration for stall-scroll')
    parser.add_argument('--trace-dir', help='Optional directory for per-sample CDP traces; adds profiling overhead')
    args = parser.parse_args()
    devices, themes = csv_list(args.devices), csv_list(args.themes)
    cpus = [float(n) for n in csv_list(args.cpu or ('1' if args.quick else '1,4'))]
    cases = csv_list(args.cases) if args.cases else [
        name for name in CASES if not (args.quick and name in ['trackpad-burst', 'rapid-retarget', 'cold-wheel'])]
    repeats = args.repeats if args.repeats is not None else (1 if args.quick else 3)
    if (not devices or set(devices) - set(DEVICES) or not themes or set(themes) - {'real', 'toon'}
            or not cases or set(cases) - set(CASES) or not cpus or any(cpu < 1 for cpu in cpus)
            or repeats < 1 or args.warmup < 0 or args.steady <= 0 or args.timeout <= 0
            or args.stall_ms <= 0):
        parser.error('Invalid device, theme, case, CPU rate, repeat count or duration')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    browser = None
    report = {
        'createdAtUTC': datetime.now(timezone.utc).isoformat(), 'url': args.url,
        'parameters': vars(args), 'browser': None,
        'host': {'platform': platform.platform(), 'machine': platform.machine()},
        'environment': 'Isolated local Chrome tab, focus emulation, host GPU, emulated viewport/input/CPU. '
                       'Physical device, display refresh, thermal and power state are not measured.',
        'presentedFrameMeasurement': 'Not available from rAF. Optional traces preserve compositor evidence; '
                                     'do not treat callback statistics as presented FPS.',
        'runs': [], 'failures': [], 'cleanupErrors': [],
    }
    script_id = None
    try:
        browser = Browser(new_tab=True)
        report['browser'] = browser.call('Browser.getVersion')
        browser.call('Emulation.setFocusEmulationEnabled', {'enabled': True})
        browser.call('Emulation.setEmulatedMedia', {'features': []})
        browser.call('Performance.enable', {'timeDomain': 'timeTicks'})
        # Explicit query theme cannot override an existing saved toon preference.
        # Clearing just that preference in this test document keeps trials valid.
        source = "try { localStorage.removeItem('universeTheme'); } catch {}\n" + PROBE
        script_id = browser.call('Page.addScriptToEvaluateOnNewDocument', {'source': source})['identifier']
        for device in devices:
            for theme in themes:
                for cpu in cpus:
                    for repetition in range(1, repeats + 1):
                        for name in cases:
                            if name.startswith('touch-') and device != 'mobile':
                                continue
                            label = f'{device}/{theme}/CPU {cpu:g}/{name}/{repetition}'
                            try:
                                result = run_case(browser, args, name, device, theme, cpu, repetition)
                                report['runs'].append(result)
                                print(json.dumps({'run': label, 'valid': result['valid'],
                                    'raf': result['sample']['callbackSummary'],
                                    'metrics': result['performanceMetrics']['delta'],
                                    'forcedStyleAndLayoutMs': result['sample']['forcedStyleAndLayoutMs'],
                                    'inputToFirstObservedMotionMs': result['sample']['inputToFirstObservedMotionMs']}), flush=True)
                            except Exception as error:
                                failure = {'run': label, 'error': str(error),
                                           'exceptionType': type(error).__name__}
                                if hasattr(error, 'trace_cleanup_error'):
                                    failure['traceCleanupError'] = error.trace_cleanup_error
                                report['failures'].append(failure)
                                print(json.dumps({'run': label, 'error': str(error)}), flush=True)
                            output.write_text(json.dumps(report, indent=2) + '\n')
    except Exception as error:
        report['failures'].append({'run': 'browser-setup-or-harness',
                                   'error': str(error), 'exceptionType': type(error).__name__})
    finally:
        if browser is not None:
            cleanup = []
            if script_id:
                cleanup.append(('remove-probe', lambda: browser.call(
                    'Page.removeScriptToEvaluateOnNewDocument', {'identifier': script_id})))
            cleanup.extend([
                ('reset-cpu-throttle', lambda: browser.call('Emulation.setCPUThrottlingRate', {'rate': 1})),
                ('close-test-tab', browser.close),
                ('close-local-websocket', browser.ws.close),
            ])
            for name, operation in cleanup:
                try:
                    operation()
                except Exception as error:
                    report['cleanupErrors'].append({'action': name, 'error': str(error),
                                                    'exceptionType': type(error).__name__})
        output.write_text(json.dumps(report, indent=2) + '\n')
    invalid = sum(not run['valid'] for run in report['runs'])
    print(f"Saved {len(report['runs'])} samples, {invalid} invalid, {len(report['failures'])} failures to {output}", flush=True)
    return 1 if invalid or report['failures'] or report['cleanupErrors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
