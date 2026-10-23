import asyncio,json,hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from uuid import UUID
from typing import Literal
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import FileResponse,JSONResponse,PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from app import store
from app.config import ROOT,DATA,CONFIG,MODEL,IMAGE_MODEL,VIDEO_MODEL,PUBLIC_ORIGIN,ALLOWED_HOSTS,ALLOWED_ORIGINS
from app.deepseek import DeepSeekProvider,ProviderError
from app.director import DirectorAgent
from app.schemas import Plan,VoiceId,MusicId,PlatformId
from app.media import capture
from app.producer import produce,ACTIVE
from app.progress import update,snapshot,estimate
from app import ops_auth
from app.operations_routes import router as operations_router
from app import youtube_service
LOCKS={}
TASKS=set()
def lock(pid):return LOCKS.setdefault(pid,asyncio.Lock())
def project(pid):
 try:
  UUID(pid);p=store.get(pid)
  if p.get('deleted_at'):raise HTTPException(404,'项目不存在')
  if p.get('owner_id') and p['owner_id']!=ops_auth.CURRENT_USER.get():raise HTTPException(404,'项目不存在')
  return p
 except (KeyError,ValueError):raise HTTPException(404,'项目不存在')
@asynccontextmanager
async def lifespan(app):
 ops_auth.initialize()
 with ops_auth.db() as c:
  rows=c.execute('SELECT payload FROM ops_jobs').fetchall()
 for raw, in rows:
  job=json.loads(raw)
  if job['status'] in ('queued','starting','uploading'):
   job.update(status='uncertain' if job['status']=='starting' else 'interrupted',error='服务重启，上传会话已保留，请在工作台恢复任务。');youtube_service.save_job(job)
 for p in store.listing():
  if p['status'] in ('producing','planning','capturing'):p['status']='interrupted';p['error']='服务已重启，确认重试会复用已提交任务和素材。';store.save(p)
 try:yield
 finally:
  await youtube_service.shutdown()
  for task in list(TASKS):task.cancel()
  if TASKS:await asyncio.gather(*list(TASKS),return_exceptions=True)
app=FastAPI(title='对话式宣传片Agent',lifespan=lifespan)
app.include_router(operations_router)
from app.chat_workspace import router as workspace_router
app.include_router(workspace_router)
@app.middleware('http')
async def guard(request,call_next):
 if request.headers.get('host','').split(':')[0] not in ALLOWED_HOSTS:return JSONResponse({'error':'仅允许本机访问'},403)
 if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin') not in ALLOWED_ORIGINS:return JSONResponse({'error':'请求来源无效'},403)
 user=ops_auth.current(request)
 if user is None and (request.url.path.startswith('/api/projects') or request.url.path=='/api/uploads'):
  with ops_auth.db() as c:has_users=c.execute('SELECT COUNT(*) FROM ops_users').fetchone()[0]>0
  if has_users or PUBLIC_ORIGIN:return JSONResponse({'error':'请先在发布与运营工作台登录，再访问你的作品。'},401)
 context=ops_auth.CURRENT_USER.set(user['id'] if user else None)
 try:response=await call_next(request)
 finally:ops_auth.CURRENT_USER.reset(context)
 response.headers['X-Frame-Options']='DENY';response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='no-referrer'
 response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'"
 if request.url.path.startswith('/api'):response.headers['Cache-Control']='no-store'
 return response
@app.exception_handler(ProviderError)
async def provider_error(request,exc):return JSONResponse({'error':str(exc)},502)
@app.get('/api/config')
def config():return {'deepseek_ready':bool(CONFIG.get('DEEPSEEK_API_KEY')),'wan_ready':bool(CONFIG.get('DASHSCOPE_API_KEY')),'models':{'director':MODEL,'image':IMAGE_MODEL,'video':VIDEO_MODEL},'max_images':6,'max_video_clips':2,'video_clip_seconds':5,'network_tools':['web_search','browser_open','browser_read'],'browser_mode':'独立公开网页浏览器','trend_mode':'可搜索公开趋势资料；不保证可访问平台实时热门榜'}
@app.get('/api/projects')
def projects():
 owners={p['id']:p.get('owner_id') for p in store.listing()}
 return [dict(p,progress=snapshot(p)) for p in store.summaries() if owners.get(p['id'])==ops_auth.CURRENT_USER.get() and not p.get('deleted_at')]
