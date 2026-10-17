"""Bounded retries for LLM requests only; never retries media or publishing."""
import asyncio,time
import httpx

class ResponseEnvelopeError(ValueError):pass

def failure_details(exc):
 text=str(exc).lower()
 kind='tls' if ('certificate' in text or 'ssl' in text) else 'dns' if ('getaddrinfo' in text or 'name resolution' in text) else 'connection'
 return {'type':type(exc).__name__,'category':kind}

async def completion_json(client,key,payload,p):
 for attempt in range(3):
  started=time.perf_counter()
  try:
   response=await client.post('https://api.deepseek.com/chat/completions',headers={'Authorization':'Bearer '+key},json=payload)
   response.raise_for_status()
   try:
    data=response.json();choices=data.get('choices') if isinstance(data,dict) else None
    if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict) or not isinstance(choices[0].get('message'),dict):raise ResponseEnvelopeError('missing message')
    message=choices[0]['message']
    if not isinstance(message.get('content'),str) and not message.get('tool_calls'):raise ResponseEnvelopeError('missing content')
   except (ValueError,TypeError) as exc:raise ResponseEnvelopeError('DeepSeek返回了无法解析的响应') from exc
   return data
  except (httpx.TransportError,httpx.HTTPStatusError,ResponseEnvelopeError) as exc:
   status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
   retryable=status in (408,429,500,502,503,504) if status else not isinstance(exc,(httpx.UnsupportedProtocol,httpx.LocalProtocolError))
   if not retryable:raise
   detail={'stage':'deepseek_transport','attempt':attempt+1,'elapsed_seconds':round(time.perf_counter()-started,2),'status':status,**failure_details(exc),'retrying':retryable and attempt<2}
   p.setdefault('diagnostics',[]).append(detail);p['diagnostics']=p['diagnostics'][-20:]
   if not retryable or attempt==2:raise
   delay=[1,3][attempt]
   if status==429:
    try:delay=min(8,max(delay,float(exc.response.headers.get('retry-after',delay))))
    except ValueError:pass
   p['llm_progress']={'phase':'retry','attempt':attempt+2,'delay_seconds':delay}
   await asyncio.sleep(delay)
