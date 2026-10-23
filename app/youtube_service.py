import asyncio,json,time,secrets,hashlib,base64,os
from pathlib import Path
from datetime import date,timedelta,datetime,timezone
from urllib.parse import urlencode,urlsplit
import httpx
from fastapi import HTTPException
from app.google_transport import google_proxy
from app import store
from app.config import ROOT,DATA
from app.ops_auth import db,initialize,digest,encrypt,decrypt

SCOPES=['https://www.googleapis.com/auth/youtube.force-ssl','https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly','https://www.googleapis.com/auth/yt-analytics.readonly']
TASKS=set();LOCKS={}
def settings():
 folder=Path(os.getenv('YOUTUBE_CONFIG_DIR',str(ROOT.parent/'YouTube')));files=list(folder.glob('*.json'))
 if len(files)!=1:raise HTTPException(503,'未找到唯一的YouTube OAuth客户端JSON，请检查YouTube配置目录。')
 try:data=json.loads(files[0].read_text(encoding='utf-8-sig'))['web']
 except Exception:raise HTTPException(503,'YouTube配置需要Web应用类型的OAuth客户端。')
 redirect=os.getenv('YOUTUBE_REDIRECT_URI','http://localhost:8000/api/auth/youtube/callback')
 if redirect not in data.get('redirect_uris',[]):raise HTTPException(503,'Google配置中缺少精确回调地址：'+redirect)
 if not data.get('client_id') or not data.get('client_secret'):raise HTTPException(503,'OAuth客户端配置不完整。')
 return data,redirect

def authorization(request,user):
 data,redirect=settings();state=secrets.token_urlsafe(40);verifier=secrets.token_urlsafe(64)
 challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
 initialize()
 with db() as c:
  c.execute('DELETE FROM ops_states WHERE expires<?',(time.time(),))
  c.execute('INSERT INTO ops_states VALUES(?,?,?,?)',(digest(state),digest(request.cookies.get('ops_session','')),encrypt({'verifier':verifier,'owner':user['id']}),time.time()+600))
 return 'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':data['client_id'],'redirect_uri':redirect,'response_type':'code','scope':' '.join(SCOPES),'state':state,'access_type':'offline','prompt':'consent select_account','include_granted_scopes':'true','code_challenge':challenge,'code_challenge_method':'S256'})

def api_error(response):
 try:
  data=response.json();error=data.get('error',{});reason=(error.get('errors') or [{}])[0].get('reason','') if isinstance(error,dict) else error
 except Exception:reason='invalidResponse'
 reasons={'accessNotConfigured':'请在Google Cloud启用YouTube Data API v3与YouTube Analytics API。','youtubeSignupRequired':'该Google账号尚未创建YouTube频道。','insufficientPermissions':'授权范围不足，请重新绑定并授予所需权限。','quotaExceeded':'Google API今日配额已用完，请查看项目配额。','commentsDisabled':'该视频关闭了评论。','invalid_grant':'Google授权已失效，请重新绑定账号。','forbidden':'Google拒绝此操作，请检查频道权限、API启用和OAuth审核状态。'}
 return HTTPException(502,reasons.get(reason,f'YouTube接口返回HTTP {response.status_code}（{reason or "unknown"}），请稍后重试。'))

