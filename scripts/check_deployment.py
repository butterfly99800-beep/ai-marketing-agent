"""Local preflight; never sends credentials or invokes paid APIs."""
import sys,json,subprocess,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from app.creative import licensed_music
from app.config import CONFIG
import fastapi,httpx,cryptography,bs4,pypdf,docx,imageio_ffmpeg
pool=licensed_music();assert len(pool)>=20,'Required audio files missing'
catalog=json.loads((root/'web/showcase/catalog.json').read_text(encoding='utf8'));assert len(catalog['items'])==3
for item in catalog['items']:assert (root/'web'/item['video'].lstrip('/')).is_file()
node=shutil.which('node');assert node,'Node.js is required'
r=subprocess.run([node,'-e',"const fs=require('fs');const p=process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':require('playwright').chromium.executablePath();if(!fs.existsSync(p))process.exit(1);console.log('Chromium ready')"],cwd=root/'renderer',capture_output=True,text=True)
assert r.returncode==0,'Run npx playwright install chromium'
print('Preflight OK: dependencies, audio, public samples and browser. No paid API calls were made.')
