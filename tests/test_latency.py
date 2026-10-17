import unittest,json,httpx
from unittest.mock import patch
from app.research import completion_with_tools
from app.deepseek import DeepSeekProvider
from test_creative import plan

class LatencyTests(unittest.IsolatedAsyncioTestCase):
 async def test_identical_reads_are_cached_and_timed(self):
  requests=[]
  def handler(req):
   requests.append(json.loads(req.content));msg={'role':'assistant','tool_calls':[{'id':str(i),'type':'function','function':{'name':'browser_open','arguments':'{"url":"https://example.com"}'}} for i in range(2)]} if len(requests)==1 else {'role':'assistant','content':'{}'}
   return httpx.Response(200,json={'choices':[{'message':msg}],'usage':{'completion_tokens':3}})
  p={'network_enabled':True}
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
   with patch('app.research.execute_tool',return_value={'title':'官网','text':'正文'} ) as tool:
    await completion_with_tools(client,'test','deepseek-flash',[],p)
  self.assertEqual(tool.await_count,1);self.assertEqual([m['cache_hit'] for m in p['llm_metrics'] if m['stage']=='web_tool'],[False,True]);self.assertEqual(p['llm_progress']['phase'],'done')
 async def test_repairs_do_not_search_again_and_keep_newly_read_evidence(self):
  original=httpx.AsyncClient;requests=[];proposal=plan();proposal['shots'][0]['evidence']=['原文中的新证据']
  p={'mode':'text','source':'企业资料','messages':[],'network_enabled':True,'clarification_done':True}
  def handler(req):
   requests.append(json.loads(req.content))
   if len(requests)==1:msg={'role':'assistant','tool_calls':[{'id':'lookup','type':'function','function':{'name':'browser_open','arguments':'{"url":"https://example.com"}'}}]}
   else:msg={'role':'assistant','content':'invalid' if len(requests)==2 else json.dumps({'reply':'方案','ready':True,'plan':proposal})}
   return httpx.Response(200,json={'choices':[{'message':msg}]})
  async def tool(name,args,project):
   page={'url':'https://example.com','title':'资料','text':'原文中的新证据'};project['research']={'pages':[page]};return page
  with patch('app.deepseek.CONFIG',{'DEEPSEEK_API_KEY':'test'}),patch('app.deepseek.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)),patch('app.research.execute_tool',side_effect=tool) as called:
   result=await DeepSeekProvider().converse(p)
  self.assertTrue(result['ready']);self.assertEqual(called.await_count,1);self.assertNotIn('tools',requests[-1]);self.assertIn('原文中的新证据',str(requests[-1]));self.assertEqual(requests[-1]['reasoning_effort'],'low')
 async def test_context_keeps_one_copy_of_same_source_and_page(self):
  original=httpx.AsyncClient;requests=[]
  def handler(req):requests.append(json.loads(req.content));return httpx.Response(200,json={'choices':[{'message':{'content':'{"reply":"收到","ready":false,"plan":null}'}}]})
  p={'mode':'text','source':'唯一的原始要求','messages':[{'role':'user','content':'唯一的原始要求'}],'site':{'pages':[{'url':'https://example.com','text':'唯一的官网正文','file':'site0.png'}]},'research':{'pages':[{'url':'https://example.com','text':'唯一的官网正文'}]}}
  with patch('app.deepseek.CONFIG',{'DEEPSEEK_API_KEY':'test'}),patch('app.deepseek.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
   await DeepSeekProvider().converse(p)
  content=requests[0]['messages'][1]['content'];self.assertEqual(content.count('唯一的原始要求'),1);self.assertEqual(content.count('唯一的官网正文'),1)

if __name__=='__main__':unittest.main()
