from pathlib import Path
import os,re
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'work/projects';DATA.mkdir(parents=True,exist_ok=True)
def load_credentials():
 values={}; pending=None
 path=ROOT/'api保存位置.env'
 if path.exists():
  for raw in path.read_text(encoding='utf-8-sig').splitlines():
   line=raw.strip()
   if not line or line.startswith('#'):continue
   m=re.match(r'^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.*)$',line)
   if m:values[m[1]]=m[2].strip().strip('\"\'');pending=None;continue
   if 'deepseek' in line.lower():pending='DEEPSEEK_API_KEY';v=re.split(r'[:：=]',line,maxsplit=1);value=v[1].strip() if len(v)>1 else '';values.update({pending:value} if value.startswith('sk-') else {});continue
   if '万相' in line or '万象' in line:pending='DASHSCOPE_API_KEY';v=re.split(r'[:：=]',line,maxsplit=1);value=v[1].strip() if len(v)>1 else '';values.update({pending:value} if value.startswith('sk-') else {});continue
   if pending and line.startswith('sk-'):values[pending]=line;pending=None
 for key in ['DEEPSEEK_API_KEY','DASHSCOPE_API_KEY','DEEPSEEK_MODEL','WAN_IMAGE_MODEL','WAN_VIDEO_MODEL','DASHSCOPE_BASE_URL','QWEN_TTS_MODEL']:
  if os.getenv(key):values[key]=os.environ[key]
 return values
CONFIG=load_credentials()
MODEL=CONFIG.get('DEEPSEEK_MODEL','deepseek-flash')
IMAGE_MODEL=CONFIG.get('WAN_IMAGE_MODEL','wan2.2-t2i-flash')
VIDEO_MODEL=CONFIG.get('WAN_VIDEO_MODEL','wan2.2-i2v-flash')
WAN_BASE=CONFIG.get('DASHSCOPE_BASE_URL','https://dashscope.aliyuncs.com').rstrip('/')
