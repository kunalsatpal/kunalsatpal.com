"""One focused gesture-response check; no performance benchmark loop."""
import argparse
import json
import time
from browser_tools import Browser

parser = argparse.ArgumentParser()
parser.add_argument('--resume-at-return', action='store_true', help='Skip already checked controller, cache and wheel cases')
args = parser.parse_args()
b = Browser(new_tab=True)


def wait(expression, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if b.js(expression):
            return
        time.sleep(.05)
    raise AssertionError(expression)


def landed(index):
    wait(f"universePerformance().snap.phase==='idle' && universePerformance().snap.settledIndex==={index} && !universePerformance().compositor.active")
    assert b.js(f"Math.abs(scrollY-({index}/8)*(document.querySelector('#journey').offsetHeight-innerHeight))<2")
    print('Exact landing at ' + str(index), flush=True)


def go(index):
    b.js(f"document.querySelector('.stop[data-i=\"{index}\"]').dispatchEvent(new MouseEvent('click',{{bubbles:true}}))")


try:
    b.call('Emulation.setFocusEmulationEnabled', {'enabled': True})
    b.call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 2, 'mobile': False})
    b.navigate('http://127.0.0.1:8765/universe.html?perf&scene=gojek')
    wait("typeof universePerformance==='function'")
    if not args.resume_at_return:
        print(b.js("import('/scripts/test-universe-input.mjs').then(m=>m.testGestureResponse())"), flush=True)
        print(b.js("import('/scripts/test-universe-input.mjs').then(m=>m.testPreparedFlight())"), flush=True)
        landed(3)
        wait('universePerformance().compositor.cachedPoses>=4')
        print('Planet neighbors prepared while idle', flush=True)
        b.call('Input.dispatchMouseEvent', {'type': 'mouseWheel', 'x': 720, 'y': 450, 'deltaX': 0, 'deltaY': 1400})
        wait('universePerformance().compositor.aligned')
        assert b.js("universePerformance().snap.targetIndex===4 && universePerformance().compositor.scenes.sort().join(',')==='cult,gojek'")
        landed(4)
        b.call('Input.dispatchMouseEvent', {'type': 'mouseWheel', 'x': 720, 'y': 450, 'deltaX': 0, 'deltaY': -1400})
        wait('universePerformance().snap.targetIndex===3')
        print('Fresh reverse gesture starts during the former landing cooldown', flush=True)
        landed(3)
    else:
        landed(3)

    go(0)
    landed(0)
    assert b.js("document.querySelector('#object img.logo').naturalWidth>0 && Math.abs(document.querySelector('#object img.logo').getBoundingClientRect().width-46)<.2")
    print('Quick landing return retains its logo and selected-page arrival', flush=True)
    go(2)
    landed(2)
    b.call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 3, 'mobile': True})
    b.call('Emulation.setTouchEmulationEnabled', {'enabled': True})
    wait("universePerformance().viewport.width===390 && universePerformance().snap.phase==='idle'")
    b.call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': 195, 'y': 650}]})
    b.call('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': 195, 'y': 580}]})
    wait("universePerformance().snap.phase==='snapping' && universePerformance().snap.touchActive")
    print('Planet flight starts while the finger is still down', flush=True)
    landed(3)
    b.call('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': 195, 'y': 450}]})
    b.call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    time.sleep(.2)
    assert b.js("universePerformance().snap.settledIndex===3 && universePerformance().snap.phase==='idle'")
    print('Continued swipe and release commit only one view', flush=True)
    errors = [event for event in b.events if event.get('method') == 'Runtime.exceptionThrown']
    assert not errors, errors
    print(json.dumps({'focusedChecks': 'passed', 'uncaughtErrors': len(errors)}), flush=True)
finally:
    b.close()
