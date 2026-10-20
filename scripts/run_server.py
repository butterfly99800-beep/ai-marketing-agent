"""One worker: in-process task locks must not be split across workers."""
import os,sys,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
if (root/'.env').exists():
 for raw in (root/'.env').read_text(encoding='utf-8-sig').splitlines():
  match=re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$",raw.strip())
  if match:os.environ.setdefault(match[1],match[2].strip().strip('\"\''))
if __name__=='__main__':
 import uvicorn
 uvicorn.run('app.main:app',host='127.0.0.1',port=8020,workers=1,proxy_headers=True,forwarded_allow_ips='127.0.0.1',access_log=False)
