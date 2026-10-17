import unittest,json,asyncio
from unittest.mock import patch
from app.creative import audit_plan,MUSIC,director_context
from app.schemas import Plan

def plan():
 return {'title':'方案','style':'浅色清晰','audience':'客户','rationale':'资料依据','music':'house_vibez',
 'creative':{'narrative':'problem_solution','energy':'balanced','background':'#eef7fa','foreground':'#152631','accent':'#0b6170'},
 'shots':[{'title':'功能','narration':'了解功能','image_prompt':'clean illustration','source':'image','duration':5,'motion':m,'purpose':'解释该功能'} for m in ['push','pan','pull']]}

class CreativeTests(unittest.TestCase):
 def test_render_defaults_do_not_overwrite_director_music(self):
  from app.main import Confirm
  self.assertIsNone(Confirm(revision=1).music)
 def test_new_plan_survives_validation(self):
  p=Plan.model_validate(plan()).model_dump();self.assertEqual(p['creative']['accent'],'#0b6170');self.assertEqual(p['shots'][2]['motion'],'pull')
 def test_duplicate_detected_without_exposing_source(self):
  p=plan();a=audit_plan(p,{'creative_context':{'recent_creatives':[{'music':'house_vibez','motions':['push','pan','pull']}]}});self.assertTrue(a['matches_recent'])
 def test_generation_cost_cap(self):
  p=plan();p['shots']=(p['shots']*3)[:7]
  with self.assertRaises(ValueError):Plan.model_validate(p)
 def test_scroll_only_for_true_website(self):
  p=plan();p['shots'][0]['motion']='page_scroll'
  with self.assertRaises(ValueError):Plan.model_validate(p)
 def test_max_twelve_capture_indices(self):
  p=plan();p['shots'][0].update(source='website',screenshot_index=11,motion='page_scroll');Plan.model_validate(p)
  p['shots'][0]['screenshot_index']=12
  with self.assertRaises(ValueError):Plan.model_validate(p)
 def test_brand_cannot_repeat(self):
  p=plan();p['shots'][0]['motion']=p['shots'][1]['motion']='brand'
  with self.assertRaises(ValueError):Plan.model_validate(p)
 def test_unused_brand_video_is_not_purchased(self):
  p=plan();p['shots'][2].update(motion='brand',video=True)
  with self.assertRaises(ValueError):Plan.model_validate(p)
 def test_music_catalog_has_resolvable_attribution(self):
  self.assertGreaterEqual(len(MUSIC),12)
  for m in MUSIC.values():self.assertTrue(m['file']);self.assertTrue(m['credit'])
 def test_unreadable_palette_is_rejected(self):
  p=plan();p['creative']['foreground']='#eef7fa'
  with self.assertRaises(ValueError):Plan.model_validate(p)
 def test_context_contains_history_not_business_content(self):
  with patch('app.creative.recent_creatives',return_value=[{'music':'urban'}]):
   ctx=director_context({'platform':'douyin'});self.assertEqual(ctx['recent_creatives'][0]['music'],'urban');self.assertEqual(ctx['platform']['aspect'],'9:16')

class DirectorContractTests(unittest.IsolatedAsyncioTestCase):
 async def test_invalid_json_is_repaired_once(self):
  import httpx
  from app.deepseek import DeepSeekProvider
  original=httpx.AsyncClient;requests=[]
  def handler(req):
   requests.append(json.loads(req.content));content='not-json' if len(requests)==1 else json.dumps({'reply':'方案','ready':True,'plan':plan()})
   return httpx.Response(200,json={'choices':[{'message':{'content':content}}]})
  with patch('app.deepseek.CONFIG',{'DEEPSEEK_API_KEY':'unit-key'}),patch('app.deepseek.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
   result=await DeepSeekProvider().converse({'mode':'text','source':'测试','messages':[]})
  self.assertTrue(result['ready']);self.assertEqual(len(requests),2);self.assertEqual(len(requests[1]['messages']),5);self.assertNotIn('tools',requests[1])
 async def test_duplicate_after_repair_is_rejected(self):
  import httpx
  from app.deepseek import DeepSeekProvider,ProviderError
  original=httpx.AsyncClient;calls=[]
  def handler(req):
   calls.append(1);return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'reply':'方案','ready':True,'plan':plan()})}}]})
  p={'mode':'text','source':'测试','messages':[],'creative_context':{'recent_creatives':[{'music':'house_vibez','motions':['push','pan','pull']}]}}
  with patch('app.deepseek.CONFIG',{'DEEPSEEK_API_KEY':'unit-key'}),patch('app.deepseek.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
   with self.assertRaises(ProviderError):await DeepSeekProvider().converse(p)
  self.assertEqual(len(calls),3)

if __name__=='__main__':unittest.main()
