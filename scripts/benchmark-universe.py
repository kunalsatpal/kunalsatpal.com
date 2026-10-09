"""Compare startup, stationary planet rendering and a scripted full-page scroll.

Local Chrome measurements are not a substitute for profiling on a physical phone.
"""
import argparse
import json
import time
from pathlib import Path
from browser_tools import Browser

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', required=True)
parser.add_argument('--output', default='/private/tmp/universe-checks/benchmark.json')
args = parser.parse_args()
b = Browser()
b.call('Storage.clearDataForOrigin', {'origin':'http://127.0.0.1:8765', 'storageTypes':'local_storage'})
b.call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
b.call('Emulation.setTouchEmulationEnabled', {'enabled':True})
b.call('Performance.enable')
script_id = b.call('Page.addScriptToEvaluateOnNewDocument', {'source':"window.__long=[];new PerformanceObserver(l=>__long.push(...l.getEntries().map(x=>({start:x.startTime,duration:x.duration})))).observe({type:'longtask',buffered:true});"})['identifier']
sample = """(scrolling => new Promise(resolve=>{
  let previous=null, start=null, intervals=[];
  const duration=scrolling?12000:3000;
  const height=document.getElementById('journey').offsetHeight-innerHeight;
  function frame(t){
    if(start===null)start=t;
    if(previous!==null)intervals.push(t-previous);
    previous=t;
    if(scrolling)scrollTo(0,height*Math.min(1,(t-start)/duration));
    if(t-start<duration)requestAnimationFrame(frame);
    else {intervals.sort((a,b)=>a-b);resolve({frames:intervals.length,p50:intervals[Math.floor(intervals.length*.5)],p95:intervals[Math.floor(intervals.length*.95)],over33:intervals.filter(x=>x>33.4).length})}
  }
  requestAnimationFrame(frame);
}))"""
def metrics():
    return {m['name']:m['value'] for m in b.call('Performance.getMetrics')['metrics']}

report = {'environment':'Local headless Chrome; mobile viewport 390x844, DPR 3, touch emulation; actual host GPU; no CPU throttling', 'runs':[]}
try:
    for page in [args.baseline, 'http://127.0.0.1:8765/universe.html']:
        for mode in ['planet','scroll']:
            b.navigate(page + ('?at=0.25&perf' if mode == 'planet' else '?perf'))
            b.js("localStorage.removeItem('universeTheme')")
            time.sleep(6)
            startup=b.js('__long')
            before=metrics()
            frames=[b.js(sample + ('(false)' if mode=='planet' else '(true)')) for _ in range(3 if mode=='planet' else 1)]
            after=metrics()
            result={'page':page,'mode':mode,'startupLongTasks':startup,'frames':frames,
                    'cpuMs':{k:round((after[k]-before[k])*1000,2) for k in ['TaskDuration','ScriptDuration','LayoutDuration','RecalcStyleDuration']}}
            report['runs'].append(result)
            print(json.dumps(result),flush=True)
finally:
    b.call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':script_id})
output=Path(args.output)
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(report,indent=2)+'\n')
