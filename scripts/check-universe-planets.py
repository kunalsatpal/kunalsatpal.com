"""Focused pixel-equivalence and GPU recovery check, without an FPS campaign.
Uses the isolated preview server and debugging Chrome from universe-performance.md.
"""
import json
import time
from PIL import Image, ImageChops, ImageStat
from browser_tools import Browser

b = Browser(new_tab=True)
try:
    b.call('Emulation.setDeviceMetricsOverride', {
        'width': 1440, 'height': 900, 'deviceScaleFactor': 2, 'mobile': False,
    })
    b.call('Page.navigate', {'url': 'http://127.0.0.1:8765/scripts/browser_tools.py'})
    time.sleep(.2)
    boxes = b.js("import('/scripts/test-universe-planets.mjs').then(m=>m.planetFixtures())")
    path = '/private/tmp/universe-planet-comparison.png'
    b.screenshot(path)
    screenshot = Image.open(path).convert('RGB')
    for box in boxes:
        native = screenshot.crop(tuple(round(v * 2) for v in box['native']))
        gpu = screenshot.crop(tuple(round(v * 2) for v in box['gpu']))
        diff = ImageChops.difference(native, gpu)
        mean = sum(ImageStat.Stat(diff).mean) / 3
        histogram = diff.histogram()
        combined = [sum(histogram[i + 256 * c] for c in range(3)) for i in range(256)]
        threshold, count, p95 = sum(combined) * .95, 0, 0
        for value, pixels in enumerate(combined):
            count += pixels
            if count >= threshold:
                p95 = value
                break
        assert mean < 1 and p95 <= 3, (box, mean, p95)
        print(json.dumps({'key': box['key'], 'time': box['time'], 'mean': mean, 'p95': p95}), flush=True)
    print(b.js("import('/scripts/test-universe-planets.mjs').then(m=>m.testPlanetFallback())"), flush=True)
    errors = [e for e in b.events if e.get('method') == 'Runtime.exceptionThrown']
    assert not errors, errors
finally:
    b.close()
