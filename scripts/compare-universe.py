"""Deterministic visual regression comparison; requires Pillow and websocket-client."""
import argparse,time,json
from pathlib import Path
from browser_tools import Browser
from PIL import Image,ImageChops,ImageStat
parser = argparse.ArgumentParser()
parser.add_argument('--baseline', required=True, help='Original universe HTML URL, served alongside its relative assets')
parser.add_argument('--output', default='/private/tmp/universe-checks')
args = parser.parse_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
b=Browser()
b.call('Storage.clearDataForOrigin', {'origin':'http://127.0.0.1:8765', 'storageTypes':'local_storage'})
b.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
b.call('Emulation.setTouchEmulationEnabled',{'enabled':True})
# Compare DOM/CSS/texture rendering at the same clock; GPU shader output is stochastic
# and is tested separately at full quality by the functional browser checks.
injection="""Object.defineProperty(Navigator.prototype,'gpu',{get:()=>undefined});
window.__clock=0;const raf=window.requestAnimationFrame.bind(window);window.requestAnimationFrame=f=>raf(()=>f(window.__clock));
let seed=42;Math.random=()=>((seed=(seed*16807)%2147483647)/2147483647);"""
sid=b.call('Page.addScriptToEvaluateOnNewDocument',{'source':injection})['identifier']
report=[]
for theme in ['real','toon']:
 for scene,at in [('hero',0),('hinge',.25),('transition',.30),('galaxy',.625)]:
  shots=[]
  for page,name in [(args.baseline,'before'),('http://127.0.0.1:8765/universe.html','after')]:
   b.navigate(page+f'?at={at}&theme={theme}')
   b.js("localStorage.removeItem('universeTheme')")
   b.js('document.fonts.ready')
   time.sleep(.4)
   b.js('window.__clock=8000')
   time.sleep(.3)
   b.js("document.getAnimations().forEach(a=>{a.pause();a.currentTime=2000});document.querySelectorAll('svg').forEach(s=>{s.pauseAnimations?.();s.setCurrentTime?.(2)});document.body.classList.remove('arriving')")
   time.sleep(.15)
   path=str(output / f'{theme}-{scene}-{name}.png')
   b.screenshot(path);shots.append(path)
  a,c=[Image.open(p).convert('RGB') for p in shots]
  diff=ImageChops.difference(a,c);stat=ImageStat.Stat(diff)
  changed=sum(1 for p in diff.getdata() if max(p)>10)
  report.append({'theme':theme,'scene':scene,'mean_channel_difference':sum(stat.mean)/3,'pixels_diff_over_10_percent':100*changed/(a.width*a.height)})
  print(report[-1],flush=True)
b.call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':sid})
open(output / 'visual-diff.json','w').write(json.dumps(report,indent=2))
