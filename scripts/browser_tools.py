"""Small Chrome DevTools client for local asset generation and performance checks.
Requires websocket-client; connect only to an isolated local debugging browser.
"""
import json, urllib.request, websocket, time, base64

class Browser:
    def __init__(self):
        tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list'))
        self.ws = websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page'), origin='http://localhost:9222', timeout=60)
        self.seq = 0
        self.events = []
        self.call('Runtime.enable')
        self.call('Page.enable')
        self.call('Network.enable')
        self.call('Network.setCacheDisabled', {'cacheDisabled': True})
    def call(self, method, params=None):
        self.seq += 1
        self.ws.send(json.dumps({'id':self.seq,'method':method,'params':params or {}}))
        while True:
            msg=json.loads(self.ws.recv())
            if msg.get('id') == self.seq:
                if 'error' in msg: raise RuntimeError(msg['error'])
                return msg.get('result',{})
            self.events.append(msg)
    def js(self, expression):
        r=self.call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
        if 'exceptionDetails' in r: raise RuntimeError(r['exceptionDetails'])
        return r.get('result',{}).get('value')
    def navigate(self, url):
        self.events=[]
        self.call('Page.navigate',{'url':url})
        for _ in range(150):
            time.sleep(.1)
            if self.js("document.querySelectorAll('.scene').length === 9 && !!document.querySelector('.mini')"):
                return
        raise RuntimeError('Page did not initialize')
    def screenshot(self,path):
        data=self.call('Page.captureScreenshot',{'format':'png'})['data']
        open(path,'wb').write(base64.b64decode(data))
