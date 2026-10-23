import time,asyncio,secrets,os
from app.config import PUBLIC_ORIGIN
from datetime import date,timedelta
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import RedirectResponse,HTMLResponse,JSONResponse
from pydantic import BaseModel,Field
from typing import Literal
from app import store
from app import ops_auth as auth
from app import youtube_service as yt
router=APIRouter()

class Credentials(BaseModel):
 name:str=Field(min_length=3,max_length=60)
 password:str=Field(min_length=8,max_length=128)

def logged_response(uid):
 response=JSONResponse({'ok':True});response.set_cookie('ops_session',auth.session(uid),httponly=True,secure=bool(PUBLIC_ORIGIN),samesite='lax',max_age=7*86400,path='/');return response

@router.post('/api/ops/register')
async def register(req:Credentials):
 if os.getenv('ALLOW_REGISTRATION','1').lower() in ('0','false','no'):raise HTTPException(403,'自助注册未开放，请联系管理员。')
 return logged_response(await asyncio.to_thread(auth.register,req.name,req.password))
@router.post('/api/ops/login')
async def login(req:Credentials,request:Request):return logged_response(await asyncio.to_thread(auth.login,req.name,req.password,request.client.host if request.client else 'local'))
@router.post('/api/ops/logout')
async def logout(request:Request):
 auth.initialize()
 with auth.db() as c:c.execute('DELETE FROM ops_sessions WHERE id=?',(auth.digest(request.cookies.get('ops_session','')),))
 response=JSONResponse({'ok':True});response.delete_cookie('ops_session',path='/');return response

@router.get('/api/ops/session')
async def who(request:Request):
 user=auth.current(request)
 try:_,redirect=yt.settings();configured=True
 except HTTPException:configured=False;redirect=os.getenv('YOUTUBE_REDIRECT_URI','http://localhost:8000/api/auth/youtube/callback')
 return {'registration_open':os.getenv('ALLOW_REGISTRATION','1').lower() not in ('0','false','no'),'user':user,'youtube_configured':configured,'redirect_uri':redirect,'local_workbench':True,'scope_names':['上传视频','读取频道与评论','读取观看数据'],'channels':yt.channels(user['id']) if user else [],'pending_binding':yt.pending_status(user['id']) if user else {'can_resume':False}}

@router.post('/api/ops/youtube/connect')
async def connect(request:Request):return {'url':yt.authorization(request,auth.require(request))}

@router.get('/api/auth/youtube/callback')
async def youtube_callback(request:Request,state:str='',code:str='',error:str=''):
 try:
  if error:raise HTTPException(400,'你已取消Google授权，可返回工作台重新绑定。')
  if not state or not code:raise HTTPException(400,'缺少Google授权参数。')
  auth.require(request);await yt.callback(request,state,code)
  response=RedirectResponse((PUBLIC_ORIGIN or 'http://localhost:8020')+'/operations.html?youtube=connected',status_code=303)
 except HTTPException as e:
  from urllib.parse import urlencode
  response=RedirectResponse((PUBLIC_ORIGIN or 'http://localhost:8020')+'/operations.html?'+urlencode({'youtube':'failed','reason':str(e.detail)[:400]}),status_code=303)
 except Exception as exc:
  from urllib.parse import urlencode
  user=auth.current(request);reference=yt.note_failure(user['id'] if user else 'unknown','callback_unexpected',exc)
  response=RedirectResponse((PUBLIC_ORIGIN or 'http://localhost:8020')+'/operations.html?'+urlencode({'youtube':'failed','reason':'授权回调处理异常（'+type(exc).__name__+'），请重新绑定。参考号：'+reference}),status_code=303)
 response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer';return response

@router.post('/api/ops/youtube/resume-binding')
async def resume_binding(request:Request):
 await yt.resume_binding(auth.require(request)['id']);return {'ok':True}

@router.get('/api/ops/channels')
async def channels(request:Request):return yt.channels(auth.require(request)['id'])
@router.post('/api/ops/channels/{connection}/disconnect')
async def disconnect(connection:str,request:Request):await yt.disconnect(auth.require(request)['id'],connection);return {'ok':True}
@router.get('/api/ops/channels/{connection}/overview')
async def overview(connection:str,request:Request):return await yt.overview(auth.require(request)['id'],connection)
@router.get('/api/ops/channels/{connection}/videos')
async def videos(connection:str,request:Request,page:str|None=None):return await yt.videos(auth.require(request)['id'],connection,page)
@router.get('/api/ops/channels/{connection}/comments')
async def comments(connection:str,request:Request,video_id:str|None=None,page:str|None=None):return await yt.comments(auth.require(request)['id'],connection,video_id,page)
@router.get('/api/ops/channels/{connection}/analytics')
async def analytics(connection:str,request:Request,start:str|None=None,end:str|None=None):
 try:
  last=date.fromisoformat(end) if end else date.today()-timedelta(days=2);first=date.fromisoformat(start) if start else last-timedelta(days=27)
  if first>last or (last-first).days>366:raise ValueError()
 except ValueError:raise HTTPException(400,'请选择不超过一年的有效日期范围。')
 return await yt.analytics(auth.require(request)['id'],connection,first.isoformat(),last.isoformat())

@router.get('/api/ops/works')
async def works(request:Request):
 uid=auth.require(request)['id']
 return [{'id':p['id'],'title':p.get('title','宣传片'),'revision':p['revision'],'duration':sum(s['duration'] for s in p['plan']['shots']),'aspect_ratio':p.get('aspect_ratio','16:9'),'video_url':p.get('video_url')} for p in store.listing() if p.get('owner_id')==uid and not p.get('deleted_at') and p.get('status')=='completed' and p.get('plan')]

class Publish(BaseModel):
 project_id:str=Field(min_length=32,max_length=40)
 revision:int=Field(ge=1)
 connection_id:str=Field(min_length=32,max_length=32)
 title:str=Field(min_length=1,max_length=100)
 description:str=Field(default='',max_length=5000)
 privacy:Literal['private','unlisted','public']='private'
 made_for_kids:bool
 contains_synthetic_media:bool=True
 category_id:Literal['22','27','28','24','26','19','17']='22'
 publish_at:str|None=Field(default=None,max_length=40)
 confirm:bool=False

@router.post('/api/ops/publish')
async def publish(req:Publish,request:Request):
 uid=auth.require(request)['id']
 if not req.confirm:raise HTTPException(400,'请检查频道、成片、标题和可见性后明确确认上传。')
 data=req.model_dump(exclude={'confirm'})
 try:job=yt.create_job(uid,data)
 except KeyError:raise HTTPException(404,'作品不存在。')
 if job['status'] not in ('uploaded','uncertain','starting','uploading'):yt.launch(job)
 return yt.public_job(job)
@router.get('/api/ops/jobs')
async def jobs(request:Request):return yt.job_list(auth.require(request)['id'])
@router.post('/api/ops/jobs/{jid}/resume')
async def resume(jid:str,request:Request):
 job=yt.job_get(auth.require(request)['id'],jid)
 if job['status']=='uncertain':raise HTTPException(409,'创建会话结果尚不确定，请先核对YouTube Studio，避免重复上传。')
 if job['status']=='uploaded':return yt.public_job(job)
 yt.launch(job);return yt.public_job(job)

