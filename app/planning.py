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


def require_dynamic_scene(plan,enabled):
 if enabled and not any(s.get('video') for s in plan.get('shots',[])):
  raise ValueError('用户已勾选AI动态画面，请安排至少1段5秒video=true的image镜头；最多2段且不超过总片长40%。截图不能伪造成AI视频。若仅真实网页的约束无法兼容，应说明冲突而不是静默返回纯静态方案。')
