"""One utterance for a whole film. Visual edits do not restart the speaker."""
import hashlib,json,re
from app.speech import SpeechProvider
from app import store

def subtitle_cues(script,duration,start=.12):
 pieces=[]
 for phrase in re.findall(r'[^，。！？；,.!?;]+[，。！？；,.!?;]?',script):
  phrase=phrase.strip()
  if not phrase:continue
  # Keep English words intact and split CJK only when a subtitle is too long.
  if re.search(r'[\u4e00-\u9fff]',phrase):pieces.extend(phrase[i:i+16] for i in range(0,len(phrase),16))
  else:
   words=phrase.split();pieces.extend(' '.join(words[i:i+7]) for i in range(0,len(words),7))
 weights=[max(1,len(re.sub(r'\s','',p))) for p in pieces];total=sum(weights) or 1;cursor=start;cues=[]
 for text,weight in zip(pieces,weights):
  end=cursor+duration*weight/total;cues.append({'text':text,'start':round(cursor,4),'end':round(end,4)});cursor=end
 return cues

async def prepare_continuous(p,folder,voice_id):
 script=(p['plan'].get('voiceover_script') or '').strip()
 if not script or not p.get('narration_enabled',True):p.pop('narration_track',None);return False
 seconds=sum(s['duration'] for s in p['plan']['shots']);signature=hashlib.sha256(json.dumps(['continuous-v2-breathing',script,voice_id,seconds],ensure_ascii=False).encode()).hexdigest();path=folder/'narration.wav';track=p.get('narration_track') or {}
 if track.get('signature')!=signature or not path.exists():
  duration=await SpeechProvider(strict_voice=True).generate(script,path,seconds-.35,voice_id)
  from app.narration_pacing import add_breathing_room
  pauses=add_breathing_room(path,seconds-.35)
  duration+=sum(item['seconds'] for item in pauses)
  track={'breathing_pauses':pauses,'file':'narration.wav','duration':duration,'start':.12,'signature':signature,'voice_id':voice_id,'mode':'continuous','subtitle_timing':'estimated_by_phrase_weight','cues':subtitle_cues(script,duration)}
  p['narration_track']=track
 for i,shot in enumerate(p['plan']['shots']):
  p['assets'].setdefault(str(i),{}).update(voice_id=voice_id,voice_provider='continuous',voice_duration=0)
 p.setdefault('events',[]).append('已生成整片连贯旁白；画面快剪时声音连续，不逐镜头重启。');store.save(p)
 return True
