"""Licensed artist music shortlist. User choices always take precedence."""
import hashlib,re

def music_candidates(project, limit=6):
 from app.creative import licensed_music
 pool={k:v for k,v in licensed_music().items() if v.get('origin')=='artist_composed'}
 text=' '.join([project.get('source','')]+[m.get('content','') for m in project.get('messages',[]) if m.get('role')=='user']).lower()
 synonyms={'软件':['saas','app','系统','智能体','agent'],'餐饮':['餐厅','美食','烘焙'],'运动':['健身','体育'],'教育':['招生','学校','大学'],'科技':['ai','人工智能'],'物流':['货运','货代','海运'],'美妆':['护肤','香水'],'旅游':['景区','文旅'],'时尚':['服装','穿搭']}
 for tag,words in synonyms.items():
  if any(w in text for w in words):text+=' '+tag
 creative=(project.get('plan') or {}).get('creative') or {}
 energy=creative.get('energy','energetic' if project.get('pace')=='fast' else 'balanced')
 recent=project.get('creative_context',{}).get('recent_creatives',[])
 scored=[]
 for key,item in pool.items():
  hits=[t for t in item.get('tags',[]) if t.lower() in text]
  score=len(hits)*4+(2 if item.get('energy')==energy else 0)
  score-=sum(4 for t in item.get('avoid_tags',[]) if t in text)
  uses=sum(r.get('music')==key for r in recent[:5]);score-=uses*3
  if not hits and key=='wallpaper':score+=1
  seed=int(hashlib.sha256((project.get('id','')+key).encode()).hexdigest()[:8],16)
  scored.append((score,seed,{'id':key,'score':score,'category':item.get('category'),'matched_tags':hits,'recent_uses':uses,'energy':item.get('energy'),'bpm':item.get('bpm')}))
 return [s[2] for s in sorted(scored,key=lambda s:(-s[0],s[1]))[:limit]]

def select_music(project):
 from app.creative import licensed_music
 pool=licensed_music();explicit=(project.get('sound_preferences') or {}).get('music')
 if explicit in pool:return explicit,'用户指定曲目。'
 # A named song in chat is also a user choice, not merely a mood hint.
 messages=[m.get('content','') for m in project.get('messages',[]) if m.get('role')=='user'] or [project.get('source','')]
 for message in reversed(messages):
  if re.search(r'(配乐|音乐).{0,6}(自动|智能|重新匹配)',message):break
  for key,item in pool.items():
   title=item.get('title') or item.get('name','').split(' · ')[0]
   if not title:continue
   match=re.search(r'(?:使用|选用|换成|指定|采用|用|选|配乐|音乐).{0,15}'+re.escape(title),message,re.I)
   if match and not re.search(r'不要|不用|排除|别用',match.group()):return key,'用户在对话中指定曲目。'
 proposed=(project.get('plan') or {}).get('music');ranked=music_candidates(project,12)
 # Keep a suitable model choice; repair synthetic/default or heavily repeated mismatches.
 scores={row['id']:row['score'] for row in ranked}
 if ranked:
  best=ranked[0]
  chosen=proposed if proposed in scores and scores[proposed]>=best['score']-3 else best['id']
  row=next(r for r in ranked if r['id']==chosen);item=pool[chosen]
  return chosen,f"真实作品：{item['name']}；匹配{('、'.join(row['matched_tags']) or row['category'])}，{item.get('bpm')} BPM；结合情绪与近期用曲避免重复。发布时附带CC BY署名。"
 return (proposed if proposed in pool else 'pulse'),'当前使用已有可用曲库。'
