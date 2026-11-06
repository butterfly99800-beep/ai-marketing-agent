import asyncio,json,tempfile,time,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
import httpx,imageio_ffmpeg
from app import store,ops_auth as auth,social_publish as social,youtube_service as yt
from app.main import app

class SocialTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'work').mkdir()
  self.patches=[patch.multiple(store,DB=self.root/'test.sqlite',DATA=self.root),patch.object(social,'DATA',self.root),patch.object(auth,'ROOT',self.root),patch.dict('os.environ',{'ALLOW_REGISTRATION':'1'})]
  for p in self.patches:p.start()
  store.initialize();auth.initialize();social.initialize()
  self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8020',headers={'Origin':'http://localhost:8020'})
  await self.c.post('/api/ops/register',json={'name':'test-user','password':'test-password-strong'})
  self.uid=(await self.c.get('/api/ops/session')).json()['user']['id']
 async def asyncTearDown(self):
  await self.c.aclose()
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def draft(self,pid=None,platform='youtube',sha=None):
  p=store.create('text','test','youtube');p.update(owner_id=self.uid,status='completed',revision=1,title='测试作品',bgm=False,plan={'shots':[{'duration':4}]},content_sha256=sha);store.save(p)
  d=dict(id=__import__('secrets').token_hex(16),project_id=p['id'],revision=1,posts=[dict(platform=platform,title='Freight quotes',caption='Compare shipping options.',keywords=['ocean freight'],hashtags=['#Shipping'])])
  with store.connection() as c:c.execute('INSERT INTO social_drafts VALUES(?,?,?)',(d['id'],self.uid,json.dumps(d)))
  return d
 def form(self,d):return dict(draft_id=d['id'],platforms=[d['posts'][0]['platform']],connection_id='a'*32,start_at=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),interval_hours=6,privacy='private',made_for_kids=False,contains_synthetic_media=False,confirm=True)
 async def post_schedule(self,d):
  with patch.object(yt,'channels',return_value=[{'id':'a'*32}]):return await self.c.post('/api/ops/social/schedule',json=self.form(d))
 async def test_upload_real_mp4_and_requires_auth(self):
  path=self.root/'sample.mp4';subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-f','lavfi','-i','color=c=blue:s=160x90:d=1','-c:v','libx264','-y',str(path)],check=True,capture_output=True)
  r=await self.c.post('/api/ops/social/upload?filename=sample.mp4',content=path.read_bytes());self.assertEqual(r.status_code,200,r.text)
  p=store.get(r.json()['id']);self.assertEqual(p['owner_id'],self.uid);self.assertAlmostEqual(r.json()['duration'],1,places=1)
  self.assertTrue((self.root/p['id']/'rev1/final.mp4').exists())
  await self.c.post('/api/ops/logout');r=await self.c.get('/api/ops/social/platforms');self.assertEqual(r.status_code,401)
 async def test_rejects_fake_video(self):
  r=await self.c.post('/api/ops/social/upload?filename=bad.mp4',content=b'not a video');self.assertEqual(r.status_code,400)
 async def test_distinct_works_do_not_shift_each_others_start_and_dedup(self):
  a=self.draft(sha='same');b=self.draft(sha='different');c=self.draft(sha='same')
  x=await self.post_schedule(a);y=await self.post_schedule(b);self.assertEqual(x.status_code,200,x.text);self.assertEqual(y.status_code,200,y.text)
  self.assertLess(abs(y.json()[0]['due']-x.json()[0]['due']),5)
  self.assertEqual((await self.post_schedule(c)).status_code,409)
  self.assertEqual((await self.post_schedule(a)).status_code,409)
 async def test_unconfigured_platform_is_not_dispatched(self):
  d=self.draft(platform='tiktok');r=await self.post_schedule(d);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()[0]['status'],'awaiting_authorization')
  with patch.object(yt,'create_job') as create:await social.tick();create.assert_not_called()
 async def test_cancel_and_cross_owner_isolation(self):
  d=self.draft(platform='instagram');r=await self.post_schedule(d);qid=r.json()[0]['id']
  await self.c.post('/api/ops/logout');await self.c.post('/api/ops/register',json={'name':'another','password':'test-password-strong'})
  self.assertEqual((await self.c.get('/api/ops/social/queue')).json(),[])
  self.assertEqual((await self.c.post('/api/ops/social/queue/'+qid+'/cancel')).status_code,404)
  self.assertEqual((await self.c.put('/api/ops/social/drafts/'+d['id'],json={'posts':d['posts']})).status_code,404)
 async def test_dispatch_is_claimed_once_and_sends_keywords(self):
  d=self.draft();r=await self.post_schedule(d);item=r.json()[0];item['due']=time.time()-2
  with store.connection() as c:c.execute('UPDATE social_queue SET due=?,payload=? WHERE id=?',(item['due'],json.dumps(item),item['id']))
  with patch.object(yt,'create_job',return_value={'id':'job-one','status':'queued'}) as create,patch.object(yt,'launch') as launch,patch.object(yt,'job_get',return_value={'id':'job-one','status':'queued'}):
   await social.tick();await social.tick();create.assert_called_once();launch.assert_called_once();self.assertEqual(create.call_args.args[1]['tags'],['ocean freight'])
 async def test_prompt_validation_limits(self):
  raw={'posts':[dict(platform='x',title='Shipping',caption='x'*241,keywords=['freight'],hashtags=[])]}
  with self.assertRaises(ValueError):social.validate_posts(raw,['x'])
  raw['posts'][0]['caption']='Ocean freight tips';self.assertEqual(len(social.validate_posts(raw,['x'])),1)
 async def test_default_home_is_publishing(self):
  r=await self.c.get('/');self.assertIn('publisher.js',r.text)

 async def recurring(self,total=2):
  d=self.draft();form=self.form(d);form['repeat_count']=total
  with patch.object(yt,'channels',return_value=[{'id':'a'*32}]):r=await self.c.post('/api/ops/social/schedule',json=form)
  self.assertEqual(r.status_code,200,r.text);item=r.json()[0];item.update(due=time.time()-1,status='submitted',youtube_job_id='job-1');social.update_item(item);return item

 async def test_same_work_repeats_after_six_hours_then_finishes(self):
  item=await self.recurring();first_due=item['due']
  with patch.object(yt,'job_get',return_value={'id':'job-1','status':'uploaded','url':'https://www.youtube.com/watch?v=test'}):await social.tick()
  row=(await self.c.get('/api/ops/social/queue')).json()[0]
  self.assertEqual(row['status'],'scheduled');self.assertEqual(row['completed_count'],1);self.assertEqual(row['project_id'],item['project_id']);self.assertEqual(row['due'],first_due+21600)
  row['due']=time.time()-1;social.update_item(row)
  with patch.object(yt,'create_job',return_value={'id':'job-2','status':'queued'}) as create,patch.object(yt,'launch'):
   await social.tick();self.assertEqual(create.call_args.args[1]['project_id'],item['project_id']);self.assertEqual(create.call_args.args[1]['social_occurrence_id'],item['id']+':2')
  with patch.object(yt,'job_get',return_value={'id':'job-2','status':'uploaded'}):await social.tick();await social.tick()
  row=(await self.c.get('/api/ops/social/queue')).json()[0];self.assertEqual(row['status'],'completed');self.assertEqual(row['completed_count'],2)

 async def test_stopping_submitted_loop_keeps_current_upload_and_prevents_next(self):
  item=await self.recurring(0);r=await self.c.post('/api/ops/social/queue/'+item['id']+'/cancel');self.assertEqual(r.status_code,200)
  with patch.object(yt,'create_job') as create:await social.tick();create.assert_not_called()
  row=(await self.c.get('/api/ops/social/queue')).json()[0];self.assertEqual(row['status'],'stopped');self.assertEqual(row['youtube_job_id'],'job-1')

 async def test_uncertain_result_does_not_start_another_repeat(self):
  await self.recurring(0)
  with patch.object(yt,'job_get',return_value={'id':'job-1','status':'uncertain'}),patch.object(yt,'create_job') as create:await social.tick();create.assert_not_called()
  row=(await self.c.get('/api/ops/social/queue')).json()[0];self.assertEqual(row['completed_count'],0);self.assertEqual(row['status'],'submitted')

 async def test_missed_slots_do_not_create_a_burst(self):
  item=await self.recurring(0);item['due']=time.time()-20*3600;social.update_item(item)
  with patch.object(yt,'job_get',return_value={'id':'job-1','status':'uploaded'}),patch.object(yt,'create_job') as create:await social.tick();create.assert_not_called()
  row=(await self.c.get('/api/ops/social/queue')).json()[0];self.assertGreater(row['due'],time.time());self.assertEqual(row['completed_count'],1)

 async def test_x_rejects_repeat_but_allows_single(self):
  d=self.draft(platform='x');form=self.form(d);form['repeat_count']=0
  self.assertEqual((await self.c.post('/api/ops/social/schedule',json=form)).status_code,400)
  form['repeat_count']=1;self.assertEqual((await self.c.post('/api/ops/social/schedule',json=form)).status_code,200)

if __name__=='__main__':unittest.main()