class New(BaseModel):
 platforms:list[PlatformId]=Field(default_factory=list,max_length=6)
 aspect_ratio:Literal['16:9','9:16','1:1']='16:9'
 narration_enabled:bool=True
 pace:Literal['fast','balanced']='fast'
 mode:Literal['text','website']
 source:str=Field(min_length=1,max_length=20000)
 platform:Literal['douyin','youtube','shorts']='douyin'
 target_duration:int=Field(default=30,ge=15,le=60)
 network_enabled:bool=True
 video_budget:bool=False
 voice:VoiceId|None=None
 music:MusicId|None=None
 bgm:bool=True
 attachment_ids:list[str]=Field(default_factory=list,max_length=5)
 background:bool=False
@app.post('/api/projects')
async def create(req:New):
 p=store.create(req.mode,req.source,req.platform,req.target_duration)
 if ops_auth.CURRENT_USER.get():p['owner_id']=ops_auth.CURRENT_USER.get();store.save(p)
 from app.uploads import attach
 try:attach(p,req.attachment_ids)
 except ValueError as exc:raise HTTPException(400,str(exc))
 p['network_enabled']=req.network_enabled
 p['video_budget']=req.video_budget;p['bgm']=req.bgm;p['sound_preferences']={'voice':req.voice,'music':req.music}
 from app.preferences import apply_preferences
 apply_preferences(p,req)
 p['messages']=[{'role':'user','content':req.source}];p['pending_user_recorded']=True;store.save(p)
 if req.background:
  capture_site=req.mode=='website' and req.network_enabled
  p['status']='capturing' if capture_site else 'planning';p['pending_message']=req.source;update(p,'读取网站' if capture_site else '分析资料',0,120 if capture_site else 60);schedule(conversation(p['id'],capture_site=capture_site));return public_project(p)
 if req.mode=='website' and req.network_enabled:
  try:p['site']=await capture(p);store.save(p)
  except ProviderError:p['status']='capture_failed';store.save(p);raise
 return p
def public_project(p):return dict(p,progress=snapshot(p))

@app.get('/api/projects/{pid}')
def detail(pid:str):return public_project(project(pid))
class Message(BaseModel):
 platforms:list[PlatformId]|None=Field(default=None,max_length=6)
 aspect_ratio:Literal['16:9','9:16','1:1']|None=None
 narration_enabled:bool|None=None
 pace:Literal['fast','balanced']|None=None
 attachment_ids:list[str]=Field(default_factory=list,max_length=5)
 clarification_answers:dict[str,str]|None=None
 text:str=Field(min_length=1,max_length=20000);platform:Literal['douyin','youtube','shorts']|None=None;video_budget:bool=False;network_enabled:bool=True;voice:VoiceId|None=None;music:MusicId|None=None;target_duration:int|None=Field(default=None,ge=15,le=60)
@app.post('/api/projects/{pid}/messages')
async def chat(pid:str,req:Message):
 if project(pid)['status'] in ('producing','planning','capturing'):raise HTTPException(409,'当前项目正在处理，请稍候')
 async with lock(pid):
  p=project(pid)
  if p['status'] in ('producing','planning','capturing'):raise HTTPException(409,'当前项目正在处理，请稍候')
  from app.uploads import attach
  try:attach(p,req.attachment_ids)
  except ValueError as exc:raise HTTPException(400,str(exc))
  if p.get('questions') or p.get('plan') or req.clarification_answers is not None:
   p['clarification_done']=True;p['clarification_answers']=req.clarification_answers or {};p['questions']=[]
  from app.preferences import apply_preferences
  apply_preferences(p,req)
  if req.target_duration is not None:p['target_duration']=req.target_duration
  p['network_enabled']=req.network_enabled
  if req.platform is not None:p['platform']=req.platform
  try:return await DirectorAgent().talk(p,req.text,req.video_budget,{'voice':req.voice,'music':req.music})
  except ProviderError:
   p['status']='draft';store.save(p);raise

