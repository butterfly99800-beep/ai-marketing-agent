import tempfile,unittest,asyncio,json
from pathlib import Path
from unittest.mock import patch,AsyncMock
from fastapi.testclient import TestClient
from app import store
from app.main import app
from app.schemas import Plan,DirectorReply
from app.media import public_url
from app.deepseek import DeepSeekProvider,ProviderError
PLAN={'title':'示例','style':'科技','audience':'企业','rationale':'根据资料','shots':[{'title':'介绍','narration':'了解服务','image_prompt':'a harbor','duration':6,'motion':'push','source':'image','evidence':['海运']} for _ in range(3)]}
PLAN=Plan.model_validate(PLAN).model_dump()
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.patch=patch.multiple(store,DB=self.path/'test.sqlite',DATA=self.path);self.patch.start();store.initialize();self.client=TestClient(app,base_url='http://localhost:8020');self.headers={'Origin':'http://localhost:8020'}
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def new(self):return self.client.post('/api/projects',json={'mode':'text','source':'海运企业','platform':'douyin'},headers=self.headers).json()
 def test_keys_never_returned(self):
  r=self.client.get('/api/config');self.assertEqual(r.status_code,200);self.assertNotIn('API_KEY',r.text);self.assertNotIn('sk-',r.text)
 def test_origin_required(self):self.assertEqual(self.client.post('/api/projects',json={'mode':'text','source':'a'}).status_code,403)
 def test_invalid_mode(self):self.assertEqual(self.client.post('/api/projects',json={'mode':'fake','source':'a'},headers=self.headers).status_code,422)
 def test_persist_history(self):
  p=self.new();self.assertEqual(self.client.get('/api/projects/'+p['id']).json()['source'],'海运企业');self.assertEqual(len(self.client.get('/api/projects').json()),1)
 def test_plan_caps(self):
  d=json.loads(json.dumps(PLAN));d['shots']*=5
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_video_cap(self):
  d=json.loads(json.dumps(PLAN))
  for s in d['shots']:s['video']=True
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_unknown_fields_rejected(self):
  with self.assertRaises(ValueError):DirectorReply.model_validate({'reply':'好','secret':'x'})
 def test_private_url_denied(self):
  for u in ['http://127.0.0.1','http://169.254.169.254','http://10.0.0.1','file:///etc/passwd','https://user:pass@example.com']:
   with self.assertRaises(ProviderError):public_url(u)
 def test_no_render_without_plan(self):
  p=self.new();self.assertEqual(self.client.post('/api/projects/'+p['id']+'/render',headers=self.headers,json={'revision':0}).status_code,409)
 def test_stale_revision_denied(self):
  p=self.new();p['plan']=PLAN;p['revision']=2;store.save(p);r=self.client.post('/api/projects/'+p['id']+'/render',headers=self.headers,json={'revision':1});self.assertEqual(r.status_code,409)
 def test_video_requires_explicit_budget(self):
  p=self.new();p['plan']=json.loads(json.dumps(PLAN));p['plan']['shots'][0]['video']=True;p['revision']=1;store.save(p);self.assertEqual(self.client.post('/api/projects/'+p['id']+'/render',headers=self.headers,json={'revision':1,'allow_video':False}).status_code,409)
 def test_chat_creates_reviewable_plan(self):
  p=self.new()
  with patch('app.main.DeepSeekProvider.converse',new=AsyncMock(return_value={'reply':'请确认三镜头','ready':True,'plan':PLAN})):
   r=self.client.post('/api/projects/'+p['id']+'/messages',headers=self.headers,json={'text':'给方案'})
  self.assertEqual(r.status_code,200);self.assertEqual(r.json()['status'],'awaiting_confirmation');self.assertEqual(r.json()['revision'],1)
 def test_chat_invalidates_old_plan(self):
  p=self.new();p['plan']=PLAN;p['revision']=1;store.save(p)
  with patch('app.main.DeepSeekProvider.converse',new=AsyncMock(return_value={'reply':'什么风格？','ready':False,'plan':None})):
   r=self.client.post('/api/projects/'+p['id']+'/messages',headers=self.headers,json={'text':'换风格'})
  self.assertIsNone(r.json()['plan']);self.assertEqual(self.client.post('/api/projects/'+p['id']+'/render',headers=self.headers,json={'revision':1}).status_code,409)
 def test_restart_preserves_submitted_tasks(self):
  p=self.new();p['status']='producing';p['assets']={'0':{'image_task':'existing-provider-id'}};store.save(p)
  with TestClient(app,base_url='http://localhost:8020') as client:
   restored=client.get('/api/projects/'+p['id']).json()
  self.assertEqual(restored['status'],'interrupted');self.assertEqual(restored['assets']['0']['image_task'],'existing-provider-id')
 def test_duplicate_complete_render_is_idempotent(self):
  p=self.new();p['revision']=1;p['status']='completed';p['plan']=PLAN;store.save(p)
  with patch('app.main.produce',new=AsyncMock()) as run:
   self.assertEqual(self.client.post('/api/projects/'+p['id']+'/render',headers=self.headers,json={'revision':1}).status_code,200)
   run.assert_not_called()
 def test_sources_not_public(self):self.assertEqual(self.client.get('/api保存位置.env').status_code,404)
