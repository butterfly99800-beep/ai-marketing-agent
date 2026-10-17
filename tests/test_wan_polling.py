import unittest,httpx
from unittest.mock import patch,AsyncMock
from app.wan import WanProvider

class WanPollingTests(unittest.IsolatedAsyncioTestCase):
 async def test_poll_reports_wait_and_recovers_without_submission(self):
  original=httpx.AsyncClient;calls=[];progress=[]
  def handler(req):
   calls.append(req)
   if len(calls)==1:raise httpx.ConnectError('temporary',request=req)
   return httpx.Response(200,json={'output':{'task_status':'RUNNING' if len(calls)==2 else 'SUCCEEDED','results':[{'url':'https://example.org/a.png'}]}})
  w=WanProvider();w.on_poll=lambda status,elapsed:progress.append(status)
  with patch('app.wan.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)),patch('app.wan.asyncio.sleep',new=AsyncMock()):result=await w.result('existing-task')
  self.assertEqual(result,'https://example.org/a.png');self.assertEqual(progress,['查询连接重试','生成中','已生成']);self.assertTrue(all(r.method=='GET' for r in calls))
 async def test_permanent_poll_connection_failure_is_bounded(self):
  from app.deepseek import ProviderError
  original=httpx.AsyncClient;calls=[]
  def handler(req):calls.append(req);raise httpx.ConnectError('temporary',request=req)
  with patch('app.wan.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)),patch('app.wan.asyncio.sleep',new=AsyncMock()):
   with self.assertRaisesRegex(ProviderError,'连续3次'):await WanProvider().result('existing-task')
  self.assertEqual(len(calls),3)
