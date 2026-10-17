import unittest,tempfile,asyncio,wave
from pathlib import Path
from unittest.mock import patch,AsyncMock
from app.schemas import Plan
from app.main import New,Message
from app.preferences import apply_preferences
from app.producer import prepare_narration
from app.speech import SpeechProvider
from app.deepseek import ProviderError
from app.creative import licensed_music,MUSIC,director_context
class MediaTests(unittest.IsolatedAsyncioTestCase):
 def test_platform_does_not_force_orientation(self):
  p={};apply_preferences(p,New(mode='text',source='抖音宣传片',platforms=['douyin','youtube'],aspect_ratio='16:9'))
  self.assertEqual(p['aspect_ratio'],'16:9');self.assertEqual(p['platforms'],['douyin','youtube'])
  apply_preferences(p,Message(text='油管也要竖版，无配音',aspect_ratio='16:9'))
  self.assertEqual(p['aspect_ratio'],'9:16');self.assertFalse(p['narration_enabled'])
 def test_only_licensed_tracks_available(self):
  tracks=licensed_music();self.assertGreaterEqual(len(tracks),12)
  self.assertNotIn('house_vibez',tracks);self.assertIn('inspired',tracks)
  for item in tracks.values():self.assertTrue(item.get('license'));self.assertTrue(item['credit'])
 async def test_disabled_narration_never_calls_tts(self):
  with tempfile.TemporaryDirectory() as tmp:
   p={'voice':'kokoro_zf_001','narration_enabled':False,'events':[],'assets':{},'plan':{'shots':[{'narration':'测试','duration':2}]*3}}
   with patch('app.producer.store.save'),patch('app.producer.SpeechProvider.generate',new_callable=AsyncMock) as generate:
    await prepare_narration(p,Path(tmp));generate.assert_not_awaited()
   self.assertTrue(all(a['voice_duration']==0 and a['voice_provider']=='disabled' for a in p['assets'].values()))
 async def test_every_shot_uses_same_locked_voice(self):
  with tempfile.TemporaryDirectory() as tmp:
   p={'voice':'kokoro_zm_010','events':[],'assets':{},'plan':{'shots':[{'narration':'测试','duration':2}]*3}}
   with patch('app.producer.store.save'),patch('app.producer.SpeechProvider.generate',new_callable=AsyncMock,return_value=1) as generate:
    await prepare_narration(p,Path(tmp))
   self.assertEqual({c.args[3] for c in generate.await_args_list},{'kokoro_zm_010'})
   self.assertEqual({a['voice_id'] for a in p['assets'].values()},{p['voice_lock']['id']})
 async def test_strict_voice_failure_does_not_switch_to_windows(self):
  provider=SpeechProvider(strict_voice=True)
  with patch('app.speech.speak') as speak:
   with self.assertRaisesRegex(ProviderError,'不会中途换音色'):await provider.fallback('测试',Path('none.wav'),2,'云端超时')
   speak.assert_not_called()
 def test_short_shots_can_reuse_prior_material_without_new_image_cost(self):
  from test_creative import plan
  p=plan();p['shots']=[dict(p['shots'][0],duration=2,asset_ref=None,motion='push')]+[dict(p['shots'][1],duration=2,asset_ref=0,motion='pan') for _ in range(6)]+[dict(p['shots'][2],duration=2,asset_ref=0,motion='pull')]
  result=Plan.model_validate(p);self.assertEqual(len(result.shots),8)
  self.assertEqual(sum(s.source=='image' and s.asset_ref is None for s in result.shots),1)
  p['shots'][0]['asset_ref']=1
  with self.assertRaises(ValueError):Plan.model_validate(p)

 def test_cannot_reuse_ai_video_as_a_still_image(self):
  from test_creative import plan
  p=plan();p['shots'][0].update(video=True,duration=5);p['shots'][1].update(asset_ref=0,video=False)
  with self.assertRaisesRegex(ValueError,'复用素材'):Plan.model_validate(p)
 def test_completed_render_options_detect_changes(self):
  from app.main import Confirm,render_options
  p={'platform':'youtube','aspect_ratio':'16:9','narration_enabled':True,'platforms':['youtube'],'voice':'kokoro_zf_001','music':'pulse','bgm':True}
  self.assertEqual(render_options(p),render_options(p,Confirm(revision=1)))
  self.assertNotEqual(render_options(p),render_options(p,Confirm(revision=1,narration_enabled=False)))
  self.assertNotEqual(render_options(p),render_options(p,Confirm(revision=1,aspect_ratio='9:16')))