def schedule(coro):
 task=asyncio.create_task(coro);TASKS.add(task);task.add_done_callback(TASKS.discard)

async def conversation(pid,capture_site=False):
 async with lock(pid):
  p=project(pid)
  try:
   if capture_site:
    update(p,'读取网站',0,120);p['site']=await capture(p);store.save(p)
   update(p,'整理方案',0,90 if capture_site else 60)
   await DirectorAgent().talk(p,p['pending_message'],p.get('video_budget',False),p.get('sound_preferences'))
   message=p.get('pending_message','')
   p.pop('pending_message',None);p.pop('error',None);store.save(p)
  except asyncio.CancelledError:
   p['status']='interrupted';p['error']='服务停止，项目已保存。';store.save(p);raise
  except Exception as exc:
   if not isinstance(exc,ProviderError):
    import logging,traceback,secrets
    reference=secrets.token_hex(4)
    frames=' > '.join(f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}' for frame in traceback.extract_tb(exc.__traceback__))
    logging.getLogger(__name__).error('Planning failure ref=%s type=%s frames=%s',reference,type(exc).__name__,frames)
    p['error_reference']=reference
   p['status']='draft';p['error']=str(exc) if isinstance(exc,ProviderError) else f'方案处理失败，请重试。诊断编号：{reference}';p.pop('pending_message',None);store.save(p)

@app.post('/api/projects/{pid}/conversations',status_code=202)
async def queue_chat(pid:str,req:Message):
 if project(pid)['status'] in ('producing','planning','capturing'):raise HTTPException(409,'当前项目正在处理，请稍候')
 async with lock(pid):
  p=project(pid)
  if p['status'] in ('producing','planning','capturing'):raise HTTPException(409,'当前项目正在处理，请稍候')
  from app.uploads import attach
  try:attach(p,req.attachment_ids)
  except ValueError as exc:raise HTTPException(400,str(exc))
  if p.get('questions') or p.get('plan') or req.clarification_answers is not None:
   p['clarification_done']=True;p['clarification_answers']=req.clarification_answers or {};p['questions']=[]
  from app.preferences import apply_preferences
  apply_preferences(p,req)
  if req.target_duration is not None:p['target_duration']=req.target_duration
  p['network_enabled']=req.network_enabled
  if req.platform is not None:p['platform']=req.platform
  p['messages'].append({'role':'user','content':req.text});p['pending_user_recorded']=True
  p['pending_message']=req.text;p['video_budget']=req.video_budget;p['sound_preferences']={'voice':req.voice,'music':req.music};apply_preferences(p,req);p['status']='planning';p.pop('error',None);p.pop('work',None);update(p,'整理方案',0,60);schedule(conversation(pid,capture_site=p['mode']=='website' and not p.get('site') and req.network_enabled));return public_project(p)

def render_options(p,req=None):
 def value(key,default):
  incoming=getattr(req,key,None) if req is not None else None
  return incoming if incoming is not None else p.get(key,default)
 return {'aspect_ratio':value('aspect_ratio','16:9' if p.get('platform')=='youtube' else '9:16'),'narration_enabled':value('narration_enabled',True),'platforms':value('platforms',[]),'voice':value('voice',(p.get('plan') or {}).get('voice','kokoro_zf_001')),'music':value('music',(p.get('plan') or {}).get('music','ambient')),'bgm':value('bgm',True)}

def copy_render_assets(source,target):
 import shutil
 target.mkdir(parents=True,exist_ok=True)
 if source.exists():
  for file in source.iterdir():
   if file.is_file() and file.name.startswith(('image','voice','video')) and file.suffix in ('.png','.wav','.mp4'):shutil.copy2(file,target/file.name)

