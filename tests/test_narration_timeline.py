import unittest,tempfile,wave
from pathlib import Path
from unittest.mock import patch,AsyncMock
from app.narration_timeline import prepare_measured

class MeasuredTimelineTests(unittest.IsolatedAsyncioTestCase):
 async def test_measured_audio_controls_scene_and_caption_boundaries(self):
  with tempfile.TemporaryDirectory() as tmp:
   p={'plan':{'shots':[{'duration':2},{'duration':2},{'duration':4}],'narration_beats':[{'text':'先比较方案，再做选择。','shot_indices':[0,1],'pause_after':.4},{'text':'单证，围绕同一票业务。','shot_indices':[2],'pause_after':.4}]},'assets':{}}
   async def generate(text,path,seconds,voice):
    length=3 if text.startswith('先') else 4
    with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(bytes(length*48000))
    return length
   mock=AsyncMock(side_effect=generate)
   with patch('app.narration_timeline.SpeechProvider.generate',mock),patch('app.narration_timeline.store.save'):
    await prepare_measured(p,Path(tmp),'kokoro_zm_011');await prepare_measured(p,Path(tmp),'kokoro_zm_011')
   self.assertEqual(mock.await_count,2)
   t=p['render_timeline'];self.assertEqual(t[0]['from'],0)
   for a,b in zip(t,t[1:]):self.assertEqual(a['from']+a['duration_frames'],b['from'])
   for cue in p['narration_track']['cues']:
    a=t[cue['shot_indices'][0]];b=t[cue['shot_indices'][-1]]
    self.assertGreaterEqual(cue['start'],a['from']/30);self.assertLessEqual(cue['end'],(b['from']+b['duration_frames'])/30)
   with wave.open(str(Path(tmp)/'narration.wav')) as w:self.assertAlmostEqual(w.getnframes()/w.getframerate(),p['render_duration'])
   self.assertEqual(round(p['render_duration']*30),t[-1]['from']+t[-1]['duration_frames'])
 async def test_invalid_visual_binding_is_rejected_before_tts(self):
  p={'plan':{'shots':[{'duration':2}]*3,'narration_beats':[{'text':'不能跳过镜头。','shot_indices':[0,2]}]},'assets':{}}
  with patch('app.narration_timeline.SpeechProvider.generate',new_callable=AsyncMock) as generate:
   with self.assertRaises(ValueError):await prepare_measured(p,Path('.'),'kokoro_zm_011')
   generate.assert_not_called()
