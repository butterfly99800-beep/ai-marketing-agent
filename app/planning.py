from copy import deepcopy
from app.schemas import Plan
from app.deepseek import ProviderError

def fit_duration(plan,seconds):
 result=deepcopy(plan);result['shots']=[deepcopy(shot) for shot in plan['shots']];shots=result['shots'];delta=seconds-sum(s['duration'] for s in shots)
 while delta:
  candidates=[s for s in shots if not s.get('video') and (s['duration']<10 if delta>0 else s['duration']>2)]
  if not candidates:raise ProviderError('当前镜头数量无法满足所选时长，请让导演重新规划镜头。')
  shot=min(candidates,key=lambda s:s['duration']) if delta>0 else max(candidates,key=lambda s:s['duration'])
  step=1 if delta>0 else -1;shot['duration']+=step;delta-=step
 return Plan.model_validate(result).model_dump()
