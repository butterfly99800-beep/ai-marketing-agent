"""Run the local studio and the exact Google OAuth callback port together."""
import os,sys,subprocess,time,socket,webbrowser,json
from urllib.request import urlopen
from app.config import ROOT
def listening(port):
 with socket.socket() as s:s.settimeout(.4);return s.connect_ex(('127.0.0.1',port))==0
def main():
 processes=[];logs=[];folder=ROOT/'work';folder.mkdir(exist_ok=True)
 try:
  for port,module,health in [(8020,'app.main:app','/api/config'),(8000,'app.youtube_bridge:app','/health')]:
   if listening(port):
    try:
     with urlopen('http://localhost:'+str(port)+health,timeout=3) as r:json.load(r)
    except Exception:raise RuntimeError(f'Port {port} is in use by another service. Stop it before starting this studio.')
    continue
   log=(folder/('server-'+str(port)+'.log')).open('a',encoding='utf8');logs.append(log)
   process=subprocess.Popen([sys.executable,'-m','uvicorn',module,'--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],cwd=ROOT,stdout=log,stderr=log);processes.append(process)
  for _ in range(30):
   if listening(8020) and listening(8000):break
   if any(p.poll() is not None for p in processes):raise RuntimeError('A service failed to start. Check work/server-8020.log and server-8000.log.')
   time.sleep(.3)
  else:raise RuntimeError('Services did not become ready.')
  print('Studio: http://localhost:8020/\nOperations: http://localhost:8020/operations.html\nYouTube callback: http://localhost:8000/api/auth/youtube/callback\nPress Ctrl+C to stop services started by this launcher.')
  webbrowser.open('http://localhost:8020/')
  while processes:
   if any(p.poll() is not None for p in processes):break
   time.sleep(1)
 except KeyboardInterrupt:pass
 finally:
  for p in processes:
   if p.poll() is None:p.terminate()
  for p in processes:
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:p.kill()
  for log in logs:log.close()
if __name__=='__main__':main()
