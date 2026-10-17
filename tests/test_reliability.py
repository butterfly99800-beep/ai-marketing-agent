import unittest,tempfile,asyncio,json
from pathlib import Path
from unittest.mock import patch
import httpx
from app.deepseek import DeepSeekProvider,ProviderError
from app.speech import SpeechProvider
class ReliabilityTests(unittest.IsolatedAsyncioTestCase):
 async def test_http_status_distinguished_from_invalid_plan(self):
  original=httpx.AsyncClient
  def handler(req):return httpx.Response(401,json={'error':'unauthorized'})
  p={'mode':'text','source':'test','messages':[],'network_enabled':False}
  with patch('app.deepseek.CONFIG',{'DEEPSEEK_API_KEY':'test-key'}),patch('app.deepseek.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
   with self.assertRaisesRegex(ProviderError,'HTTP 401'):await DeepSeekProvider().converse(p)
  self.assertEqual(p['diagnostics'][0]['stage'],'deepseek_http')
 async def test_pending_speech_uses_local_without_http_submission(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'work/voice_cache').mkdir(parents=True)
   import hashlib
   key=hashlib.sha256(('qwen3-tts-flash'+'Ethan'+'测试').encode()).hexdigest()
   (root/'work/voice_cache'/f'{key}.json').write_text('{"pending":true}')
   with patch('app.speech.ROOT',root),patch('app.speech.CONFIG',{}),patch('app.speech.speak',return_value=1.2) as local,patch('app.speech.httpx.AsyncClient') as cloud:
    provider=SpeechProvider();self.assertEqual(await provider.generate('测试',root/'voice.wav',4),1.2)
    cloud.assert_not_called();local.assert_called_once();self.assertTrue(provider.fallback_reason)
