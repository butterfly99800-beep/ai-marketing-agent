import unittest,json,hashlib,asyncio
from unittest.mock import patch
from app.config import ROOT
from app.creative import licensed_music,director_context
from app.music_matching import select_music,music_candidates
from app.schemas import Plan

class RealMusicTests(unittest.TestCase):
 def test_eleven_individually_verified_artist_tracks(self):
  report=json.loads((ROOT/'assets/licenses/incompetech-curated/import-report.json').read_text(encoding='utf8'))
  self.assertEqual(len(report),11)
  pool=licensed_music()
  for row in report:
   item=pool[row['id']];self.assertEqual(item['license'],'CC BY 4.0');self.assertTrue(item['attribution_required'])
   self.assertEqual(hashlib.sha256((ROOT/'renderer/public/audio'/item['file']).read_bytes()).hexdigest(),item['sha256'])
   self.assertGreater(item['duration_seconds'],60);self.assertTrue(item['official_metadata']['isrc'])
   self.assertTrue((ROOT/'assets/licenses/incompetech-curated'/(row['id']+'-credit.txt')).exists())
 def test_auto_uses_artist_music_for_different_subjects(self):
  choices=[]
  for brief in ['物流货代工业企业力量','咖啡餐饮酒店高级爵士','时尚服装年轻活动','招生学校教育校园温暖','软件科技产品解说','运动健身力量快节奏']:
   p={'source':brief,'pace':'fast','plan':{'music':'pulse','creative':{}}};key,why=select_music(p)
   self.assertEqual(licensed_music()[key]['origin'],'artist_composed');self.assertIn('真实作品',why);choices.append(key)
  self.assertGreaterEqual(len(set(choices)),5)
 def test_named_song_in_chat_wins_over_subject_matching(self):
  key,_=select_music({'source':'工业物流','messages':[{'role':'user','content':'配乐使用 Carefree'}]});self.assertEqual(key,'carefree')
 def test_explicit_synthetic_selection_still_wins(self):
  key,_=select_music({'source':'咖啡','sound_preferences':{'music':'pulse'}});self.assertEqual(key,'pulse')
 def test_recent_track_is_penalized_without_randomizing_retries(self):
  p={'id':'stable','source':'生活温暖','plan':{'music':'pulse'}};first=music_candidates(p)[0]['id']
  p['creative_context']={'recent_creatives':[{'music':first}]*4}
  second=music_candidates(p)[0]['id'];self.assertNotEqual(first,second);self.assertEqual(select_music(p),select_music(p))
 def test_context_and_schema_expose_new_music(self):
  with patch('app.creative.recent_creatives',return_value=[]):ctx=director_context({'platform':'youtube','source':'咖啡馆'})
  self.assertIn('apero_hour',ctx['music_catalog']);self.assertTrue(ctx['music_recommendations'])
  self.assertIn('apero_hour',str(Plan.model_json_schema()))

if __name__=='__main__':unittest.main()