def pending_table():
 initialize()
 with db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS ops_oauth_pending(owner TEXT PRIMARY KEY, token TEXT NOT NULL, expires REAL NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS ops_oauth_events(id TEXT PRIMARY KEY, owner TEXT NOT NULL, phase TEXT, error_type TEXT, created REAL)')
  c.execute('DELETE FROM ops_oauth_pending WHERE expires<?',(time.time(),))

def pending_status(owner):
 pending_table()
 with db() as c:
  row=c.execute('SELECT expires FROM ops_oauth_pending WHERE owner=?',(owner,)).fetchone()
 return {'can_resume':bool(row),'expires_at':row[0] if row else None}

def note_failure(owner,phase,exc):
 pending_table();reference=secrets.token_hex(4)
 with db() as c:c.execute('INSERT INTO ops_oauth_events VALUES(?,?,?,?,?)',(reference,owner,phase,type(exc).__name__,time.time()))
 return reference

async def google_request(client,method,url,**kwargs):
 # Retrying GET is safe. A token POST is retried only when connection setup
 # failed before a request could be delivered; never retry an ambiguous exchange.
 for attempt in range(3):
  try:return await client.request(method,url,**kwargs)
  except httpx.HTTPError as exc:
   safe=method=='GET' or isinstance(exc,(httpx.ConnectError,httpx.ConnectTimeout))
   if not safe or attempt==2:raise
   await asyncio.sleep(.4*(attempt+1))

async def complete_binding(owner,token):
 try:
  async with httpx.AsyncClient(proxy=google_proxy(),timeout=httpx.Timeout(30,connect=8)) as client:
   response=await google_request(client,'GET','https://www.googleapis.com/youtube/v3/channels',params={'part':'snippet,contentDetails','mine':'true'},headers={'Authorization':'Bearer '+token['access_token']})
  if response.is_error:raise api_error(response)
  channels=response.json().get('items',[])
  if not channels:raise HTTPException(400,'Google授权已收到，但账号没有可访问的YouTube频道；请先创建频道后点击继续完成绑定。')
 except httpx.HTTPError as exc:
  reference=note_failure(owner,'channel_lookup',exc)
  raise HTTPException(502,'Google授权已加密保存，但YouTube频道查询连接失败（'+type(exc).__name__+'）。请点击“继续完成绑定”，无需再次授权。参考号：'+reference) from exc
 except (KeyError,ValueError,TypeError) as exc:
  reference=note_failure(owner,'channel_response',exc)
  raise HTTPException(502,'YouTube返回的频道资料格式异常，授权已保留，可继续完成绑定。参考号：'+reference) from exc
 pending_table()
 try:
  with store.LOCK,db() as c:
   count=0
   for channel in channels:
    cid=channel.get('id')
    if not cid:continue
    existing=c.execute('SELECT id,token FROM ops_channels WHERE owner=? AND channel_id=?',(owner,cid)).fetchone()
    # A new/empty channel can omit contentDetails or its uploads playlist.
    # Binding must succeed independently of whether it already has videos.
    playlist=((channel.get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads')
    saved=dict(token,uploads_playlist=playlist)
    if existing and not saved.get('refresh_token'):saved['refresh_token']=decrypt(existing[1]).get('refresh_token')
    if not saved.get('refresh_token'):raise HTTPException(400,'Google未返回离线授权，请重新绑定并确认同意离线访问。')
    title=(channel.get('snippet') or {}).get('title') or cid
    c.execute('INSERT INTO ops_channels VALUES(?,?,?,?,?,?) ON CONFLICT(owner,channel_id) DO UPDATE SET title=excluded.title,token=excluded.token',(existing[0] if existing else secrets.token_hex(16),owner,cid,title,encrypt(saved),time.time()));count+=1
   if not count:raise HTTPException(502,'YouTube响应缺少有效频道编号，授权已保留，请继续重试。')
   c.execute('DELETE FROM ops_oauth_pending WHERE owner=?',(owner,))
 except HTTPException:raise
 except Exception as exc:
  reference=note_failure(owner,'save_channel',exc)
  raise HTTPException(500,'频道授权已收到，但本地保存失败，授权已保留。参考号：'+reference) from exc

async def resume_binding(owner):
 pending_table()
 with db() as c:row=c.execute('SELECT token FROM ops_oauth_pending WHERE owner=? AND expires>?',(owner,time.time())).fetchone()
 if not row:raise HTTPException(409,'没有可恢复的授权，请重新点击绑定YouTube频道。')
 token=decrypt(row[0])
 if token.get('expires_at',time.time()+60)<time.time():
  if not token.get('refresh_token'):raise HTTPException(409,'授权已过期，请重新绑定频道。')
  data,_=settings()
  try:
   async with httpx.AsyncClient(proxy=google_proxy(),timeout=30) as client:
    response=await google_request(client,'POST','https://oauth2.googleapis.com/token',data={'client_id':data['client_id'],'client_secret':data['client_secret'],'refresh_token':token['refresh_token'],'grant_type':'refresh_token'})
  except httpx.HTTPError:raise HTTPException(502,'Google连接暂不可用，授权已保留，请检查代理后继续完成绑定。')
  if response.is_error:raise api_error(response)
  token.update(response.json());token['expires_at']=time.time()+token.get('expires_in',3600)-60
  with db() as c:c.execute('UPDATE ops_oauth_pending SET token=? WHERE owner=?',(encrypt(token),owner))
 await complete_binding(owner,token)

async def callback(request,state,code):
 initialize();sid=digest(request.cookies.get('ops_session',''))
 with store.LOCK,db() as c:
  row=c.execute('SELECT session,verifier,expires FROM ops_states WHERE id=?',(digest(state),)).fetchone()
  if not row or row[0]!=sid or row[2]<time.time():raise HTTPException(400,'授权状态已过期或浏览器会话不一致。请在同一个Chrome/Edge窗口中登录工作台后重新绑定。')
  c.execute('DELETE FROM ops_states WHERE id=?',(digest(state),))
 try:state_data=decrypt(row[1])
 except Exception as exc:raise HTTPException(500,'本地授权状态无法解密，请重新发起绑定。') from exc
 owner=state_data['owner'];data,redirect=settings()
 try:
  async with httpx.AsyncClient(proxy=google_proxy(),timeout=httpx.Timeout(40,connect=8)) as client:
   response=await google_request(client,'POST','https://oauth2.googleapis.com/token',data={'client_id':data['client_id'],'client_secret':data['client_secret'],'redirect_uri':redirect,'code':code,'code_verifier':state_data['verifier'],'grant_type':'authorization_code'})
  if response.is_error:raise api_error(response)
  token=response.json()
  if not token.get('access_token'):raise ValueError('missing access token')
 except httpx.HTTPError as exc:
  reference=note_failure(owner,'token_exchange',exc)
  raise HTTPException(502,'Google令牌交换连接失败（'+type(exc).__name__+'），尚未获取可保存的授权，请检查服务器到Google的代理连接后重新绑定。参考号：'+reference) from exc
 except (KeyError,ValueError,TypeError) as exc:
  reference=note_failure(owner,'token_response',exc)
  raise HTTPException(502,'Google令牌交换响应异常，请重新绑定。参考号：'+reference) from exc
 token['expires_at']=time.time()+token.get('expires_in',3600)-60
 granted=set(token.get('scope','').split())
 if not set(SCOPES).issubset(granted):raise HTTPException(400,'授权缺少评论访问、上传、频道只读或数据分析权限，请重新绑定并勾选全部所需权限。')
 pending_table()
 with db() as c:c.execute('INSERT INTO ops_oauth_pending VALUES(?,?,?) ON CONFLICT(owner) DO UPDATE SET token=excluded.token,expires=excluded.expires',(owner,encrypt(token),time.time()+7*86400))
 await complete_binding(owner,token)

def channels(owner):
 initialize()
 with db() as c:rows=c.execute('SELECT id,channel_id,title,created FROM ops_channels WHERE owner=?',(owner,)).fetchall()
 return [dict(zip(('id','channel_id','title','connected_at'),r)) for r in rows]

async def access(owner,connection):
 initialize();lock=LOCKS.setdefault('token:'+connection,asyncio.Lock())
 async with lock:
  with db() as c:row=c.execute('SELECT token,channel_id FROM ops_channels WHERE id=? AND owner=?',(connection,owner)).fetchone()
  if not row:raise HTTPException(404,'频道未绑定到当前账号。')
  token=decrypt(row[0])
  if token.get('expires_at',0)<time.time():
   data,_=settings()
   async with httpx.AsyncClient(proxy=google_proxy(),timeout=30) as c:r=await c.post('https://oauth2.googleapis.com/token',data={'client_id':data['client_id'],'client_secret':data['client_secret'],'refresh_token':token['refresh_token'],'grant_type':'refresh_token'})
   if r.is_error:raise api_error(r)
   token.update(r.json());token['expires_at']=time.time()+token.get('expires_in',3600)-60
   with db() as c:c.execute('UPDATE ops_channels SET token=? WHERE id=? AND owner=?',(encrypt(token),connection,owner))
  return token,row[1]

async def request_api(owner,connection,path,params=None,analytics=False):
 token,_=await access(owner,connection)
 try:
  async with httpx.AsyncClient(proxy=google_proxy(),timeout=httpx.Timeout(30,connect=8)) as c:
   r=await google_request(c,'GET',('https://youtubeanalytics.googleapis.com/v2/' if analytics else 'https://www.googleapis.com/youtube/v3/')+path,params=params,headers={'Authorization':'Bearer '+token['access_token']})
 except httpx.HTTPError as exc:raise HTTPException(502,'连接YouTube数据接口失败，请检查代理或稍后刷新。') from exc
 if r.is_error:raise api_error(r)
 return r.json()

async def overview(owner,connection):
 _,cid=await access(owner,connection)
 result=await request_api(owner,connection,'channels',{'part':'snippet,statistics','id':cid})
 return (result.get('items') or [{}])[0]

async def videos(owner,connection,page=None):
 token,cid=await access(owner,connection)
 if not token.get('uploads_playlist'):
  refreshed=await request_api(owner,connection,'channels',{'part':'contentDetails','id':cid})
  items=refreshed.get('items') or []
  playlist=(((items[0].get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads')) if items else None
  if not playlist:return {'items':[],'notice':'频道暂无可用的上传列表，绑定仍然有效。'}
  token['uploads_playlist']=playlist
  with db() as c:c.execute('UPDATE ops_channels SET token=? WHERE owner=? AND id=?',(encrypt(token),owner,connection))
 result=await request_api(owner,connection,'playlistItems',{'part':'contentDetails','playlistId':token['uploads_playlist'],'maxResults':25,**({'pageToken':page} if page else {})})
 ids=[r['contentDetails']['videoId'] for r in result.get('items',[])]
 if not ids:return {'items':[]}
 rows=await request_api(owner,connection,'videos',{'part':'snippet,statistics,status,contentDetails','id':','.join(ids)})
 return {'items':rows.get('items',[]),'nextPageToken':result.get('nextPageToken')}

async def comments(owner,connection,video_id=None,page=None):
 _,cid=await access(owner,connection)
 params={'part':'snippet','maxResults':30,'textFormat':'plainText','order':'time'}
 if video_id:
  check=await request_api(owner,connection,'videos',{'part':'snippet','id':video_id})
  if not check.get('items') or check['items'][0]['snippet']['channelId']!=cid:raise HTTPException(403,'只能查看当前绑定频道的视频评论。')
  params['videoId']=video_id
 else:params['allThreadsRelatedToChannelId']=cid
 if page:params['pageToken']=page
 return await request_api(owner,connection,'commentThreads',params)

async def analytics(owner,connection,start,end):
 return await request_api(owner,connection,'reports',{'ids':'channel==MINE','startDate':start,'endDate':end,'metrics':'views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost','dimensions':'day','sort':'day'},True)

def save_job(job):
 with db() as c:c.execute('UPDATE ops_jobs SET payload=?,updated=? WHERE id=? AND owner=?',(json.dumps(job,ensure_ascii=False),time.time(),job['id'],job['owner']))

def job_get(owner,jid):
 initialize()
 with db() as c:row=c.execute('SELECT payload FROM ops_jobs WHERE id=? AND owner=?',(jid,owner)).fetchone()
 if not row:raise HTTPException(404,'发布任务不存在。')
 return json.loads(row[0])

def job_list(owner):
 initialize()
 with db() as c:rows=c.execute('SELECT payload FROM ops_jobs WHERE owner=? ORDER BY updated DESC LIMIT 50',(owner,)).fetchall()
 return [public_job(json.loads(r[0])) for r in rows]

def public_job(job):return {k:v for k,v in job.items() if k not in ('owner','upload_session','session_expires','fingerprint')}

def create_job(owner,form):
 initialize();p=store.get(form['project_id'])
 if p.get('owner_id')!=owner or p.get('deleted_at'):raise HTTPException(404,'当前账号没有此作品的发布权限。')
 if p['status']!='completed':raise HTTPException(409,'作品尚未生成完成。')
 if form['revision']!=p['revision']:raise HTTPException(409,'作品已更新，请重新选择成片。')
 if not any(c['id']==form['connection_id'] for c in channels(owner)):raise HTTPException(404,'请选择当前账号已绑定的频道。')
 from app.creative import MUSIC
 if p.get('bgm',True):form['description']=(form['description'].strip()+'\n\nMusic credits:\n'+MUSIC[p.get('music','ambient')]['credit']).strip()
 if len(form['description'])>5000:raise HTTPException(400,'正文加配乐署名超过5000字，请缩短发布说明。')
 if form.get('publish_at'):
  try:when=datetime.fromisoformat(form['publish_at'].replace('Z','+00:00'))
  except ValueError:raise HTTPException(400,'定时发布时间格式不正确。')
  if not when.tzinfo or when<datetime.now(timezone.utc)+timedelta(minutes=15):raise HTTPException(400,'定时发布至少需要提前15分钟并包含时区。')
  form['privacy']='private';form['publish_at']=when.astimezone(timezone.utc).isoformat()
 raw=json.dumps([owner,form],sort_keys=True);fingerprint=digest(raw)
 with store.LOCK,db() as c:
  row=c.execute('SELECT payload FROM ops_jobs WHERE fingerprint=?',(fingerprint,)).fetchone()
  if row:return json.loads(row[0])
  job=dict(form,id=secrets.token_hex(16),owner=owner,status='queued',progress=0,created_at=datetime.now(timezone.utc).isoformat())
  c.execute('INSERT INTO ops_jobs VALUES(?,?,?,?,?)',(job['id'],owner,fingerprint,json.dumps(job,ensure_ascii=False),time.time()))
 return job

def launch(job):
 task=asyncio.create_task(upload(job['owner'],job['id']));TASKS.add(task);task.add_done_callback(TASKS.discard)

async def upload(owner,jid):
 lock=LOCKS.setdefault('job:'+jid,asyncio.Lock())
 if lock.locked():return
 async with lock:
  job=job_get(owner,jid)
  if job.get('video_id'):return
  path=DATA/job['project_id']/f'rev{job["revision"]}'/'final.mp4'
  if not path.is_file():job.update(status='failed',error='原始成片不存在。');save_job(job);return
  size=path.stat().st_size
  try:
   token,_=await access(owner,job['connection_id']);headers={'Authorization':'Bearer '+token['access_token']}
   async with httpx.AsyncClient(proxy=google_proxy(),timeout=httpx.Timeout(180,connect=20),follow_redirects=False) as c:
    if not job.get('upload_session'):
     status={'privacyStatus':job['privacy'],'selfDeclaredMadeForKids':job['made_for_kids'],'containsSyntheticMedia':job['contains_synthetic_media']}
     if job.get('publish_at'):status['publishAt']=job['publish_at']
     body={'snippet':{'title':job['title'],'description':job['description'],'categoryId':job['category_id']},'status':status}
     job.update(status='starting');save_job(job)
     try:r=await c.post('https://www.googleapis.com/upload/youtube/v3/videos',params={'uploadType':'resumable','part':'snippet,status'},headers=dict(headers,**{'X-Upload-Content-Type':'video/mp4','X-Upload-Content-Length':str(size)}),json=body)
     except httpx.HTTPError:job.update(status='uncertain',error='上传会话创建结果不明，请先核对YouTube Studio后再建立新任务，防止重复上传。');save_job(job);return
     if r.is_error:raise api_error(r)
     location=r.headers.get('location','');u=urlsplit(location)
     if u.scheme!='https' or u.hostname!='www.googleapis.com' or u.port not in (None,443):raise HTTPException(502,'Google返回异常上传会话地址。')
     job.update(upload_session=encrypt({'url':location}),status='uploading');save_job(job)
    location=decrypt(job['upload_session'])['url'];r=await c.put(location,headers=dict(headers,**{'Content-Length':'0','Content-Range':f'bytes */{size}'}),content=b'')
    if r.status_code in (200,201):result=r.json()
    elif r.status_code==308:
     offset=int(r.headers['range'].rsplit('-',1)[-1])+1 if r.headers.get('range') else 0
     with path.open('rb') as file:
      while offset<size:
       file.seek(offset);block=file.read(1024*1024*4);end=offset+len(block)-1
       r=await c.put(location,headers=dict(headers,**{'Content-Type':'video/mp4','Content-Length':str(len(block)),'Content-Range':f'bytes {offset}-{end}/{size}'}),content=block)
       if r.status_code in (200,201):result=r.json();break
       if r.status_code!=308:raise api_error(r)
       offset=int(r.headers.get('range',f'bytes=0-{end}').rsplit('-',1)[-1])+1;job.update(progress=min(99,int(offset/size*100)),status='uploading');save_job(job)
      else:raise HTTPException(502,'Google未确认上传完成，请恢复查询当前上传会话。')
    else:raise api_error(r)
    if not result.get('id'):raise HTTPException(502,'上传结果缺少视频编号，请核对YouTube Studio。')
    job.update(video_id=result['id'],url='https://www.youtube.com/watch?v='+result['id'],status='uploaded',progress=100,actual_privacy=result.get('status',{}).get('privacyStatus'),processing_status=result.get('status',{}).get('uploadStatus'));job.pop('error',None);save_job(job)
  except asyncio.CancelledError:
   job.update(status='interrupted',error='服务已停止，上传会话已保存，可继续上传。');save_job(job);raise
  except Exception as e:
   job.update(status='interrupted' if job.get('upload_session') else 'failed',error=str(e.detail) if isinstance(e,HTTPException) else '网络中断，已保留上传会话，请恢复当前任务。');save_job(job)

async def disconnect(owner,connection):
 with db() as c:row=c.execute('SELECT token FROM ops_channels WHERE owner=? AND id=?',(owner,connection)).fetchone()
 if not row:raise HTTPException(404,'频道不存在。')
 if any(j.get('connection_id')==connection and j['status'] in ('queued','starting','uploading') for j in job_list(owner)):raise HTTPException(409,'该频道存在正在上传的任务，请稍后解绑。')
 token=decrypt(row[0])
 async with httpx.AsyncClient(proxy=google_proxy(),timeout=20) as c:
  r=await c.post('https://oauth2.googleapis.com/revoke',data={'token':token.get('refresh_token') or token['access_token']})
  if r.status_code not in (200,400):raise api_error(r)
 with db() as c:c.execute('DELETE FROM ops_channels WHERE owner=? AND id=?',(owner,connection))

async def shutdown():
 for task in list(TASKS):task.cancel()
 if TASKS:await asyncio.gather(*list(TASKS),return_exceptions=True)
