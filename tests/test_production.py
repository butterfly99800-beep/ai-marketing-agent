import unittest,os
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
class ProductionTests(unittest.TestCase):
 def test_public_origin_keeps_private_api_private(self):
  with patch('app.main.PUBLIC_ORIGIN','https://wyf.suiyizou.xyz'),patch('app.main.ALLOWED_HOSTS',{'wyf.suiyizou.xyz'}),patch('app.main.ALLOWED_ORIGINS',{'https://wyf.suiyizou.xyz'}):
   c=TestClient(app,base_url='https://wyf.suiyizou.xyz')
   self.assertEqual(c.get('/api/projects').status_code,401)
   result=c.get('/showcase/catalog.json');self.assertEqual(result.status_code,200);data=result.json()
   self.assertEqual(len(data['items']),3)
   for item in data['items']:
    self.assertNotIn('owner_id',item);self.assertNotIn('publish_draft',item);self.assertNotIn('assets',item)
   self.assertEqual(c.post('/api/ops/login',headers={'Origin':'https://evil.example'},json={}).status_code,403)
   self.assertEqual(c.get('/api/config',headers={'Host':'evil.example'}).status_code,403)
 def test_registration_can_be_disabled(self):
  with patch.dict(os.environ,{'ALLOW_REGISTRATION':'0'}):
   c=TestClient(app,base_url='http://localhost:8020');r=c.post('/api/ops/register',headers={'Origin':'http://localhost:8020'},json={'name':'unit-user','password':'unit-password'})
   self.assertEqual(r.status_code,403)
 def test_https_session_cookie_is_secure(self):
  from app.operations_routes import logged_response
  with patch('app.operations_routes.PUBLIC_ORIGIN','https://wyf.suiyizou.xyz'),patch('app.operations_routes.auth.session',return_value='unit-session'):
   cookie=logged_response('unit-user').headers['set-cookie'];self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie)

 def test_auto_voice_does_not_select_missing_local_model(self):
  from app.audio_catalog import select_voice
  with patch('app.audio_catalog.kokoro_ready',return_value=False):
   self.assertEqual(select_voice({'plan':{'voice':'kokoro_zm_011'}}),'Ethan')
   self.assertEqual(select_voice({'plan':{'voice':'kokoro_zf_001'}}),'Cherry')
