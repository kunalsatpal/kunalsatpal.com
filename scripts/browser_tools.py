"""Small Chrome DevTools client for local asset generation and performance checks.
Requires websocket-client; connect only to an isolated local debugging browser.
"""
import json, urllib.request, websocket, time, base64

class Browser:
    def __init__(self, new_tab=False):
        if new_tab:
            request = urllib.request.Request('http://127.0.0.1:9222/json/new?about:blank', method='PUT')
            tab = json.load(urllib.request.urlopen(request))
        else:
            tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list'))
            tab = next(t for t in tabs if t['type'] == 'page')
        self.target_id = tab['id'] if new_tab else None
        self.ws = websocket.create_connection(tab['webSocketDebuggerUrl'], origin='http://localhost:9222', timeout=60)
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

    def close(self):
        if self.target_id:
            self.call('Target.closeTarget', {'targetId': self.target_id})
        self.ws.close()
