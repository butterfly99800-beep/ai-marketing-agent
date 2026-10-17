"""Local ONNX voice inference. No voice cloning, no remote requests at render time."""
import sys,threading,hashlib,wave,subprocess,shutil
from app.config import ROOT
from app.deepseek import ProviderError
ENGINE=None;G2P=None;LOCK=threading.Lock()
def generate(text,path,seconds,voice):
 global ENGINE,G2P
 deps=str(ROOT/'.runtime/voice_deps')
 if deps not in sys.path:sys.path.insert(0,deps)
 from app.audio_catalog import VOICE_PROFILES,kokoro_ready
 if not kokoro_ready():raise ProviderError('Kokoro模型尚未就绪，请先完成模型安装或选择云端音色')
 profile=VOICE_PROFILES[voice];speaker=profile['speaker']
 cache=ROOT/'work/kokoro_cache';cache.mkdir(parents=True,exist_ok=True)
 key=hashlib.sha256(('kokoro-v1.1-zh|'+speaker+'|'+text).encode()).hexdigest();raw=cache/(key+'.wav')
 with LOCK:
  if not raw.exists():
   from kokoro_onnx import Kokoro
   import soundfile as sf
   folder=ROOT/'models/kokoro'
   if ENGINE is None:ENGINE=Kokoro(str(folder/'kokoro-v1.1-zh.onnx'),str(folder/'voices-v1.1-zh.bin'),vocab_config=str(folder/'config.json'))
   if profile['language']=='zh':
    if G2P is None:
     from misaki import zh
     G2P=zh.ZHG2P(version='1.1',en_callable=lambda value:ENGINE.tokenizer.phonemize(value,lang='en-us'))
    phonemes,_=G2P(text);samples,rate=ENGINE.create(phonemes,voice=speaker,speed=1.05,is_phonemes=True)
   else:samples,rate=ENGINE.create(text,voice=speaker,speed=1.05,lang='en-gb' if speaker.startswith('bf_') else 'en-us')
   pending=raw.with_suffix('.pending.wav');sf.write(str(pending),samples,rate,subtype='PCM_16');pending.replace(raw)
 with wave.open(str(raw)) as wav:duration=wav.getnframes()/wav.getframerate()
 available=max(.4,seconds-.12);ratio=max(1,duration/available)
 if ratio>1.35:raise ProviderError(f'旁白需要{duration:.1f}秒，镜头可用{available:.1f}秒。请缩短该句；不会换音色或裁断旁白。')
 if ratio>1:
  import imageio_ffmpeg
  result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(raw),'-af',f'atempo={ratio:.6f}','-ar','24000','-ac','1',str(path)],capture_output=True,timeout=45)
  if result.returncode:raise ProviderError('配音时长适配失败，原始音频已保留')
 else:shutil.copyfile(raw,path)
 with wave.open(str(path)) as wav:return wav.getnframes()/wav.getframerate()