class Confirm(BaseModel):
 aspect_ratio:Literal['16:9','9:16','1:1']|None=None
 narration_enabled:bool|None=None
 platforms:list[PlatformId]|None=Field(default=None,max_length=6)
 revision:int;allow_video:bool=False;bgm:bool=True;voice:VoiceId|None=None;music:MusicId|None=None
@app.post('/api/projects/{pid}/render')
async def render(pid:str,req:Confirm):
 if project(pid)['status'] in ('planning','capturing'):raise HTTPException(409,'当前项目正在分析，请稍候')
 async with lock(pid):
  p=project(pid)
  unchanged=render_options(p)==render_options(p,req)
  if p['status']=='completed' and req.revision==p['revision'] and unchanged:return p
  if not p['plan'] or req.revision!=p['revision']:raise HTTPException(409,'方案已变更，请确认当前方案')
  try:Plan.model_validate(p['plan'])
  except ValueError:raise HTTPException(409,'方案文字或视频预算不符合限制，请让导演精简后重新确认。')
  if pid in ACTIVE or p['status']=='producing':return p
  if sum(s['video'] for s in p['plan']['shots']) and not req.allow_video:raise HTTPException(409,'该方案包含付费短视频，请明确开启预算')
  if p['status']=='completed':
   previous=DATA/pid/f'rev{p["revision"]}';p['revision']+=1
   await asyncio.to_thread(copy_render_assets,previous,DATA/pid/f'rev{p["revision"]}')
   p.pop('video_url',None);p.pop('no_bgm_url',None)
  from app.preferences import apply_preferences
  apply_preferences(p,req)
  p['voice']=req.voice or p.get('voice') or p['plan'].get('voice','Ethan');p['music']=req.music or p.get('music') or p['plan'].get('music','ambient');p['plan']['music']=p['music'];p['plan']['voice']=p['voice'];p['bgm']=req.bgm;p['video_budget']=req.allow_video;p['status']='producing';p.pop('error',None);p.pop('work',None);update(p,'准备素材',0,estimate(p));schedule(produce(pid));return public_project(p)
@app.get('/api/projects/{pid}/video')
def video(pid:str,bgm:bool=True):
 p=project(pid);file=DATA/pid/f'rev{p["revision"]}'/('final.mp4' if bgm else 'final_no_bgm.mp4') 
 if p['status']!='completed' or not file.exists():raise HTTPException(404,'成片尚未完成')
 return FileResponse(file,media_type='video/mp4',filename='advertisement.mp4')
@app.get('/api/projects/{pid}/music-credit')
def music_credit(pid:str):
 p=project(pid)
 from app.creative import MUSIC
 return PlainTextResponse(MUSIC.get(p.get('music','ambient'),MUSIC['ambient'])['credit'],headers={'Content-Disposition':'attachment; filename="music-credit.txt"'})

@app.get('/api/creative-catalog')
def creative_catalog():
 from app.creative import MUSIC,PLATFORMS,RECIPES
 return {'music':MUSIC,'platforms':PLATFORMS,'recipes':RECIPES}

@app.get('/api/projects/{pid}/production-report')
def production_report(pid:str):
 p=project(pid)
 return {'creative_audit':p.get('creative_audit'),'quality_report':p.get('quality_report'),'plan':p.get('plan')}

@app.get('/api/projects/{pid}/review-frame/{index}')
def review_frame(pid:str,index:int):
 p=project(pid)
 if p['status']!='completed' or not 1<=index<=12:raise HTTPException(404)
 file=DATA/pid/f'rev{p["revision"]}'/'qa'/f'shot-{index}.jpg'
 if not file.exists():raise HTTPException(404)
 return FileResponse(file,media_type='image/jpeg')

class BrowseRequest(BaseModel):
 url:str=Field(min_length=8,max_length=2048)
 scroll_y:int=Field(default=0,ge=0,le=60000)

