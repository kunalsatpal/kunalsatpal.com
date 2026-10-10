"""Case-study navigation checks using the local browser setup in docs/universe-performance.md."""
import time, json
from browser_tools import Browser
b=Browser()
base='http://127.0.0.1:8765/'
checks=[]
def wait(expr, timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if b.js(expr): return
        time.sleep(.05)
    raise AssertionError('Timed out: '+expr)
def check(value, label):
    assert value,label
    checks.append(label)
    print(label,flush=True)
def ready():
    wait("!!document.querySelector('#nextMoons .nextmoon') && !document.body.classList.contains('arriving')")
    time.sleep(.35)
for width,height in [(1440,900),(390,844)]:
    b.call('Emulation.setDeviceMetricsOverride', {'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<500})
    for key,planet in [('promo','gojek'),('Fitclub','cult'),('cart_abandonment','cult')]:
        b.call('Page.navigate',{'url':base+'case.html?c='+key})
        ready()
        check(b.js("getComputedStyle(document.querySelector('#world')).opacity === '1' && getComputedStyle(document.querySelector('#world')).transform === 'none' && document.querySelector('#lander img').naturalWidth > 0"),f'{width} {key}: visible hero, loaded image, stable page geometry')
        b.js("scrollTo(0, document.documentElement.scrollHeight-innerHeight)")
        time.sleep(.2)
        # Capture page geometry in the middle of the exit, before location changes.
        result=b.js("""new Promise(resolve=>{
          const before={y:scrollY,height:document.documentElement.scrollHeight};
          document.querySelector('#back2').click(); document.querySelector('#back2').click();
          setTimeout(()=>resolve({before,y:scrollY,height:document.documentElement.scrollHeight,
            transform:getComputedStyle(document.querySelector('#world')).transform,
            filter:getComputedStyle(document.querySelector('#world')).filter}),120)
        })""")
        check(result['transform']=='none' and result['filter']=='none' and abs(result['height']-result['before']['height'])<2 and abs(result['y']-result['before']['y'])<2,f'{width} {key}: closing from article bottom preserves scroll and layout: {result}')
        wait("location.pathname.endsWith('universe.html') && !!document.querySelector('.mini')")
        wait("document.querySelector('.scene[data-scene=\""+planet+"\"]')?.classList.contains('active')")
        time.sleep(.5)
        check(b.js("getComputedStyle(document.querySelector('#camera')).opacity === '1' && document.querySelector('#camera').style.transform === ''"), f'{width} {key}: Back to orbit shows the correct planet')
        history=b.call('Page.getNavigationHistory')
        entry=history['entries'][history['currentIndex']-1]
        b.call('Page.navigateToHistoryEntry',{'entryId':entry['id']})
        ready()
        check(b.js("!document.body.classList.contains('leaving') && !document.documentElement.classList.contains('lenis-stopped')"),f'{width} {key}: browser Back restores visibility and scrolling')
        # Cached-page lifecycle must also work when a browser elects to reload history.
        b.js("document.querySelector('#back').click();dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
        time.sleep(.4)
        check(b.js("location.pathname.endsWith('case.html') && getComputedStyle(document.querySelector('#world')).opacity === '1' && !document.documentElement.classList.contains('lenis-stopped')"),f'{width} {key}: cached restoration cancels pending navigation')
        b.js("scrollTo(0,0)")
        if key=='promo': b.screenshot('/tmp/case-navigation-'+str(width)+'.png')
# Link semantics and switching between case studies.
check(b.js("(()=>{let prevented; document.addEventListener('click', e=>{prevented=e.defaultPrevented;e.preventDefault()},{once:true}); const e=new MouseEvent('click',{bubbles:true,cancelable:true,ctrlKey:true});document.querySelector('.nextmoon').dispatchEvent(e);return prevented===false})()"),'Modified next-case clicks retain native browser behavior')
next_url=b.js("document.querySelector('.nextmoon').href")
b.js("document.querySelector('.nextmoon').click()")
wait('location.href === '+json.dumps(next_url));ready()
check(True,'Next case opens and reveals correctly')
b.call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
b.call('Page.navigate',{'url':base+'case.html?c=promo'});ready()
b.js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
wait("location.pathname.endsWith('universe.html') && !!document.querySelector('.mini')")
check(True,'Reduced-motion Escape navigation returns to orbit')
b.call('Emulation.setEmulatedMedia',{'features':[]})
b.call('Page.navigate', {'url':base+'universe.html?scene=gojek'})
wait("!!document.querySelector('.scene[data-scene=gojek] .moon.open')")
time.sleep(.6)
b.js("document.querySelector('.scene[data-scene=gojek] .moon.open').click()")
wait("location.pathname.endsWith('case.html')"); ready()
check(True,'Universe moon opens the case study')
history=b.call('Page.getNavigationHistory')
entry=history['entries'][history['currentIndex']-1]
b.call('Page.navigateToHistoryEntry', {'entryId':entry['id']})
wait("location.pathname.endsWith('universe.html') && !!document.querySelector('.mini')")
time.sleep(.6)
check(b.js("getComputedStyle(document.body).opacity === '1' && document.querySelector('#camera').style.filter === '' && !document.documentElement.classList.contains('lenis-stopped')"),'Browser Back restores the universe without a frozen fade or stopped scrolling')
print(json.dumps({'passed':len(checks)},indent=2))
