import unittest,asyncio
from unittest.mock import patch
from app.director import DirectorAgent
from app.schemas import Plan
class SoundTests(unittest.TestCase):
 def test_explicit_voice_overrides_recommendation(self):
  class Provider:
   async def converse(self,p):return {'reply':'方案','ready':True,'plan':{'title':'测试','voice':'Ethan','music':'cipher'}}
  p={'messages':[],'revision':0}
  with patch('app.director.store.save'):
   asyncio.run(DirectorAgent(Provider()).talk(p,'女声',False,{'voice':'Cherry','music':'ambient'}))
  self.assertEqual(p['plan']['voice'],'Cherry');self.assertEqual(p['music'],'ambient')
 def test_auto_uses_recommendation(self):
  class Provider:
   async def converse(self,p):return {'reply':'方案','ready':True,'plan':{'title':'测试','voice':'Serena','music':'ambient'}}
  p={'messages':[],'revision':0}
  with patch('app.director.store.save'),patch('app.audio_catalog.kokoro_ready',return_value=True):
   asyncio.run(DirectorAgent(Provider()).talk(p,'推荐',False,{'voice':None,'music':None}))
  self.assertEqual(p['voice'],'kokoro_zf_001')
