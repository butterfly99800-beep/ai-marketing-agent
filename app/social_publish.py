"""Uploaded works, platform-specific drafts and a durable, single-worker queue.

Only YouTube has a live adapter. Other targets remain reviewable/exportable drafts.
No blind retries across an uncertain remote publishing boundary.
"""
import asyncio, hashlib, json, logging, os, re, secrets, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
import httpx, imageio_ffmpeg
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from app import store, ops_auth as auth, youtube_service as yt
from app.config import ROOT, DATA, CONFIG, MODEL
from app.deepseek_transport import completion_json

router = APIRouter(prefix='/api/ops/social')
log = logging.getLogger(__name__)
PROFILES = {
 'youtube': ('YouTube / Shorts',100,4500,8,'已接入 YouTube 授权；Shorts 由平台判定'),
 'tiktok': ('TikTok',100,1800,5,'待 Content Posting API 审核及用户授权'),
 'instagram': ('Instagram Reels',100,2000,5,'待专业账号、应用权限及用户授权'),
 'facebook': ('Facebook Reels',100,3000,5,'待 Facebook Page 发布权限及用户授权'),
 'x': ('X / Twitter',80,240,2,'待 X API 发布及媒体上传权限'),
 'linkedin': ('LinkedIn',100,2500,4,'待成员/组织发布权限及用户授权'),
 'pinterest': ('Pinterest',100,450,5,'待 Pins API 授权及视频封面支持'),
 'threads': ('Threads',100,450,1,'待 Threads 发布权限及用户授权'),
 'snapchat': ('Snapchat Spotlight',80,140,3,'待 Public Profile API 接入资格及用户授权'),
}

