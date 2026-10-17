from app.deepseek import DeepSeekProvider
from app import store
class DirectorAgent:
 """Conversation → explicit reviewable plan, with an interchangeable LLM provider."""
 def __init__(self,provider=None):self.provider=provider or DeepSeekProvider()
 async def talk(self,p,message,allow_video=False,sound_preferences=None):
  if sound_preferences is not None:p["sound_preferences"]=sound_preferences
  p.pop('publish_draft',None);p.pop('publish_job_id',None)
  p['plan']=None;p['status']='planning';p.pop('video_url',None);p['video_budget']=allow_video
  recorded=p.pop('pending_user_recorded',False) and p.get('messages') and p['messages'][-1]=={'role':'user','content':message}
  if not recorded:p['messages'].append({'role':'user','content':message})
  # Keep the first request and a bounded recent conversation instead of losing the initial brief.
  if len(p['messages'])>40:p['messages']=p['messages'][:1]+p['messages'][-39:]
  store.save(p)
  from app.creative import director_context,audit_plan
  p['creative_context']=director_context(p)
  p['production_version']=3
  reply=await self.provider.converse(p)
  if reply['ready'] and reply['plan'] and p.get('target_duration'):
   from app.planning import fit_duration
   reply['plan']=fit_duration(reply['plan'],p['target_duration'])
  p['questions']=reply.get('questions',[])
  p['status']='awaiting_input' if p['questions'] else 'draft';p['messages'].append({'role':'assistant','content':reply['reply']})
  if reply['ready'] and reply['plan']:
   p['plan']=reply['plan'];p['revision']+=1;p['assets']={};p['status']='awaiting_confirmation'
   if not p.get('custom_title'):p['title']=reply['plan']['title']
   from app.audio_catalog import select_voice
   p['plan']['voice']=select_voice(p)
   from app.music_matching import select_music
   selected_music,music_reason=select_music(p)
   p['plan']['music']=selected_music
   if p['plan'].get('creative') is not None:p['plan']['creative']['music_reason']=music_reason
   for key,default in [('voice','kokoro_zf_001'),('music','pulse')]:
    p[key]=p.get('sound_preferences',{}).get(key) or reply['plan'].get(key,default);p['plan'][key]=p[key]
   if p['plan'].get('shots'):p['creative_audit']=audit_plan(p['plan'],p)
  store.save(p);return p