@app.post('/api/projects/{pid}/browse')
async def browse(pid:str,req:BrowseRequest):
 async with lock(pid):
  p=project(pid)
  if p['status'] in ('planning','capturing','producing'):raise HTTPException(409,'当前项目正在处理，请稍候')
  from app.research import execute_tool
  result=await execute_tool('browser_open',{'url':req.url,'scroll_y':req.scroll_y},p)
  if result.get('error'):raise ProviderError(result['error'])
  return public_project(p)

@app.get('/api/projects/{pid}/browser-image/{name}')
def browser_image(pid:str,name:str):
 import re
 p=project(pid)
 if not re.fullmatch(r'browser-[a-f0-9]{32}\.png',name):raise HTTPException(404)
 file=DATA/pid/name
 if not file.exists():raise HTTPException(404)
 return FileResponse(file,media_type='image/png')

@app.get('/api/projects/{pid}/assets/{name}')
def asset(pid:str,name:str):
 p=project(pid)
 if not __import__('re').fullmatch(r'browser-[a-f0-9]{32}\.png',name) and name not in tuple(f'site{i}.png' for i in range(12)) and not (name.startswith('image') and name[5:-4].isdigit() and name.endswith('.png')):raise HTTPException(404)
 file=DATA/pid/name if name.startswith(('site','browser-')) else DATA/pid/f'rev{p["revision"]}'/name
 if not file.exists():raise HTTPException(404)
 return FileResponse(file)
@app.post('/api/uploads')
async def upload(request:Request,name:str):
 from app.uploads import save_upload,MAX_BYTES
 data=bytearray()
 async for chunk in request.stream():
  data.extend(chunk)
  if len(data)>MAX_BYTES:raise HTTPException(413,'单个文件不能超过10MB')
 try:return await asyncio.to_thread(save_upload,name,bytes(data))
 except ValueError as exc:raise HTTPException(400,str(exc))
 except Exception:raise HTTPException(400,'文件无法读取，请检查格式或是否加密')

@app.get('/api/media-catalog')
def media_catalog():
 from app.audio_catalog import voice_catalog
 from app.creative import licensed_music
 return {'voices':voice_catalog(),'music':{k:dict(v,preview_url='/api/music/'+k+'/preview') for k,v in licensed_music().items()},'music_sources':[{'name':'Incompetech','license':'逐曲CC BY，下载成片时附署名','url':'https://incompetech.com/music/royalty-free/'},{'name':'Pixabay','license':'需逐曲留存凭证；自动素材库须另行获得许可','url':'https://pixabay.com/service/terms/'},{'name':'Mixkit','license':'不得批量下载或转售素材库；SaaS需单独确认','url':'https://mixkit.co/terms/'}]}

@app.get('/api/voices/{voice}/preview')
async def voice_preview(voice:str):
 from app.audio_catalog import VOICE_PROFILES
 if voice not in VOICE_PROFILES or not voice.startswith('kokoro_'):raise HTTPException(404)
 folder=ROOT/'work/voice_previews';folder.mkdir(parents=True,exist_ok=True);path=folder/(voice+'.wav')
 if not path.exists():
  from app.kokoro_voice import generate
  text='让每一个好想法，被更多人看见。' if VOICE_PROFILES[voice]['language']=='zh' else 'Make every great idea stand out. Discover a better way to work.'
  await asyncio.to_thread(generate,text,path,15,voice)
 return FileResponse(path,media_type='audio/wav')

@app.get('/api/music/{track}/preview')
def music_preview(track:str):
 from app.creative import licensed_music
 music=licensed_music()
 if track not in music:raise HTTPException(404)
 return FileResponse(ROOT/'renderer/public/audio'/music[track]['file'])

@app.get('/api/media-license-guide')
def media_license_guide():
 return FileResponse(ROOT/'19_音色与配乐授权指南.txt',media_type='text/plain',filename='audio-license-guide.txt')

app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='web')


