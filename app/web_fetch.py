"""Read-only public HTTP fallback, relevance checked search, no cookies or login."""
import asyncio,re,base64
from urllib.parse import urljoin,urlsplit,parse_qs,unquote
from datetime import datetime,timezone
import httpx
from bs4 import BeautifulSoup
from app.deepseek import ProviderError

async def fetch_page(url,limit=3*1024*1024):
 from app.media import public_url
 async with httpx.AsyncClient(timeout=httpx.Timeout(18,connect=8),follow_redirects=False,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'zh-CN,zh;q=0.9,en;q=0.7'}) as c:
  for _ in range(5):
   await asyncio.to_thread(public_url,url)
   async with c.stream('GET',url) as r:
    if r.is_redirect:url=urljoin(url,r.headers.get('location',''));continue
    r.raise_for_status();data=bytearray()
    if not any(x in r.headers.get('content-type','text/html') for x in ('text/','html','xml')):raise ProviderError('该链接不是可读取的网页正文')
    async for block in r.aiter_bytes():
     data.extend(block)
     if len(data)>limit:raise ProviderError('网页超过读取大小限制')
    soup=BeautifulSoup(bytes(data),'html.parser');title=soup.title.get_text(' ',strip=True) if soup.title else urlsplit(url).hostname
    links=[{'title':a.get_text(' ',strip=True)[:100],'url':urljoin(url,a.get('href',''))} for a in soup.select('a[href]') if a.get_text(strip=True)]
    for tag in soup.select('script,style,noscript,svg'):tag.decompose()
    return {'url':url,'title':title,'text':soup.get_text(' ',strip=True)[:18000],'links':[a for a in links if a['url'].startswith(('https://','http://'))][:80],'fetched_at':datetime.now(timezone.utc).isoformat(),'reader':'http','notice':'已读取公开网页原文，未登录、未提交表单；浏览器截图不可用。'},soup
 raise ProviderError('网页重定向次数过多')

def relevant(query,title,snippet):
 text=(title+' '+snippet).lower();q=query.lower()
 entities=re.findall(r'[\u4e00-\u9fff]{2,14}?(?:大学|公司|集团)',q)
 if entities and not any(e in text for e in entities):return False
 words=re.findall(r'[a-z0-9]{2,}',q)
 chinese=''.join(re.findall(r'[\u4e00-\u9fff]',q));pairs={chinese[i:i+2] for i in range(len(chinese)-1)}
 return any(w in text for w in words) or (sum(p in text for p in pairs)>=min(3,len(pairs)) if pairs else False)

def clean_link(raw):
 try:
  u=urlsplit(raw);params=parse_qs(u.query)
  if 'duckduckgo.com' in u.hostname and params.get('uddg'):return params['uddg'][0]
  if u.hostname.endswith('bing.com') and params.get('u'):
   code=params['u'][0]
   if code.startswith('a1'):return base64.urlsafe_b64decode(code[2:]+'===').decode()
 except Exception:pass
 return raw

async def search(query):
 engines=[('bing','https://www.bing.com/search',{'q':query,'setlang':'zh-Hans','cc':'cn'},'li.b_algo','h2 a'),('baidu','https://www.baidu.com/s',{'wd':query},'div.result,div.c-container','h3 a'),('sogou','https://www.sogou.com/web',{'query':query},'.vrwrap,.rb','h3 a'),('duckduckgo','https://html.duckduckgo.com/html/',{'q':query},'.result','a.result__a')]
 diagnostics=[]
 for name,base,params,selector,anchor in engines:
  url=str(httpx.URL(base,params=params))
  try:
   _,soup=await fetch_page(url);results=[]
   for node in soup.select(selector):
    a=node.select_one(anchor)
    if not a:continue
    title=a.get_text(' ',strip=True);snippet=node.get_text(' ',strip=True)[:1200];link=clean_link(urljoin(base,a.get('href','')))
    if link.startswith(('http://','https://')) and relevant(query,title,snippet):results.append({'title':title,'url':link,'snippet':snippet})
   diagnostics.append({'engine':name,'relevant_results':len(results)})
   if results:return {'query':query,'engine':name,'results':results[:8],'fetched_at':datetime.now(timezone.utc).isoformat(),'diagnostics':diagnostics}
  except Exception as e:diagnostics.append({'engine':name,'error':type(e).__name__})
 return {'query':query,'results':[],'error':'各搜索源未返回与问题相关的结果，不能把无关结果当作已找到资料。','diagnostics':diagnostics}
