import unittest,json,httpx
from unittest.mock import patch,AsyncMock
from app.deepseek_transport import completion_json,ResponseEnvelopeError

class ConnectionRetryTests(unittest.IsolatedAsyncioTestCase):
 async def test_connect_failure_recovers(self):
  calls=[];p={}
  def handler(req):
   calls.append(req)
   if len(calls)<3:raise httpx.ConnectError('connection failed',request=req)
   return httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]})
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
   with patch('app.deepseek_transport.asyncio.sleep',new=AsyncMock()):data=await completion_json(c,'test',{},p)
  self.assertEqual(len(calls),3);self.assertEqual(data['choices'][0]['message']['content'],'{}');self.assertTrue(p['diagnostics'][0]['retrying'])
 async def test_auth_failure_is_not_retried(self):
  calls=[]
  def handler(req):calls.append(req);return httpx.Response(401,json={'error':'invalid'})
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
   with self.assertRaises(httpx.HTTPStatusError):await completion_json(c,'test',{}, {})
  self.assertEqual(len(calls),1)
 async def test_broken_response_is_bounded(self):
  calls=[]
  def handler(req):calls.append(req);return httpx.Response(200,text='')
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
   with patch('app.deepseek_transport.asyncio.sleep',new=AsyncMock()),self.assertRaises(ResponseEnvelopeError):await completion_json(c,'test',{}, {})
  self.assertEqual(len(calls),3)
 async def test_retry_does_not_repeat_completed_web_tools(self):
  from app.research import completion_with_tools
  requests=[]
  def handler(req):
   requests.append(req)
   if len(requests)==1:return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'one','type':'function','function':{'name':'web_search','arguments':'{"query":"test"}'}}]}}]})
   if len(requests)==2:raise httpx.ConnectError('connection failed',request=req)
   return httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]})
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
   with patch('app.deepseek_transport.asyncio.sleep',new=AsyncMock()),patch('app.research.execute_tool',new=AsyncMock(return_value={'results':[]})) as tool:
    await completion_with_tools(c,'test','model',[],{})
    self.assertEqual(tool.await_count,1)
  self.assertEqual(len(requests),3)
