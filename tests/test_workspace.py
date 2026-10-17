import unittest,tempfile,asyncio,json
from pathlib import Path
from unittest.mock import patch
import httpx
from app import store
from app.main import app,TASKS,lifespan
from app.planning import fit_duration
from app.progress import snapshot,update
from app.deepseek import ProviderError
BASE={'title':'企业宣传','style':'电影感','voice':'Cherry','music':'cipher','audience':'外贸客户','rationale':'依据资料','shots':[{'title':'海运','narration':'提供海运服务','image_prompt':'harbor','duration':6,'motion':'push','source':'image','video':False,'evidence':['海运']} for _ in range(3)]}
class DurationTests(unittest.TestCase):
 def test_exact_odd_seconds_and_fixed_video(self):
  p=json.loads(json.dumps(BASE));p['shots'][0].update(video=True,duration=5)
  result=fit_duration(p,23);self.assertEqual(sum(s['duration'] for s in result['shots']),23);self.assertEqual(result['shots'][0]['duration'],5)
 def test_sixty_seconds(self):
  p=json.loads(json.dumps(BASE));p['shots']*=2;result=fit_duration(p,60);self.assertEqual(sum(s['duration'] for s in result['shots']),60)
 def test_impossible_duration_does_not_silently_change(self):
  with self.assertRaises(ProviderError):fit_duration(BASE,60)
 def test_estimate_not_fake_completion(self):
  p={'status':'producing','work':{'percent':75,'stage':'合成','started_at':'2000-01-01T00:00:00+00:00','estimated_seconds':100}};s=snapshot(p);self.assertEqual(s['percent'],75);self.assertIsNone(s['eta_min'])
class BackgroundTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.patch=patch.multiple(store,DB=root/'test.sqlite',DATA=root);self.patch.start();store.initialize();self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8020',headers={'Origin':'http://localhost:8020'})
 async def asyncTearDown(self):
  for task in list(TASKS):task.cancel()
  if TASKS:await asyncio.gather(*list(TASKS),return_exceptions=True)
  await self.client.aclose();self.patch.stop();self.tmp.cleanup()
 async def test_background_conversation_survives_navigation_and_client_close(self):
  a=store.create('text','海运','youtube',23);b=store.create('text','仓储','douyin');entered=asyncio.Event();release=asyncio.Event()
  async def delayed(_self,p):entered.set();await release.wait();return {'reply':'方案已准备','ready':True,'plan':json.loads(json.dumps(BASE))}
  with patch('app.deepseek.DeepSeekProvider.converse',new=delayed),patch('app.main.produce') as production:
   response=await self.client.post('/api/projects/'+a['id']+'/conversations',json={'text':'规划方案','target_duration':23});self.assertEqual(response.status_code,202)
   await asyncio.wait_for(entered.wait(),1)
   other=await self.client.get('/api/projects/'+b['id']);self.assertEqual(other.json()['id'],b['id'])
   busy=await asyncio.wait_for(self.client.post('/api/projects/'+a['id']+'/conversations',json={'text':'重复'}),1);self.assertEqual(busy.status_code,409)
   await self.client.aclose();release.set();await asyncio.gather(*list(TASKS));await asyncio.sleep(0)
  production.assert_not_awaited()
  saved=store.get(a['id']);self.assertEqual(saved['status'],'awaiting_confirmation');self.assertEqual(sum(s['duration'] for s in saved['plan']['shots']),23)
 async def test_render_runs_after_request_client_closed(self):
  p=store.create('text','海运','youtube');p.update(plan=json.loads(json.dumps(BASE)),revision=1);store.save(p);entered=asyncio.Event();release=asyncio.Event()
  async def fake(pid):entered.set();await release.wait();saved=store.get(pid);saved['status']='completed';store.save(saved)
  with patch('app.main.produce',new=fake):
   response=await self.client.post('/api/projects/'+p['id']+'/render',json={'revision':1});self.assertEqual(response.status_code,200)
   await entered.wait();await self.client.aclose();release.set();await asyncio.gather(*list(TASKS));await asyncio.sleep(0)
  self.assertEqual(store.get(p['id'])['status'],'completed')
 async def test_selected_duration_is_persisted_and_invalid_is_rejected(self):
  r=await self.client.post('/api/projects',json={'mode':'text','source':'海运','target_duration':47});self.assertEqual(r.json()['target_duration'],47)
  r=await self.client.post('/api/projects',json={'mode':'text','source':'海运','target_duration':61});self.assertEqual(r.status_code,422)
 async def test_listing_is_lightweight(self):
  p=store.create('text','海运'*5000,'youtube');p['messages']=[{'role':'user','content':'x'*10000}];store.save(p);r=await self.client.get('/api/projects');self.assertNotIn('source',r.json()[0]);self.assertLess(len(r.content),1200)
