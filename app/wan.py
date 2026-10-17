import asyncio,base64,httpx,time
from app.config import CONFIG,WAN_BASE,IMAGE_MODEL,VIDEO_MODEL
from app.deepseek import ProviderError

class SubmissionError(ProviderError):
 def __init__(self,message,definitive=False,code=None,status=None):
  super().__init__(message);self.definitive=definitive;self.code=code;self.status=status

def provider_error(data,status):
 code=str(data.get('code','Unknown'))[:90]
 reasons={'InvalidApiKey':'API密钥无效或地域不匹配','InvalidParameter':'请求参数不合法','DataInspectionFailed':'提示词未通过内容审核','IPInfringementSuspect':'提示词可能涉及受保护内容','AccessDenied':'没有该模型权限','Arrearage':'账号欠费或额度不足','Throttling':'请求限流'}
 reason=reasons.get(code,'服务商拒绝本次请求')
 detail=str(data.get('message',''))[:240]
 import re
 detail=re.sub(r'sk-[\w-]+','[已隐藏]',detail)
 return SubmissionError(f'万相提交被拒绝（HTTP {status} / {code}）：{reason}。{detail}',400<=status<500,code,status)

class WanProvider:
 def __init__(self):self.on_poll=None;self.headers={'Authorization':'Bearer '+CONFIG.get('DASHSCOPE_API_KEY',''),'X-DashScope-Async':'enable'}
 async def submit(self,prompt,vertical=False,image=None):
  if not CONFIG.get('DASHSCOPE_API_KEY'):raise SubmissionError('万相密钥未配置',True)
  if image:
   body={'model':VIDEO_MODEL,'input':{'prompt':prompt,'img_url':'data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()},'parameters':{'resolution':'720P','duration':5,'prompt_extend':False}};endpoint='/api/v1/services/aigc/video-generation/video-synthesis'
  else:
   body={'model':IMAGE_MODEL,'input':{'prompt':prompt,'negative_prompt':'文字，水印，商标，畸形，低清晰度'},'parameters':{'size':'720*1280' if vertical else '1280*720','n':1,'prompt_extend':False}};endpoint='/api/v1/services/aigc/text2image/image-synthesis'
  try:
   async with httpx.AsyncClient(timeout=httpx.Timeout(75,connect=20)) as c:r=await c.post(WAN_BASE+endpoint,headers=self.headers,json=body)
  except httpx.TimeoutException as exc:raise SubmissionError('万相提交连接超时，结果尚未确认；已保留记录，不自动重复扣费。') from exc
  except httpx.HTTPError as exc:raise SubmissionError('万相提交网络连接中断，结果尚未确认；请检查代理或网络连接。') from exc
  try:data=r.json()
  except ValueError:raise SubmissionError(f'万相返回异常格式（HTTP {r.status_code}），提交结果尚未确认。')
  if r.is_error or data.get('code'):raise provider_error(data,r.status_code)
  task=data.get('output',{}).get('task_id')
  if not task:raise SubmissionError('万相未返回任务编号，已停止自动重复提交。')
  return task
 async def result(self,task_id):
  started=time.monotonic();failures=0
  async with httpx.AsyncClient(timeout=httpx.Timeout(30,connect=10)) as c:
   for _ in range(180):
    try:
     r=await c.get(WAN_BASE+'/api/v1/tasks/'+task_id,headers=self.headers);r.raise_for_status();o=r.json()['output'];failures=0
    except (httpx.HTTPError,KeyError,ValueError) as exc:
     failures+=1
     if self.on_poll:self.on_poll('查询连接重试',int(time.monotonic()-started))
     if failures>=3:raise ProviderError('万相任务查询连续3次失败，任务编号已保留；继续时只查询，不重复提交。') from exc
     await asyncio.sleep(min(8,failures*2));continue
    status=o.get('task_status','UNKNOWN')
    if self.on_poll:self.on_poll({'PENDING':'排队中','RUNNING':'生成中','SUCCEEDED':'已生成'}.get(status,status),int(time.monotonic()-started))
    if status=='SUCCEEDED':return o.get('video_url') or o['results'][0]['url']
    if status in ('FAILED','CANCELED','UNKNOWN'):raise ProviderError('万相任务未成功：'+str(o.get('code','FAILED'))[:80])
    await asyncio.sleep(4)
  raise ProviderError('万相任务超时，任务编号已保留；继续时只查询，不重复提交。')
