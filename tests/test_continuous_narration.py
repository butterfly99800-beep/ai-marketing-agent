import unittest,tempfile,asyncio
from pathlib import Path
from unittest.mock import patch,AsyncMock
from app.continuous_narration import prepare_continuous,subtitle_cues
class ContinuousTests(unittest.IsolatedAsyncioTestCase):
 async def test_whole_film_one_call_and_cache(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);p={'plan':{'voiceover_script':'让信息顺着业务流动。现在，预约演示。','shots':[{'duration':3} for _ in range(10)]},'assets':{}}
   async def generate(text,path,seconds,voice):
    import wave
    with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*288000)
    return 12
   mock=AsyncMock(side_effect=generate)
   with patch('app.continuous_narration.SpeechProvider.generate',mock),patch('app.continuous_narration.store.save'):
    self.assertTrue(await prepare_continuous(p,folder,'kokoro_zm_011'));self.assertTrue(await prepare_continuous(p,folder,'kokoro_zm_011'))
   self.assertEqual(mock.await_count,1);self.assertEqual(len(p['assets']),10)
   self.assertEqual(p['narration_track']['mode'],'continuous')
 async def test_disabled_never_generates(self):
  with patch('app.continuous_narration.SpeechProvider.generate',new_callable=AsyncMock) as mock:
   p={'narration_enabled':False,'plan':{'voiceover_script':'测试'},'narration_track':{}}
   self.assertFalse(await prepare_continuous(p,Path('.'),'kokoro_zm_011'));mock.assert_not_called();self.assertNotIn('narration_track',p)
 def test_cues_bounded_and_sequential(self):
  cues=subtitle_cues('每一票货，都不该耗在反复确认上。让协作更顺手。',12)
  self.assertAlmostEqual(cues[-1]['end'],12.12);self.assertEqual(cues[0]['start'],.12)
  for a,b in zip(cues,cues[1:]):self.assertLessEqual(a['end'],b['start'])
