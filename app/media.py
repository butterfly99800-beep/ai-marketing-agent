import asyncio,ipaddress,socket,shutil,subprocess,json,wave,re,os
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from app.config import ROOT,DATA
from app.deepseek import ProviderError
NODE=os.getenv('NODE_BINARY') or shutil.which('node') or (r'D:\soft\node.exe' if os.name=='nt' else 'node')
def public_url(url):
 u=urlsplit(url)
 if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.port not in (None,80,443):raise ProviderError('仅支持公开HTTP/HTTPS地址')
 try:
  records=socket.getaddrinfo(u.hostname,u.port or 443)
  addresses=[ipaddress.ip_address(r[4][0]) for r in records]
  # Local proxy Fake-IP range is never trusted as a real destination. Verify public DNS.
  if addresses and all(isinstance(a,ipaddress.IPv4Address) and a in ipaddress.ip_network('198.18.0.0/15') for a in addresses):
   try:ipaddress.ip_address(u.hostname);raise ProviderError('不允许直接访问代理伪地址')
   except ValueError:pass
   if re.fullmatch(r'dashscope-result-[a-z0-9-]+\.oss-[a-z0-9-]+\.aliyuncs\.com',u.hostname) and '-internal' not in u.hostname:
    # Fixed public vendor CDN, authenticated by HTTPS in the downloader; not arbitrary website hosts.
    return url
   addresses=[]
   # Proxy Fake-IP is checked against independent public DNS. A broken IPv6 lookup
   # must not discard an already valid IPv4 answer.
   for endpoint in ('https://dns.alidns.com/resolve','https://cloudflare-dns.com/dns-query','https://dns.google/resolve'):
    for typ in ('A','AAAA'):
     try:
      res=httpx.get(endpoint,params={'name':u.hostname,'type':typ},headers={'Accept':'application/dns-json'},timeout=5);res.raise_for_status()
      addresses.extend(ipaddress.ip_address(a['data']) for a in res.json().get('Answer',[]) if a.get('type') in (1,28))
     except (httpx.HTTPError,ValueError):continue
     if addresses:break
    if addresses:break
  if not addresses or any(not a.is_global for a in addresses):raise ProviderError('不允许访问本机、内网或特殊地址')
 except (OSError,httpx.HTTPError,ValueError) as e:raise ProviderError('网址解析或公开DNS校验失败') from e
 return url
async def download(url,path,limit=80*1024*1024):
 public_url(url)
 async with httpx.AsyncClient(timeout=90,follow_redirects=False) as c:
  async with c.stream('GET',url) as r:
   if r.status_code!=200:raise ProviderError('生成素材下载失败')
   length=0;tmp=path.with_suffix(path.suffix+'.part')
   try:
    with tmp.open('wb') as f:
     async for chunk in r.aiter_bytes():
      length+=len(chunk)
      if length>limit:raise ProviderError('素材文件超过大小限制')
      f.write(chunk)
    tmp.replace(path)
   finally:tmp.unlink(missing_ok=True)
async def capture(project):
 public_url(project['source']);directory=DATA/project['id']
 proc=await asyncio.create_subprocess_exec(NODE,str(ROOT/'renderer/capture.cjs'),project['source'],str(directory),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 try:await asyncio.wait_for(proc.communicate(),180)
 except asyncio.TimeoutError:await stop_owned(proc);raise ProviderError('网站截图超时')
 except asyncio.CancelledError:await stop_owned(proc);raise
 if proc.returncode:raise ProviderError('网站截图失败，网站可能限制访问或地址不受支持。')
 return json.loads((directory/'site.json').read_text(encoding='utf-8'))
def speak(text,path,seconds):
 if os.name!='nt':raise ProviderError('Linux不支持Windows系统音色，请选择云端音色或安装Kokoro模型。')
 # Invoke a fixed local script; narration is UTF-8 data in a file, never shell code.
 source=path.with_suffix('.txt');source.write_text(text,encoding='utf-8-sig')
 command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'renderer/speak.ps1'),str(source),str(path)]
 for rate in (1,2,3,4,5,6):
  result=subprocess.run(command+[str(rate)],capture_output=True,timeout=40)
  if result.returncode:raise ProviderError('本地旁白失败，请检查Windows语音包')
  with wave.open(str(path)) as w:duration=w.getnframes()/w.getframerate()
  if duration<=seconds-.2:return duration
 raise ProviderError('旁白超出可读语速范围，请将此镜头旁白精简后重试。')
 
async def stop_owned(proc):
 if proc.returncode is None:
  if __import__('os').name=='nt':
   await asyncio.to_thread(subprocess.run,['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=10)
  else:proc.kill()
  await proc.wait()

