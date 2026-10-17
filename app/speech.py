import asyncio,hashlib,json,wave,subprocess,shutil
from pathlib import Path
import httpx,imageio_ffmpeg
from app.config import CONFIG,WAN_BASE,ROOT
from app.media import download,speak
from app.deepseek import ProviderError
from app.audio_catalog import VOICE_PROFILES
VOICES=set(VOICE_PROFILES)
class SpeechProvider:
 def __init__(self,strict_voice=False):self.strict_voice=strict_voice;self.fallback_reason=None
 async def fallback(self,text,path,seconds,reason):
  if self.strict_voice:raise ProviderError('当前整片音色无法完成：'+reason+' 为保证一致性已停止，不会中途换音色。可在设置中更换整片音色后重试。')
  self.fallback_reason=reason
  return await asyncio.to_thread(speak,text,path,seconds)
 async def generate(self,text,path,seconds,voice='Ethan'):
  self.fallback_reason=None
  if voice not in VOICES:raise ProviderError('不支持的配音音色')
  if voice.startswith('kokoro_'):
   from app.kokoro_voice import generate
   return await asyncio.to_thread(generate,text,path,seconds,voice)
  if voice=='local':return await asyncio.to_thread(speak,text,path,seconds)
  model=CONFIG.get('QWEN_TTS_MODEL','qwen3-tts-flash');key=hashlib.sha256((model+voice+text).encode()).hexdigest();cache=ROOT/'work/voice_cache';cache.mkdir(exist_ok=True);saved=cache/(key+'.wav');meta=cache/(key+'.json')
  if not saved.exists():
   if meta.exists():record=json.loads(meta.read_text(encoding='utf-8'))
   else:record={}
   if not record.get('url'):
    if record.get('pending'):return await self.fallback(text,path,seconds,'上次云端配音响应不明，未重复扣费；本镜头改用本地配音。')
    meta.write_text(json.dumps({'pending':True}),encoding='utf-8')
    async with httpx.AsyncClient(timeout=180) as client:
     try:
      response=await client.post(WAN_BASE+'/api/v1/services/aigc/multimodal-generation/generation',headers={'Authorization':'Bearer '+CONFIG.get('DASHSCOPE_API_KEY','')},json={'model':model,'input':{'text':text,'voice':voice,'language_type':'Chinese' if any('\u4e00'<=c<='\u9fff' for c in text) else 'English'}})
      if response.status_code>=400:meta.unlink(missing_ok=True);raise ProviderError('云端配音调用失败，请检查千问TTS权限和余额。')
      record={'url':response.json()['output']['audio']['url'],'voice':voice,'model':model};meta.write_text(json.dumps(record),encoding='utf-8')
     except httpx.HTTPError:
      return await self.fallback(text,path,seconds,'云端配音连接或响应异常，未重复提交；本镜头改用本地配音。')
     except (KeyError,ValueError,TypeError):
      return await self.fallback(text,path,seconds,'云端配音响应缺少有效音频地址；本镜头改用本地配音。')
   raw=cache/(key+'.raw.wav');await download(record['url'],raw,15*1024*1024)
   result=await asyncio.to_thread(subprocess.run,[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(raw),'-af','loudnorm=I=-18:TP=-2:LRA=7','-ar','24000','-ac','1','-c:a','pcm_s16le',str(saved)],capture_output=True,timeout=45)
   if result.returncode:raise ProviderError('云端配音格式处理失败')
  with wave.open(str(saved)) as w:duration=w.getnframes()/w.getframerate()
  if duration>seconds-.25:
   ratio=duration/max(.5,seconds-.3)
   if ratio>1.25:return await self.fallback(text,path,seconds,'云端旁白超出镜头可用时长，改用按镜头适配的本地配音。')
   fitted=await asyncio.to_thread(subprocess.run,[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(saved),'-af',f'atempo={ratio:.6f}','-c:a','pcm_s16le',str(path)],capture_output=True,timeout=45)
   if fitted.returncode:raise ProviderError('旁白时长适配失败，原音频已保留。')
   with wave.open(str(path)) as w:return w.getnframes()/w.getframerate()
  shutil.copyfile(saved,path);return duration
