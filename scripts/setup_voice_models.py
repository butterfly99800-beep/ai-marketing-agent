from pathlib import Path
import httpx,hashlib,json,concurrent.futures
r=Path(__file__).resolve().parents[1];folder=r/'models/kokoro';folder.mkdir(parents=True,exist_ok=True)
base='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
items={'kokoro-v1.1-zh.onnx':base+'kokoro-v1.1-zh.onnx','voices-v1.1-zh.bin':base+'voices-v1.1-zh.bin','config.json':'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/raw/main/config.json','MODEL_CARD.md':'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/raw/main/README.md','MODEL_LICENSE.txt':'https://www.apache.org/licenses/LICENSE-2.0.txt','RUNTIME_LICENSE.txt':'https://raw.githubusercontent.com/thewh1teagle/kokoro-onnx/main/LICENSE'}
def get(item):
 name,url=item;file=folder/name
 if file.exists() and file.stat().st_size>100:print('EXISTS',name,flush=True);return
 with httpx.Client(follow_redirects=True,timeout=120) as client:
  with client.stream('GET',url) as response:
   response.raise_for_status()
   with file.with_suffix(file.suffix+'.part').open('wb') as out:
    for data in response.iter_bytes():out.write(data)
 file.with_suffix(file.suffix+'.part').replace(file);print('DOWNLOADED',name,file.stat().st_size,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for future in [pool.submit(get,i) for i in items.items()]:
  try:future.result()
  except Exception as e:print('FAILED',type(e).__name__,str(e).split('For more')[0][:180],flush=True)
manifest=[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in folder.iterdir() if p.is_file() and not p.name.endswith('.part')]
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
