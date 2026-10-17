"""Bounded, auditable web tools executed by the app, not fictitious model browsing."""
import asyncio,json,uuid
from datetime import datetime,timezone
from app.config import ROOT,DATA
from app.deepseek import ProviderError
from app.media import NODE,public_url,stop_owned

TOOLS=[
 {'type':'function','function':{'name':'web_search','description':'联网搜索公开资料。返回带URL的结果摘要；重要事实应继续browser_open查看原文。','parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'browser_open','description':'用独立浏览器打开公开URL，读取渲染后的正文和链接并截图。可沿返回链接继续浏览，不能登录或提交表单。','parameters':{'type':'object','properties':{'url':{'type':'string'},'tab':{'type':'string','maxLength':80},'scroll_y':{'type':'integer','minimum':0,'maximum':60000}},'required':['url'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'browser_read','description':'重新读取本项目最近打开的公开网页。不是用户个人浏览器的所有标签页。','parameters':{'type':'object','properties':{},'additionalProperties':False}}},
]

def save_project(p):
 from app import store
 if p.get('id'):
  try:store.save(p)
  except KeyError:pass

async def run_browser(p,action,**kwargs):
 if not p.get('network_enabled',True):raise ProviderError('本次对话已关闭联网')
 folder=DATA/p['id'];folder.mkdir(exist_ok=True,parents=True)
 token=uuid.uuid4().hex;request=folder/f'research-{token}.json';result_file=f'research-result-{token}.json'
 request.write_text(json.dumps(dict(action=action,id=token,result_file=result_file,**kwargs),ensure_ascii=False),encoding='utf-8')
 proc=await asyncio.create_subprocess_exec(NODE,str(ROOT/'renderer/research.cjs'),str(request),str(folder),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 try:
  await asyncio.wait_for(proc.communicate(),85)
  if proc.returncode:raise ProviderError('浏览器读取失败，页面可能限制访问或需要验证。')
  return json.loads((folder/result_file).read_text(encoding='utf-8'))
 except asyncio.TimeoutError:
  await stop_owned(proc);raise ProviderError('浏览器读取超时，请换一个公开页面或稍后再试。')
 except asyncio.CancelledError:
  await stop_owned(proc);raise
 finally:request.unlink(missing_ok=True)

async def execute_tool(name,args,p):
 if not p.get('network_enabled',True):return {'error':'本次对话已关闭联网'}
 if name not in ('web_search','browser_open','browser_read'):return {'error':'不支持的工具'}
 log=p.setdefault('research',{}).setdefault('actions',[])
 entry={'tool':name,'status':'running','started_at':datetime.now(timezone.utc).isoformat()}
 if name=='web_search':entry['query']=str(args.get('query',''))[:300]
 else:entry['url']=args.get('url') or p.get('browser',{}).get('url')
 log.append(entry);p['research']['actions']=log[-30:];save_project(p)
 try:
  if name=='web_search':
   from app.web_fetch import search,relevant
   query=str(args.get('query',''))[:300]
   result=await search(query)
   if not result.get('results'):
    try:
     browser=await run_browser(p,'search',query=query)
     browser['results']=[r for r in browser.get('results',[]) if relevant(query,r.get('title',''),r.get('snippet',''))]
     if browser['results']:result=browser
    except ProviderError:pass
   p['research']['search_results']=result.get('results',[])
  else:
   url=entry['url']
   if not url:raise ProviderError('还没有打开网页，请先提供URL或搜索')
   await asyncio.to_thread(public_url,url)
   try:result=await run_browser(p,'open',url=url,scroll_y=int(args.get('scroll_y',0)),tab=str(args.get('tab',''))[:80])
   except ProviderError:
    from app.web_fetch import fetch_page
    try:result,_=await fetch_page(url)
    except Exception as exc:raise ProviderError('网页连接失败：'+type(exc).__name__+'，请检查官网地址、代理或网站访问状态。') from exc
   pages=p['research'].setdefault('pages',[]);pages[:]=[a for a in pages if a['url']!=result['url']];pages.append(result);p['research']['pages']=pages[-8:]
   p['browser']={k:result.get(k) for k in ('url','title','file','fetched_at','scroll_y')}
   # Browser screenshots can become real production assets, with the same indices the director sees.
   site=p.get('site') or {'pages':[]};p['site']=site;site.setdefault('pages',[])
   index=next((i for i,a in enumerate(site['pages']) if a.get('url')==result['url'] and a.get('scroll_y',0)==result.get('scroll_y',0) and a.get('state',{}).get('selected_tab')==result.get('state',{}).get('selected_tab') and a.get('kind')=='browser'),None)
   if result.get('file') and index is None and len(site['pages'])<12:index=len(site['pages']);site['pages'].append({})
   if result.get('file') and index is not None:
    site['pages'][index]={k:result.get(k) for k in ('url','title','text','file','scroll_y','state','regions','pageH')};site['pages'][index]['kind']='browser';result['screenshot_index']=index
   for view in result.get('views',[]):
    found=next((i for i,a in enumerate(site['pages']) if a.get('url')==view.get('url') and a.get('scroll_y',0)==view.get('scroll_y',0) and a.get('state',{}).get('selected_tab')==view.get('state',{}).get('selected_tab')),None)
    if found is None and len(site['pages'])<12:
     found=len(site['pages']);site['pages'].append(dict(view,kind='browser'))
    if found is not None:view['screenshot_index']=found
   site.setdefault('design_tokens',result.get('design_tokens',{}))
  entry['status']='failed' if result.get('error') else 'done';entry['summary']=result.get('title') or f"找到{len(result.get('results',[]))}条结果"
  save_project(p)
  return result
 except (ProviderError,ValueError,TypeError) as exc:
  entry['status']='failed';entry['error']=str(exc);save_project(p);return {'error':str(exc),'tool':name}

async def completion_with_tools(client,key,model,messages,p,allow_tools=True):
 enabled=p.get('network_enabled',True) and allow_tools;used=0;cache={}
 import time
 metrics=p.setdefault('llm_metrics',[])
 for turn in range(7):
  planning=bool(p.get('clarification_done') or p.get('site') or p.get('research',{}).get('pages'))
  payload={'model':model,'messages':messages,'response_format':{'type':'json_object'},'max_tokens':16000,'thinking':{'type':'enabled' if planning else 'disabled'}}
  if planning:payload['reasoning_effort']='low'
  if enabled and turn<6 and used<8:payload['tools']=TOOLS
  p['llm_progress']={'phase':'model','round':turn+1,'started_at':datetime.now(timezone.utc).isoformat()};save_project(p)
  started=time.perf_counter()
  from app.deepseek_transport import completion_json
  data=await completion_json(client,key,payload,p);choice=data['choices'][0];message=choice['message'];calls=message.get('tool_calls') or []
  usage=data.get('usage',{})
  metrics.append({'stage':'deepseek_request','round':turn+1,'elapsed_seconds':round(time.perf_counter()-started,3),'thinking':'low' if planning else 'disabled','input_chars':sum(len(str(m.get('content') or '')) for m in messages),'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),'reasoning_tokens':usage.get('completion_tokens_details',{}).get('reasoning_tokens'),'tool_calls':len(calls),'finish_reason':choice.get('finish_reason')});p['llm_metrics']=metrics[-30:]
  if not calls:
   p['llm_progress']={'phase':'done','round':turn+1};save_project(p)
   return message.get('content') or '{}'
  messages.append({k:v for k,v in message.items() if k in ('role','content','tool_calls','reasoning_content')})
  p['llm_progress']={'phase':'tools','round':turn+1};save_project(p)
  for call in calls:
   if used>=8:result={'error':'本轮联网工具已达8次上限，请基于已读资料回答，或请用户继续。'}
   else:
    used+=1;started=time.perf_counter();cached=False
    try:
     args=json.loads(call['function']['arguments']);name=call['function']['name'];cache_key=name+json.dumps(args,sort_keys=True,ensure_ascii=False)
     if name!='browser_read' and cache_key in cache:result=cache[cache_key];cached=True
     else:
      result=await execute_tool(name,args,p)
      if name!='browser_read' and not result.get('error'):cache[cache_key]=result
     metrics.append({'stage':'web_tool','tool':name,'elapsed_seconds':round(time.perf_counter()-started,3),'cache_hit':cached});p['llm_metrics']=metrics[-30:]
    except (ValueError,KeyError,TypeError):result={'error':'工具参数无效'}
   messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
 raise ProviderError('联网检索轮次已达上限，资料已保留，请继续对话。')