class MoreTests(unittest.TestCase):
 def test_image_null_index_normalized(self):
  d=json.loads(json.dumps(PLAN));d['shots'][0]['screenshot_index']=None
  self.assertEqual(Plan.model_validate(d).shots[0].screenshot_index,0)
 def test_website_null_index_rejected(self):
  d=json.loads(json.dumps(PLAN));d['shots'][0]['source']='website';d['shots'][0]['screenshot_index']=None
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_video_fraction_cap(self):
  d=json.loads(json.dumps(PLAN));d['shots'][0]['video']=d['shots'][1]['video']=True;d['shots'][0]['duration']=d['shots'][1]['duration']=5
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_looped_video_duration_denied(self):
  d=json.loads(json.dumps(PLAN));d['shots'][0]['video']=True;d['shots'][0]['duration']=10
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_brand_hold_budget(self):
  d=json.loads(json.dumps(PLAN));d['shots'][0]['title']='A'*25;d['shots'][0]['motion']='brand'
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_visual_text_budget(self):
  d=json.loads(json.dumps(PLAN));d['shots'][0]['narration']='文'*40
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_unbroken_wide_english_rejected(self):
  d=json.loads(json.dumps(PLAN));d['shots'][0]['title']='W'*32
  with self.assertRaises(ValueError):Plan.model_validate(d)
  d=json.loads(json.dumps(PLAN));d['shots'][0]['narration']='W'*64
  with self.assertRaises(ValueError):Plan.model_validate(d)
 def test_wan_single_image_contract(self):
  import httpx
  from app.wan import WanProvider
  records=[];original=httpx.AsyncClient
  def handler(request):records.append(json.loads(request.content));return httpx.Response(200,json={'output':{'task_id':'unit-task'}})
  with patch('app.wan.CONFIG',{'DASHSCOPE_API_KEY':'unit-only'}),patch('app.wan.httpx.AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs)):
   self.assertEqual(asyncio.run(WanProvider().submit('港口',True)),'unit-task')
  self.assertEqual(records[0]['parameters']['n'],1);self.assertEqual(records[0]['parameters']['size'],'720*1280')
 def test_wan_video_five_second_contract(self):
  import httpx
  from app.wan import WanProvider
  records=[];original=httpx.AsyncClient
  def handler(request):records.append(json.loads(request.content));return httpx.Response(200,json={'output':{'task_id':'unit-task'}})
  with tempfile.TemporaryDirectory() as tmp:
   image=Path(tmp)/'image.png';image.write_bytes(b'png')
   with patch('app.wan.CONFIG',{'DASHSCOPE_API_KEY':'unit-only'}),patch('app.wan.httpx.AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs)):
    asyncio.run(WanProvider().submit('自然运动',True,image))
  self.assertEqual(records[0]['parameters']['duration'],5);self.assertEqual(records[0]['parameters']['resolution'],'720P')
if __name__=='__main__':unittest.main()

