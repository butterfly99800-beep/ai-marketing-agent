import unittest,asyncio,json,tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
from app import store
from app.main import app,TASKS
from app.research import completion_with_tools,execute_tool

class ToolLoopTests(unittest.IsolatedAsyncioTestCase):
 async def test_real_function_result_is_returned_to_model(self):
  payloads=[]
  def handler(req):
   body=json.loads(req.content);payloads.append(body)
   msg={'role':'assistant','content':None,'reasoning_content':'tool reasoning','tool_calls':[{'id':'call_1','type':'function','function':{'name':'web_search','arguments':'{"query":"学校官网"}'}}]} if len(payloads)==1 else {'role':'assistant','content':'{"reply":"已搜索","ready":false,"plan":null}'}
   return httpx.Response(200,json={'choices':[{'message':msg}]})
  messages=[{'role':'user','content':'查官网'}]
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
   with patch('app.research.execute_tool',return_value={'results':[{'title':'官网','url':'https://example.edu'}]}) as execute:
    raw=await completion_with_tools(client,'test','test-model',messages,{'network_enabled':True})
  self.assertEqual(json.loads(raw)['reply'],'已搜索');self.assertIn('tools',payloads[0]);self.assertEqual(payloads[1]['messages'][-1]['role'],'tool');self.assertEqual(payloads[1]['messages'][-2]['reasoning_content'],'tool reasoning');execute.assert_awaited_once()
 async def test_disabled_network_does_not_advertise_tools(self):
  payloads=[]
  def handler(req):payloads.append(json.loads(req.content));return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'{}'}}]})
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:await completion_with_tools(client,'test','test',[],{'network_enabled':False})
  self.assertNotIn('tools',payloads[0])
 async def test_private_browser_address_rejected_before_launch(self):
  p={'id':'validation','network_enabled':True}
  with patch('app.research.save_project'),patch('app.research.run_browser') as launch:
   result=await execute_tool('browser_open',{'url':'http://127.0.0.1:8020'},p)
  self.assertIn('error',result);launch.assert_not_awaited()

class FirstMessageTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();folder=Path(self.tmp.name);self.patch=patch.multiple(store,DB=folder/'test.sqlite',DATA=folder);self.patch.start();store.initialize();self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8020',headers={'Origin':'http://localhost:8020'})
 async def asyncTearDown(self):
  for task in list(TASKS):task.cancel()
  if TASKS:await asyncio.gather(*list(TASKS),return_exceptions=True)
  await self.client.aclose();self.patch.stop();self.tmp.cleanup()
 async def test_original_first_request_persisted_before_and_after_reply(self):
  original='制作江苏科技大学招生宣传片，资料你从官网找。'
  with patch('app.deepseek.DeepSeekProvider.converse',return_value={'reply':'收到原始需求','ready':False,'plan':None}):
   r=await self.client.post('/api/projects',json={'mode':'text','source':original,'background':True})
   self.assertEqual(r.json()['messages'],[{'role':'user','content':original}]);pid=r.json()['id']
   if TASKS:await asyncio.gather(*list(TASKS))
  saved=store.get(pid);self.assertEqual(saved['messages'][0]['content'],original);self.assertEqual(len([m for m in saved['messages'] if m['role']=='user']),1)
 async def test_followup_is_immediately_visible_and_not_duplicated(self):
  p=store.create('text','第一条需求','youtube')
  with patch('app.deepseek.DeepSeekProvider.converse',return_value={'reply':'收到','ready':False,'plan':None}):
   r=await self.client.post(f"/api/projects/{p['id']}/conversations",json={'text':'换成温暖风格','network_enabled':False,'platform':'douyin'})
   self.assertEqual(r.json()['messages'][-1]['content'],'换成温暖风格')
   if TASKS:await asyncio.gather(*list(TASKS))
  saved=store.get(p['id']);self.assertEqual(len(saved['messages']),2);self.assertFalse(saved['network_enabled']);self.assertEqual(saved['platform'],'douyin')

if __name__=='__main__':unittest.main()