def initialize():
 with store.connection() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS social_drafts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,payload TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS social_queue(id TEXT PRIMARY KEY,owner TEXT NOT NULL,project TEXT NOT NULL,platform TEXT NOT NULL,account TEXT NOT NULL,due REAL NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL, UNIQUE(owner,project,platform,account));''')

def owned(uid, pid):
 try: p=store.get(pid)
 except KeyError: raise HTTPException(404,'作品不存在')
 if p.get('owner_id')!=uid or p.get('deleted_at') or p.get('status')!='completed':raise HTTPException(404,'作品不存在或尚未完成')
 return p

def probe(path):
 # Decode a frame rather than trusting extension/MIME. No transcoding on 2GB hosts.
 r=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(path),'-map','0:v:0','-frames:v','1','-f','null','-'],capture_output=True,timeout=40)
 text=r.stderr.decode(errors='replace')
 if r.returncode:raise ValueError('无法读取视频，请上传有效 MP4 视频')
 m=re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)',text)
 if not m:raise ValueError('视频时长无法识别')
 seconds=int(m[1])*3600+int(m[2])*60+float(m[3])
 if not 0<seconds<=3600:raise ValueError('视频须在 1 小时以内')
 return seconds

@router.get('/platforms')
async def platforms(request:Request):
 auth.require(request)
 return [dict(id=k,name=v[0],title_limit=v[1],caption_limit=v[2],hashtags_limit=v[3],status=v[4],adapter_ready=k=='youtube') for k,v in PROFILES.items()]

@router.post('/upload')
async def upload(request:Request,filename:str='video.mp4'):
 uid=auth.require(request)['id'];limit=int(os.getenv('SOCIAL_UPLOAD_MAX_MB','150'))*1024*1024
 if len(filename)>255 or Path(filename).suffix.lower()!='.mp4':raise HTTPException(400,'目前支持 MP4 成品；请先导出为 MP4')
 pid=__import__('uuid').uuid4().__str__();folder=DATA/pid/'rev1';folder.mkdir(parents=True,exist_ok=False);path=folder/'final.mp4';size=0;sha=hashlib.sha256()
 try:
  with path.open('wb') as out:
   async for chunk in request.stream():
    size+=len(chunk)
    if size>limit:raise HTTPException(413,f'文件超过 {limit//1024//1024} MB')
    if __import__('shutil').disk_usage(folder).free<300*1024*1024:raise HTTPException(507,'磁盘空间不足，请先扩容或清理')
    sha.update(chunk);out.write(chunk)
  seconds=await asyncio.to_thread(probe,path)
  p={'id':pid,'owner_id':uid,'mode':'upload','source':'用户上传成品','title':Path(filename).stem[:100],'status':'completed','revision':1,'created_at':store.now(),'bgm':False,'messages':[],'assets':{},'content_sha256':sha.hexdigest(),'plan':{'shots':[{'duration':seconds}]},'video_url':f'/api/projects/{pid}/video','imported':True}
  store.save(p);return {'id':pid,'title':p['title'],'duration':seconds,'revision':1}
 except HTTPException: path.unlink(missing_ok=True);raise
 except (ValueError,subprocess.TimeoutExpired) as e:path.unlink(missing_ok=True);raise HTTPException(400,str(e) if isinstance(e,ValueError) else '读取视频超时')
 except BaseException:path.unlink(missing_ok=True);raise

@router.get('/drafts')
async def list_drafts(request:Request):
 uid=auth.require(request)['id'];initialize()
 with store.connection() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM social_drafts WHERE owner=? ORDER BY rowid DESC LIMIT 100',(uid,))]

class DraftEdit(BaseModel):
 posts:list[dict]=Field(min_length=1,max_length=9)

@router.put('/drafts/{did}')
async def edit_draft(did:str,req:DraftEdit,request:Request):
 uid=auth.require(request)['id'];initialize()
 with store.connection() as c:
  row=c.execute('SELECT payload FROM social_drafts WHERE id=? AND owner=?',(did,uid)).fetchone()
  if not row:raise HTTPException(404,'文案不存在')
  draft=json.loads(row[0])
  try:draft['posts']=validate_posts({'posts':req.posts},[p['platform'] for p in draft['posts']])
  except (ValueError,KeyError,TypeError):raise HTTPException(400,'文案格式或长度不正确')
  c.execute('UPDATE social_drafts SET payload=? WHERE id=? AND owner=?',(json.dumps(draft,ensure_ascii=False),did,uid))
 return draft

class DraftRequest(BaseModel):
 project_id:str=Field(max_length=40)
 brief:str=Field(default='',max_length=12000)
 language:str=Field(default='English',max_length=60)
 platforms:list[str]=Field(min_length=1,max_length=9)

class Post(BaseModel):
 platform:str
 title:str=Field(min_length=1,max_length=100)
 caption:str=Field(min_length=1,max_length=4500)
 keywords:list[str]=Field(max_length=12)
 hashtags:list[str]=Field(max_length=8)

def validate_posts(raw,selected):
 posts=[Post.model_validate(x).model_dump() for x in raw['posts']]
 if sorted(p['platform'] for p in posts)!=sorted(set(selected)):raise ValueError('平台文案不完整')
 for p in posts:
  _,title,caption,tags,_=PROFILES[p['platform']]
  if len(p['title'])>title or len(p['hashtags'])>tags:raise ValueError('平台标题或标签超限')
  if any(not re.fullmatch(r'#[\w]+',h) for h in p['hashtags']):raise ValueError('标签格式错误')
  if any(not k.strip() or len(k)>100 for k in p['keywords']) or sum(len(k)+1 for k in p['keywords'])>450:raise ValueError('关键词格式或总长度不正确')
  if len(p['caption']+'\n'+' '.join(p['hashtags']))>caption:raise ValueError('正文和标签超过平台编辑限制')
 return posts

@router.post('/drafts')
async def drafts(req:DraftRequest,request:Request):
 uid=auth.require(request)['id'];p=owned(uid,req.project_id)
 if any(k not in PROFILES for k in req.platforms):raise HTTPException(400,'不支持的平台')
 if not CONFIG.get('DEEPSEEK_API_KEY'):raise HTTPException(503,'文案服务未配置 DeepSeek 密钥')
 messages=[{'role':'system','content':(ROOT/'prompts/social-publish.txt').read_text(encoding='utf-8')},{'role':'user','content':json.dumps({'brief':req.brief,'filename':p['title'],'language':req.language,'profiles':{k:dict(title_limit=PROFILES[k][1],caption_limit=PROFILES[k][2],hashtag_limit=PROFILES[k][3]) for k in dict.fromkeys(req.platforms)}},ensure_ascii=False)}]
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(150,connect=20)) as c:
   for attempt in range(2):
    data=await completion_json(c,CONFIG['DEEPSEEK_API_KEY'],{'model':MODEL,'messages':messages,'response_format':{'type':'json_object'},'max_tokens':6500}, {})
    try: posts=validate_posts(json.loads(data['choices'][0]['message']['content']),req.platforms);break
    except (ValueError,KeyError,TypeError) as e:
     if attempt:raise
     messages.append({'role':'user','content':'上次输出未通过结构验证：'+str(e)[:160]+'。请重新返回完整 JSON，遵守各平台长度限制。'})
 except Exception as e:
  ref=secrets.token_hex(4);log.warning('Social copy failure ref=%s type=%s',ref,type(e).__name__);raise HTTPException(502,'文案生成失败，请重试。诊断编号：'+ref)
 initialize();draft=dict(id=secrets.token_hex(16),project_id=p['id'],revision=p['revision'],posts=posts,created_at=store.now())
 with store.connection() as c:c.execute('INSERT INTO social_drafts VALUES(?,?,?)',(draft['id'],uid,json.dumps(draft,ensure_ascii=False)))
 return draft

class Schedule(BaseModel):
 draft_id:str=Field(max_length=32)
 platforms:list[str]=Field(min_length=1,max_length=9)
 connection_id:str=Field(default='',max_length=32)
 start_at:datetime
 interval_hours:int=Field(default=6,ge=1,le=168)
 repeat_count:int=Field(default=1,ge=0,le=1000)
 privacy:str=Field(default='private',pattern='^(private|unlisted|public)$')
 made_for_kids:bool
 contains_synthetic_media:bool
 confirm:bool=False

@router.post('/schedule')
async def schedule(req:Schedule,request:Request):
 uid=auth.require(request)['id'];initialize()
 if not req.confirm:raise HTTPException(400,'请确认文案、账号、受众和发布时间')
 if not req.start_at.tzinfo or req.start_at.timestamp()<time.time()-60:raise HTTPException(400,'请选择未来时间（含时区）')
 with store.connection() as c:row=c.execute('SELECT payload FROM social_drafts WHERE id=? AND owner=?',(req.draft_id,uid)).fetchone()
 if not row:raise HTTPException(404,'文案不存在')
 draft=json.loads(row[0]);p=owned(uid,draft['project_id']);selected=set(req.platforms);posts=[x for x in draft['posts'] if x['platform'] in selected]
 if {x['platform'] for x in posts}!=selected:raise HTTPException(400,'所选平台缺少文案')
 if 'x' in selected and req.repeat_count!=1:raise HTTPException(400,'X 不支持相同内容自动循环发布，请选择仅发布一次或移除 X')
 if 'youtube' in selected and not any(x['id']==req.connection_id for x in yt.channels(uid)):raise HTTPException(400,'请先绑定并选择 YouTube 频道')
 if draft['revision']!=p['revision']:raise HTTPException(409,'作品已更新，请重新生成文案')
 rows=[]
 with store.LOCK,store.connection() as c:
  due=req.start_at.timestamp()
  for post in posts:
   account=req.connection_id if post['platform']=='youtube' else 'pending'
   # Block the same binary under another filename as well as repeat queue entries.
   if p.get('content_sha256'):
    for old, in c.execute('SELECT payload FROM social_queue WHERE owner=? AND platform=? AND account=? AND status!=?',(uid,post['platform'],account,'cancelled')):
     if json.loads(old).get('content_sha256')==p['content_sha256']:raise HTTPException(409,'此视频已有发布计划，请在原计划中查看或停止循环')
   status='scheduled' if post['platform']=='youtube' else 'awaiting_authorization'
   item=dict(id=secrets.token_hex(16),project_id=p['id'],platform=post['platform'],account=account,due=due,status=status,post=post,content_sha256=p.get('content_sha256'),revision=p['revision'],privacy=req.privacy,made_for_kids=req.made_for_kids,contains_synthetic_media=req.contains_synthetic_media,interval_hours=req.interval_hours,repeat_count=req.repeat_count,completed_count=0,history=[])
   try:c.execute('INSERT INTO social_queue VALUES(?,?,?,?,?,?,?,?)',(item['id'],uid,p['id'],post['platform'],account,item['due'],status,json.dumps(item,ensure_ascii=False)))
   except __import__('sqlite3').IntegrityError:raise HTTPException(409,'该作品已在此账号排队；请取消原任务或使用不同作品')
   rows.append(item)
 return rows

@router.get('/queue')
async def queue(request:Request):
 uid=auth.require(request)['id'];initialize()
 with store.connection() as c:items=[json.loads(r[0]) for r in c.execute('SELECT payload FROM social_queue WHERE owner=? ORDER BY due DESC',(uid,))]
 for item in items:
  if item.get('youtube_job_id'):
   try:item['upload']=yt.public_job(yt.job_get(uid,item['youtube_job_id']))
   except HTTPException:pass
 return items

@router.post('/queue/{qid}/cancel')
async def cancel(qid:str,request:Request):
 uid=auth.require(request)['id'];initialize()
 with store.LOCK,store.connection() as c:
  row=c.execute('SELECT payload,status FROM social_queue WHERE id=? AND owner=?',(qid,uid)).fetchone()
  if not row:raise HTTPException(404,'任务不存在')
  item=json.loads(row[0]);item['status']='stopped';item['stopped_at']=store.now()
  c.execute('UPDATE social_queue SET status=?,payload=? WHERE id=? AND owner=?',('stopped',json.dumps(item,ensure_ascii=False),qid,uid))
 return {'ok':True,'message':'已停止后续发布；已经提交的平台上传不会撤回'}

def update_item(item):
 with store.connection() as c:c.execute('UPDATE social_queue SET status=?,due=?,payload=? WHERE id=?',(item['status'],item['due'],json.dumps(item,ensure_ascii=False),item['id']))

def advance_completed():
 """Only a confirmed upload consumes an occurrence. Failed/uncertain jobs pause.

 Missed slots are skipped, never replayed in a burst after a long outage.
 """
 with store.connection() as c:rows=c.execute("SELECT owner,payload FROM social_queue WHERE status='submitted'").fetchall()
 for uid,raw in rows:
  item=json.loads(raw)
  if not item.get('youtube_job_id'):continue
  try:job=yt.job_get(uid,item['youtube_job_id'])
  except HTTPException:
   item.update(status='needs_review',error='未找到对应上传记录，请先核对平台');update_item(item);continue
  if job['status']!='uploaded':continue
  count=item.get('completed_count',0)+1
  item['completed_count']=count
  item['history']=(item.get('history',[])+[{'job_id':job['id'],'url':job.get('url'),'due':item['due'],'observed_uploaded_at':store.now()}])[-100:]
  total=item.get('repeat_count',1)
  if total and count>=total:item['status']='completed'
  else:
   interval=item.get('interval_hours',6)*3600
   due=item['due']+interval
   if due<=time.time():due+=(int((time.time()-due)//interval)+1)*interval
   item.update(status='scheduled',due=due)
   item.pop('youtube_job_id',None)
  update_item(item)

async def tick():
 initialize()
 advance_completed()
 with store.connection() as c:rows=c.execute("SELECT owner,payload FROM social_queue WHERE status='scheduled' AND due<=? ORDER BY due LIMIT 10",(time.time(),)).fetchall()
 for uid,raw in rows:
  item=json.loads(raw)
  with store.connection() as c:
   claimed=c.execute("UPDATE social_queue SET status='dispatching' WHERE id=? AND status='scheduled'",(item['id'],)).rowcount
  if not claimed:continue
  try:
   owned(uid,item['project_id']);post=item['post']
   form=dict(project_id=item['project_id'],revision=item['revision'],connection_id=item['account'],title=post['title'],description=post['caption']+'\n\n'+' '.join(post['hashtags']),tags=post['keywords'],privacy=item['privacy'],made_for_kids=item['made_for_kids'],contains_synthetic_media=item['contains_synthetic_media'],category_id='22',publish_at=None)
   # Stable per occurrence: retries reuse one upload, intentional repeats create a new one.
   if 'repeat_count' in item:form['social_occurrence_id']=item['id']+':'+str(item.get('completed_count',0)+1)
   job=yt.create_job(uid,form)
   item.update(status='submitted',youtube_job_id=job['id']);update_item(item)
   if job['status']=='queued':yt.launch(job)
  except Exception as e:
   item.update(status='failed',error=str(e.detail) if isinstance(e,HTTPException) else '任务提交失败，请检查服务日志');update_item(item);log.warning('Social dispatch failure type=%s',type(e).__name__)

async def worker():
 initialize()
 with store.connection() as c:
  rows=c.execute("SELECT payload FROM social_queue WHERE status='dispatching'").fetchall()
 for raw, in rows:
  item=json.loads(raw);item.update(status='needs_review',error='服务在提交时重启，请先核对发布记录，避免重复上传');update_item(item)
 while True:
  try:await tick()
  except asyncio.CancelledError:raise
  except Exception:log.exception('Social queue worker error')
  await asyncio.sleep(15)
