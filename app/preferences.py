import re
from app.audio_catalog import VOICE_PROFILES
def apply_preferences(p,req):
 for key in ('aspect_ratio','narration_enabled','pace'):
  value=getattr(req,key,None)
  if value is not None:p[key]=value
 values=getattr(req,'platforms',None)
 if values is not None:
  p['platforms']=list(dict.fromkeys(values))
  if values:p['platform']=values[0]
 # Natural language overrides defaults without deriving orientation from a platform name.
 message=getattr(req,'text',None) or getattr(req,'source','')
 found=[]
 for code,pattern in [('douyin',r'抖音'),('shorts',r'shorts'),('youtube',r'youtube(?!\s*shorts)|油管'),('xiaohongshu',r'小红书'),('bilibili',r'哔哩|b站'),('instagram',r'instagram')]:
  if re.search(pattern,message,re.I):found.append(code)
 if found:p['platforms']=found if re.search(r'只发|仅发',message) else list(dict.fromkeys(p.get('platforms',[])+found));p['platform']=p['platforms'][0]
 if re.search(r'竖[版屏]|9\s*[:：]\s*16',message):p['aspect_ratio']='9:16'
 elif re.search(r'横[版屏]|16\s*[:：]\s*9',message):p['aspect_ratio']='16:9'
 elif re.search(r'方[版屏形]|1\s*[:：]\s*1',message):p['aspect_ratio']='1:1'
 if re.search(r'去掉配音|无配音|关闭配音|不(?:要|用|加|需要)配音',message):p['narration_enabled']=False
 elif re.search(r'开启配音|加上配音|需要配音',message):p['narration_enabled']=True
 if re.search(r'慢一点|舒缓节奏',message):p['pace']='balanced'
 elif re.search(r'快一点|快节奏|快剪',message):p['pace']='fast'
 if re.search(r'男声|女声',message) and not (p.get('sound_preferences') or {}).get('voice'):
  p.setdefault('sound_preferences',{})['voice']='kokoro_zm_010' if '男声' in message else 'kokoro_zf_001'
