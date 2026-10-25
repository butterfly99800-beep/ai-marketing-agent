"""Sentence-level measured narration, with visual edits derived from real WAV samples."""
import asyncio,hashlib,json,math,wave
from app.speech import SpeechProvider
from app import store
FPS=30

async def prepare_measured(p,folder,voice_id):
 beats=p['plan'].get('narration_beats') or []
 if not beats or not p.get('narration_enabled',True):return False
 shots=p['plan']['shots'];order=[i for b in beats for i in b['shot_indices']]
 if order!=list(range(len(shots))):raise ValueError('每个镜头必须按顺序绑定到一句旁白，不能遗漏或重复')
 signature=hashlib.sha256(json.dumps(['measured-v2-minimum-shots',beats,voice_id,[(s.get('duration'),s.get('video'),s.get('motion')) for s in shots]],ensure_ascii=False,sort_keys=True).encode()).hexdigest();track=p.get('narration_track') or {};path=folder/'narration.wav'
 if track.get('signature')==signature and path.exists() and p.get('render_timeline'):return True
 chunks=[];cues=[];timeline=[];segments=[];sample_rate=24000;cursor=0
 # Every sentence uses the same voice. A sentence is never clipped to a shot.
 for n,beat in enumerate(beats):
  source=folder/f'narration-sentence-{n}.wav';await SpeechProvider(strict_voice=True).generate(beat['text'],source,25,voice_id)
  with wave.open(str(source),'rb') as w:
   if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getframerate()!=sample_rate:raise ValueError('旁白采样格式必须为24kHz单声道PCM')
   samples=w.readframes(w.getnframes());frames=w.getnframes()
  pre=round((.18 if n==0 else .08)*sample_rate);pause=round(float(beat.get('pause_after',.4))*sample_rate)
  tail=1.2 if n==len(beats)-1 else 0
  indices=beat['shot_indices']
  minimums=[round((5 if shots[i].get('video') else 3 if i==0 else 1 if shots[i].get('motion')=='brand' else 2)*FPS) for i in indices]
  block=max(pre+frames+pause+round(tail*sample_rate),round(sum(minimums)/FPS*sample_rate));end=math.ceil((cursor+block)/sample_rate*FPS)/FPS;block=round(end*sample_rate)-cursor
  chunks.append(bytes(pre*2)+samples+bytes((block-pre-frames)*2))
  start=(cursor+pre)/sample_rate;stop=start+frames/sample_rate
  cues.append({'text':beat['text'],'start':start,'end':stop,'shot_indices':beat['shot_indices']})
  start_frame=round(cursor/sample_rate*FPS);total_frames=round(block/sample_rate*FPS);indices=beat['shot_indices'];weights=[shots[i]['duration'] for i in indices];used=0
  extra=max(0,total_frames-sum(minimums))
  for k,i in enumerate(indices):
   next_used=total_frames if k==len(indices)-1 else sum(minimums[:k+1])+round(extra*sum(weights[:k+1])/sum(weights))
   timeline.append({'index':i,'from':start_frame+used,'duration_frames':next_used-used,'beat_index':n});used=next_used
  segments.append({'sentence':n,'text':beat['text'],'start_sample':cursor+pre,'sample_count':frames,'start_frame':start_frame,'duration_frames':total_frames,'shot_indices':indices});cursor+=block
 if cursor/sample_rate>60:raise ValueError('自然语速旁白超过60秒，请精简整句；不会裁断或强行加速')
 with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sample_rate);w.writeframes(b''.join(chunks))
 p['render_timeline']=timeline;p['render_duration']=cursor/sample_rate
 p['narration_track']={'file':'narration.wav','duration':cursor/sample_rate,'start':0,'mode':'measured_sentences','voice_id':voice_id,'signature':signature,'subtitle_timing':'measured_sentence_audio','cues':cues,'segments':segments}
 for i in range(len(shots)):p['assets'].setdefault(str(i),{}).update(voice_duration=0,voice_id=voice_id,voice_provider='measured_sentences')
 (folder/'narration-timeline.json').write_text(json.dumps({'fps':FPS,'duration':p['render_duration'],'shots':timeline,'sentences':segments},ensure_ascii=False,indent=2),encoding='utf8')
 p.setdefault('events',[]).append('按真实句子音频采样建立镜头与字幕时间轴；保留完整句子和换气停顿。');store.save(p);return True
