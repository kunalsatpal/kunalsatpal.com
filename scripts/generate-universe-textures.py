"""Generate identical browser Canvas textures once, rather than on every page load.

Start the preview server on 8765 and isolated Chrome on debugging port 9222.
Install websocket-client in a development virtualenv, then run this script.
"""
import base64
import hashlib
import json
import time
from pathlib import Path
from browser_tools import Browser

root = Path(__file__).resolve().parents[1]
browser = Browser()
browser.call('Page.navigate', {'url': 'http://127.0.0.1:8765/scripts/'})
deadline = time.monotonic() + 10
while not browser.js("location.pathname === '/scripts/' && document.readyState === 'complete'"):
    if time.monotonic() > deadline:
        raise RuntimeError('Local preview server did not become ready')
    time.sleep(.1)
files = browser.js("import('/scripts/generate-universe-textures.mjs').then(m => m.generateTextures())")
output = root / 'site/textures/universe'
output.mkdir(parents=True, exist_ok=True)
manifest = {}
for name, url in files.items():
    data = base64.b64decode(url.split(',', 1)[1])
    (output / name).write_bytes(data)
    manifest[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Generated {len(files)} textures ({sum(v["bytes"] for v in manifest.values()):,} bytes).')
