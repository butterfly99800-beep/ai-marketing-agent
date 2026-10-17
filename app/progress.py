from datetime import datetime,timezone
import math
from app import store

def update(p,stage,percent,estimated=None,completed=None,total=None):
 old=p.get('work',{});p['work']={'stage':stage,'percent':percent,'started_at':old.get('started_at',store.now()),'estimated_seconds':estimated or old.get('estimated_seconds',180),'completed':completed,'total':total};store.save(p)

def snapshot(p):
 work=dict(p.get('work') or {});status=p.get('status')
 if status=='completed':work.update(stage='已完成',percent=100,eta_min=0,eta_max=0)
 elif status in ('producing','planning','capturing'):
  if not work:work={'stage':'准备中','percent':0,'started_at':p.get('updated_at',store.now()),'estimated_seconds':180}
  try:elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(work['started_at'])).total_seconds()
  except (KeyError,ValueError):elapsed=0
  remaining=work.get('estimated_seconds',180)-elapsed
  if remaining>0:work.update(eta_min=max(1,math.ceil(remaining*.65/60)),eta_max=max(1,math.ceil(remaining*1.5/60)))
  else:work.update(eta_min=None,eta_max=None)
 return work

def estimate(p):
 shots=p['plan']['shots'];seconds=sum(s['duration'] for s in shots)
 return max(90,int(sum(12+(75 if s['source']=='image' else 1)+(150 if s.get('video') else 0) for s in shots)+seconds*(4 if p.get('bgm',True) else 2)))
