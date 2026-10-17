import unittest,tempfile,json,asyncio,time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
import httpx
from app import store,ops_auth as auth,youtube_service as yt
from app.main import app
from app.wan import WanProvider,SubmissionError
from app.web_fetch import relevant

class OperationsTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name);self.patches=[patch('app.youtube_service.google_proxy',return_value=None),patch.multiple(store,DB=self.folder/'db.sqlite',DATA=self.folder),patch.object(yt,'DATA',self.folder),patch.object(auth,'ROOT',self.folder)]
  for p in self.patches:p.start()
  (self.folder/'work').mkdir();store.initialize();auth.initialize()
  self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8020',headers={'Origin':'http://localhost:8020'})
 async def asyncTearDown(self):
  await yt.shutdown();await self.c.aclose()
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 async def register(self,name='operator'):
  r=await self.c.post('/api/ops/register',json={'name':name,'password':'test-password-strong'});self.assertEqual(r.status_code,200)
  return (await self.c.get('/api/ops/session')).json()['user']['id']
 async def make_work(self,uid):
  p=store.create('text','测试','youtube');p.update(owner_id=uid,status='completed',revision=1,title='成片',music='carefree',bgm=True,plan={'shots':[{'duration':15}]});store.save(p)
  folder=self.folder/p['id']/'rev1';folder.mkdir(parents=True);(folder/'final.mp4').write_bytes(b'fake-video-test')
  with auth.db() as c:c.execute('INSERT INTO ops_channels VALUES(?,?,?,?,?,?)',('a'*32,uid,'channel-one','测试频道',auth.encrypt({'access_token':'secret-access','refresh_token':'secret-refresh','expires_at':time.time()+1000,'uploads_playlist':'uploads'}),time.time()))
  return p
 def form(self,p):return dict(project_id=p['id'],revision=1,connection_id='a'*32,title='发布标题',description='说明',privacy='private',made_for_kids=False,contains_synthetic_media=True,category_id='22',publish_at=None)
 async def test_login_cookie_is_http_only_and_password_not_stored_plain(self):
  uid=await self.register();self.assertIn('ops_session',self.c.cookies)
  with auth.db() as c:row=c.execute('SELECT password FROM ops_users WHERE id=?',(uid,)).fetchone()
  self.assertNotEqual(row[0],'test-password-strong')
  r=await self.c.post('/api/ops/login',json={'name':'operator','password':'test-password-strong'});self.assertIn('httponly',r.headers['set-cookie'].lower())
 async def test_encrypts_and_round_trips_tokens(self):
  value=auth.encrypt({'refresh_token':'sensitive'});self.assertNotIn('sensitive',value);self.assertEqual(auth.decrypt(value)['refresh_token'],'sensitive')
 async def test_first_operator_claims_legacy_work_and_second_cannot_access(self):
  p=store.create('text','legacy','youtube');uid=await self.register();self.assertEqual(store.get(p['id'])['owner_id'],uid)
  await self.c.post('/api/ops/logout',json={});await self.register('another')
  self.assertEqual((await self.c.get('/api/projects/'+p['id'])).status_code,404)
 async def test_public_catalog_never_returns_tokens_or_client_secret(self):
  uid=await self.register();await self.make_work(uid)
  text=(await self.c.get('/api/ops/session')).text
  self.assertNotIn('secret-access',text);self.assertNotIn('secret-refresh',text);self.assertNotIn('client_secret',text)
 async def test_oauth_state_and_pkce_bound_to_browser_and_exact_callback(self):
  uid=await self.register()
  fake={'client_id':'client','client_secret':'secret'}
  with patch.object(yt,'settings',return_value=(fake,'http://localhost:8000/api/auth/youtube/callback')):
   response=await self.c.post('/api/ops/youtube/connect',json={});query=parse_qs(urlsplit(response.json()['url']).query)
   self.assertEqual(query['redirect_uri'][0],'http://localhost:8000/api/auth/youtube/callback');self.assertEqual(query['code_challenge_method'],['S256']);self.assertNotIn('client_secret',query)
   from starlette.requests import Request
   request=Request({'type':'http','headers':[(b'cookie',b'ops_session=wrong')]})
   with self.assertRaises(Exception) as error:await yt.callback(request,query['state'][0],'code')
   self.assertEqual(error.exception.status_code,400)
 async def test_oauth_success_persists_encrypted_channel_and_state_is_single_use(self):
  uid=await self.register();original=httpx.AsyncClient
  fake={'client_id':'client','client_secret':'secret'}
  def handler(request):
   if request.url.host=='oauth2.googleapis.com':return httpx.Response(200,json={'access_token':'new-access','refresh_token':'new-refresh','expires_in':3600,'scope':' '.join(yt.SCOPES)})
   return httpx.Response(200,json={'items':[{'id':'new-channel','snippet':{'title':'新频道'},'contentDetails':{'relatedPlaylists':{'uploads':'new-uploads'}}}]})
  with patch.object(yt,'settings',return_value=(fake,'http://localhost:8000/api/auth/youtube/callback')):
   result=await self.c.post('/api/ops/youtube/connect',json={});state=parse_qs(urlsplit(result.json()['url']).query)['state'][0]
   with patch('app.youtube_service.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
    result=await self.c.get('/api/auth/youtube/callback',params={'state':state,'code':'test-code'});self.assertIn('connected',result.headers['location'])
   self.assertEqual(yt.channels(uid)[0]['channel_id'],'new-channel')
   again=await self.c.get('/api/auth/youtube/callback',params={'state':state,'code':'test-code'});self.assertIn('failed',again.headers['location'])
   with auth.db() as c:encrypted=c.execute('SELECT token FROM ops_channels').fetchone()[0]
   self.assertNotIn('new-refresh',encrypted)
 async def test_anonymous_cannot_read_registered_users_projects(self):
  await self.register();await self.c.post('/api/ops/logout',json={});self.assertEqual((await self.c.get('/api/projects')).status_code,401)
 async def test_confirm_required_and_credit_automatically_appended(self):
  uid=await self.register();p=await self.make_work(uid);form=self.form(p)
  r=await self.c.post('/api/ops/publish',json=form);self.assertEqual(r.status_code,400)
  with patch.object(yt,'launch') as launch:
   r=await self.c.post('/api/ops/publish',json=dict(form,confirm=True));self.assertEqual(r.status_code,200);self.assertIn('Kevin MacLeod',r.json()['description']);launch.assert_called_once()
 async def test_duplicate_submission_returns_same_job_and_cross_owner_denied(self):
  uid=await self.register();p=await self.make_work(uid);a=yt.create_job(uid,self.form(p));b=yt.create_job(uid,self.form(p));self.assertEqual(a['id'],b['id'])
  with self.assertRaises(Exception) as error:yt.job_get('other-owner',a['id'])
  self.assertEqual(error.exception.status_code,404)
 async def test_resumable_upload_and_duplicate_does_not_upload_twice(self):
  uid=await self.register();p=await self.make_work(uid);job=yt.create_job(uid,self.form(p));calls=[];original=httpx.AsyncClient
  def handler(request):
   calls.append(request)
   if request.method=='POST':return httpx.Response(200,headers={'Location':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test'})
   if request.headers.get('content-range','').startswith('bytes */'):return httpx.Response(308)
   return httpx.Response(200,json={'id':'video-test','status':{'privacyStatus':'private','uploadStatus':'uploaded'}})
  with patch('app.youtube_service.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
   await yt.upload(uid,job['id']);await yt.upload(uid,job['id'])
  saved=yt.job_get(uid,job['id']);self.assertEqual(saved['status'],'uploaded');self.assertEqual(len(calls),3);self.assertEqual(saved['video_id'],'video-test');self.assertEqual(calls[-1].content,b'fake-video-test')
  self.assertNotIn('upload_session',yt.public_job(saved))
 async def test_analytics_and_comments_use_owner_token_and_channel(self):
  uid=await self.register();await self.make_work(uid)
  with patch.object(yt,'request_api',return_value={'items':[]}) as api:
   await yt.comments(uid,'a'*32)
   self.assertEqual(api.call_args.args[3]['allThreadsRelatedToChannelId'],'channel-one')
  with patch.object(yt,'request_api',return_value={}) as api:
   await yt.analytics(uid,'a'*32,'2026-01-01','2026-01-28');self.assertEqual(api.call_args.args[-1],True)
 async def test_failed_submission_returns_real_code_and_is_retryable(self):
  original=httpx.AsyncClient
  def handler(r):return httpx.Response(400,json={'code':'InvalidParameter','message':'input.prompt invalid'})
  with patch('app.wan.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)),patch('app.wan.CONFIG',{'DASHSCOPE_API_KEY':'test'}):
   with self.assertRaises(SubmissionError) as caught:await WanProvider().submit('测试')
  self.assertTrue(caught.exception.definitive);self.assertIn('InvalidParameter',str(caught.exception))
 def test_search_rejects_generic_province_results(self):
  self.assertFalse(relevant('江苏科技大学计算机学院 官网','江苏省','江苏省介绍'))
  self.assertTrue(relevant('江苏科技大学计算机学院 官网','江苏科技大学计算机学院','学校官网'))

 async def test_channel_network_failure_preserves_authorization_for_resume(self):
  uid=await self.register();original=httpx.AsyncClient;counts={'token':0,'channel':0}
  fake={'client_id':'client','client_secret':'secret'}
  def handler(request):
   if request.url.host=='oauth2.googleapis.com':
    counts['token']+=1;return httpx.Response(200,json={'access_token':'temporary-access','refresh_token':'saved-refresh','expires_in':3600,'scope':' '.join(yt.SCOPES)})
   counts['channel']+=1
   if counts['channel']<=3:raise httpx.ConnectError('test',request=request)
   return httpx.Response(200,json={'items':[{'id':'UCempty','snippet':{'title':'空频道'}}]})
  with patch.object(yt,'settings',return_value=(fake,'http://localhost:8000/api/auth/youtube/callback')):
   response=await self.c.post('/api/ops/youtube/connect',json={});state=parse_qs(urlsplit(response.json()['url']).query)['state'][0]
   with patch('app.youtube_service.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
    response=await self.c.get('/api/auth/youtube/callback',params={'state':state,'code':'code'});self.assertIn('failed',response.headers['location'])
    self.assertEqual(yt.channels(uid),[]);self.assertTrue(yt.pending_status(uid)['can_resume'])
    with auth.db() as c:raw=c.execute('SELECT token FROM ops_oauth_pending').fetchone()[0]
    self.assertNotIn('saved-refresh',raw)
    response=await self.c.post('/api/ops/youtube/resume-binding',json={});self.assertEqual(response.status_code,200)
   self.assertEqual(yt.channels(uid)[0]['title'],'空频道');self.assertFalse(yt.pending_status(uid)['can_resume']);self.assertEqual(counts['token'],1)
 async def test_ambiguous_token_timeout_is_not_retried(self):
  calls=[]
  def handler(request):calls.append(request);raise httpx.ReadTimeout('test',request=request)
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
   with self.assertRaises(httpx.ReadTimeout):await yt.google_request(client,'POST','https://oauth2.googleapis.com/token',data={'code':'test'})
  self.assertEqual(len(calls),1)
 async def test_connect_failure_before_delivery_can_retry_safely(self):
  calls=[]
  def handler(request):
   calls.append(request)
   if len(calls)==1:raise httpx.ConnectError('test',request=request)
   return httpx.Response(200,json={'ok':True})
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:response=await yt.google_request(client,'POST','https://oauth2.googleapis.com/token',data={})
  self.assertEqual(len(calls),2);self.assertEqual(response.status_code,200)

 async def test_rename_soft_delete_and_video_versions_are_private(self):
  uid=await self.register();p=await self.make_work(uid)
  from app import chat_workspace as workspace
  with patch.object(workspace,'DATA',self.folder):
   r=await self.c.patch('/api/projects/'+p['id'],json={'title':'我的新名称'});self.assertEqual(r.status_code,200);self.assertTrue(r.json()['custom_title'])
   library=(await self.c.get('/api/films')).json();self.assertEqual(library[0]['revision'],1)
   self.assertEqual((await self.c.get(library[0]['video_url'])).status_code,200)
   r=await self.c.delete('/api/projects/'+p['id']);self.assertEqual(r.status_code,200)
   self.assertEqual((await self.c.get('/api/films')).json(),[])
   self.assertEqual((await self.c.get('/api/projects/'+p['id'])).status_code,404)
   self.assertTrue((self.folder/p['id']/'rev1/final.mp4').exists())
   self.assertIsNotNone(store.get(p['id']).get('deleted_at'))
  await self.c.post('/api/ops/logout',json={});await self.register('second-user')
  self.assertEqual((await self.c.patch('/api/projects/'+p['id'],json={'title':'跨账号'})).status_code,404)

 async def test_chat_publish_generates_card_and_only_confirms_once(self):
  uid=await self.register();p=await self.make_work(uid);original=httpx.AsyncClient
  raw={'title':'让协作更顺畅','description':'把工作串起来。预约演示。','connection_id':'a'*32,'privacy':'private','made_for_kids':False,'category_id':'22'}
  def handler(request):return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(raw)}}]})
  with patch('app.chat_workspace.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)),patch.object(yt,'launch') as launch:
   r=await self.c.post('/api/projects/'+p['id']+'/publish-draft',json={'text':'帮我上传到YouTube'});self.assertEqual(r.status_code,200);launch.assert_not_called()
   draft=r.json()['publish_draft'];self.assertEqual(draft['form']['title'],raw['title'])
   wrong=await self.c.post('/api/projects/'+p['id']+'/publish-confirm',json={'token':'wrong'});self.assertEqual(wrong.status_code,409)
   a=await self.c.post('/api/projects/'+p['id']+'/publish-confirm',json={'token':draft['token']});self.assertEqual(a.status_code,200)
   b=await self.c.post('/api/projects/'+p['id']+'/publish-confirm',json={'token':draft['token']});self.assertEqual(a.json()['id'],b.json()['id'])
  self.assertEqual(len(yt.job_list(uid)),1)

 async def test_chat_publish_requires_bound_channel(self):
  uid=await self.register();p=await self.make_work(uid)
  with auth.db() as c:c.execute('DELETE FROM ops_channels WHERE owner=?',(uid,))
  r=await self.c.post('/api/projects/'+p['id']+'/publish-draft',json={});self.assertEqual(r.status_code,409)


if __name__=='__main__':unittest.main()
