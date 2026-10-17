import json,httpx,re,time
from pathlib import Path
from app.config import CONFIG,MODEL,ROOT
from app.schemas import DirectorReply
class ProviderError(Exception):pass
class DeepSeekProvider:
 async def converse(self,p):
  key=CONFIG.get('DEEPSEEK_API_KEY')
  if not key:raise ProviderError('DeepSeek密钥未配置')
  prompt=(ROOT/'prompts/director.txt').read_text(encoding='utf-8-sig')
  context={k:p.get(k) for k in ['mode','source','platform','messages','site','research','network_enabled','video_budget','sound_preferences','target_duration','creative_context','attachments','clarification_done','platforms','aspect_ratio','narration_enabled','pace']}
  # Do not send identical source text twice or duplicate screenshot text in research.
  context['messages']=[m for m in (context.get('messages') or []) if not(m.get('role')=='user' and m.get('content')==p.get('source'))]
  site=p.get('site') or {}
  context['site']={k:v for k,v in site.items() if k!='pages'}
  context['site']['pages']=[{k:v for k,v in page.items() if k in ('url','title','label','kind','text','file','scroll_y','state','regions','pageH')} for page in site.get('pages',[])]
  seen={page.get('url') for page in site.get('pages',[]) if page.get('text')}
  research=p.get('research') or {}
  context['research']={'search_results':research.get('search_results',[]),'pages':[{k:v for k,v in page.items() if k in ('url','title','text') and not(k=='text' and page.get('url') in seen)} for page in research.get('pages',[])]}
  context['output_schema']=DirectorReply.model_json_schema()
  context['default_direction']='先用questions给最多3个补充问题，每题2–3选项且首项推荐。clarification_done=true后不再问可选问题，只返回一个最终方案，等待用户点击开始生成。'
  context['capabilities']={'web_search':p.get('network_enabled',True),'browser_open':p.get('network_enabled',True),'browser_read':'本项目独立浏览器最近页面；不读取个人浏览器所有标签页'}
  messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(context,ensure_ascii=False)}]
  async with httpx.AsyncClient(timeout=httpx.Timeout(180,connect=20)) as client:
   for attempt in range(3):
    try:
     from app.research import completion_with_tools
     raw=await completion_with_tools(client,key,MODEL,messages,p,allow_tools=attempt==0)
    except httpx.HTTPStatusError as exc:
     status=exc.response.status_code;p.setdefault('diagnostics',[]).append({'stage':'deepseek_http','status':status,'model':MODEL});
     reason={401:'API密钥无效',402:'余额不足',403:'模型权限不足',429:'请求限流',500:'服务商内部错误',503:'服务暂不可用'}.get(status,'服务商返回异常')
     raise ProviderError(f'DeepSeek接口HTTP {status}：{reason}，需求已保留。') from exc
    except httpx.TimeoutException as exc:
     p.setdefault('diagnostics',[]).append({'stage':'deepseek_timeout','model':MODEL});raise ProviderError('DeepSeek响应超时，需求已保留，可继续重试。') from exc
    except httpx.TransportError as exc:
     from app.deepseek_transport import failure_details
     detail=failure_details(exc);p.setdefault('diagnostics',[]).append({'stage':'deepseek_connection',**detail,'model':MODEL})
     reason={'tls':'TLS证书连接失败','dns':'域名解析失败','connection':'连接建立或传输失败'}[detail['category']]
     raise ProviderError('DeepSeek'+reason+'，已尝试3次；需求已保留，稍后可继续。') from exc
    except (httpx.HTTPError,KeyError,ValueError) as exc:
     p.setdefault('diagnostics',[]).append({'stage':'deepseek_response','type':type(exc).__name__,'model':MODEL});raise ProviderError('DeepSeek返回的响应格式无效，需求已保留。') from exc
    try:
     reply=DirectorReply.model_validate_json(raw)
     if reply.ready and reply.questions:raise ValueError('最终方案不能同时包含补充问题')
     if p.get('clarification_done') and reply.questions:raise ValueError('用户已补充或跳过，不再提问，返回单一完整方案')
     if reply.ready and reply.plan and p.get('production_version',0)>=3 and p.get('narration_enabled',True) and not reply.plan.narration_beats:raise ValueError('有配音的新方案必须给narration_beats，以完整句子绑定镜头，不能独立编排旁白和画面')
     if reply.ready and reply.plan is None:raise ValueError('ready=true必须包含plan')
     if reply.plan and reply.plan.creative is None:raise ValueError('方案缺少可执行creative导演方向')
     if reply.plan and p.get('target_duration'):
      from app.planning import fit_duration
      try:reply.plan=type(reply.plan).model_validate(fit_duration(reply.plan.model_dump(),p['target_duration']))
      except ProviderError as exc:raise ValueError(str(exc)) from exc
     if reply.plan:
      from app.creative import audit_plan
      audit=audit_plan(reply.plan.model_dump(),p)
      explicit_repeat=any(re.search(r'沿用上一|保持上一|和上一.*一样|复用同一',m.get('content','')) for m in p.get('messages',[])[-2:] if m.get('role')=='user')
      if audit['matches_recent'] and not explicit_repeat:raise ValueError('与近期镜头顺序和配乐完全重复，请按当前内容重新策划；用户指定项保持')
     if reply.plan:
      web_shots=[s for s in reply.plan.shots if s.source=='website']
      available=len((p.get('site') or {}).get('pages',[]))
      if available>=3 and len(web_shots)>=3 and len({s.screenshot_index for s in web_shots})<3:raise ValueError('已抓到多个网站画面，请按内容匹配至少3个不同的截图索引，不能整片重复首屏')
      if p['mode']=='website' and sum(s.source=='image' and s.asset_ref is None for s in reply.plan.shots)>1:raise ValueError('网站方案最多使用一张概念图片，请以真实截图为主。')
      evidence_text='\n'.join(a.get('text','') for a in p.get('attachments',[]))+'\n'+p['source']+'\n'+'\n'.join(page.get('text','') for page in (p.get('site') or {}).get('pages',[]))+'\n'+'\n'.join(page.get('text','') for page in (p.get('research') or {}).get('pages',[]))+'\n'+'\n'.join(m['content'] for m in p['messages'] if m['role']=='user')
      for shot in reply.plan.shots:
       if any(q not in evidence_text for q in shot.evidence):raise ValueError('分镜事实依据未通过原文校验，请让Agent重新规划。')
       if shot.layout=='workflow' and any(label not in evidence_text for label in shot.graphic_labels):raise ValueError('流程标签须来自用户资料，不能编造服务。')
       if shot.source=='website' and shot.screenshot_index>=len((p.get('site') or {}).get('pages',[])):raise ValueError('分镜引用了不存在的网站截图。')
       if shot.video and not p.get('video_budget'):raise ValueError('当前未开启短视频预算，不能调用视频模型。')
     break
    except ValueError as exc:
     issues=exc.errors(include_url=False,include_input=False,include_context=False) if hasattr(exc,'errors') else [{'msg':str(exc)[:500]}]
     p.setdefault('diagnostics',[]).append({'stage':'plan_validation','attempt':attempt+1,'issues':issues});p['diagnostics']=p['diagnostics'][-12:]
     if attempt==2:raise ProviderError('DeepSeek已响应，但方案自动修复3次仍未通过：'+str(issues[0].get('msg','格式错误'))[:180]+'。需求已保留，无需精简资料。') from exc
     # Only repair generated JSON; never retry ambiguous paid media submissions.
     # Keep one current repair candidate, not every invalid full storyboard.
     evidence={'site':context.get('site'),'research':context.get('research')}
     # Tool-read facts remain available even when the tool loop is disabled for repairs.
     evidence['site']={'pages':[{k:v for k,v in page.items() if k in ('url','title','text','file')} for page in (p.get('site') or {}).get('pages',[])]}
     evidence['research']={'pages':[{k:v for k,v in page.items() if k in ('url','title','text')} for page in (p.get('research') or {}).get('pages',[]) if page.get('url') not in {a.get('url') for a in evidence['site']['pages']}]}
     messages=messages[:2]+[{'role':'user','content':'仅修复方案，复用以下已读资料，不重新联网：'+json.dumps(evidence,ensure_ascii=False)},{'role':'assistant','content':raw},{'role':'user','content':'修复JSON方案并完整返回，不改变用户事实。校验问题：'+str(exc)[:1600]}]
  return reply.model_dump()
