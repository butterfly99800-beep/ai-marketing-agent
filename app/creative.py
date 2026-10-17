"""Executable creative vocabulary shared with the director, not a fixed timeline."""
import hashlib
from collections import Counter

MUSIC = {
 'house_vibez': {'file':'house-vibez.mp3','bpm':123,'tags':['现代','产品','有节奏','服务'],'credit':'House Vibez — Lily J / Mixkit Stock Music Free License; https://assets.mixkit.co/music/745/745.mp3'},
 'cat_walk': {'file':'cat-walk.mp3','bpm':129,'tags':['时尚','活力','消费','快节奏'],'credit':'Cat Walk — Arulo / Mixkit Stock Music Free License; https://assets.mixkit.co/music/371/371.mp3'},
 'hiphop': {'file':'tonight-hiphop.mp3','bpm':103,'tags':['年轻','故事','城市','社交'],'credit':'Tonight — Michael Ramir C. / Mixkit Stock Music Free License; https://assets.mixkit.co/music/841/841.mp3'},
 'urban': {'file':'g-eazy-nba-type.mp3','bpm':86,'tags':['沉稳','工业','力量','慢节奏'],'credit':'G Eazy NBA type — Arulo / Mixkit Stock Music Free License; https://assets.mixkit.co/music/403/403.mp3'},
 'ambient': {'file':'music.wav','bpm':None,'tags':['安静','克制','专业','解说'],'credit':'Original code-generated instrumental bed.'},
 'cipher': {'file':'cipher.mp3','bpm':None,'tags':['电子','科技'],'credit':'"Cipher" Kevin MacLeod (incompetech.com). CC BY 4.0 https://creativecommons.org/licenses/by/4.0/ ; edited and mixed.'},
}
# Stock-library terms do not grant a blanket SaaS redistribution right.
for _key in ('house_vibez','cat_walk','hiphop','urban'):
 MUSIC[_key].update(enabled=False,license='Mixkit: requires review for SaaS library use',attribution_required=False)
MUSIC['ambient'].update(origin='procedural',category='程序合成备用',name='Ambient · 原创氛围',enabled=True,license='Project original',attribution_required=False)
MUSIC['cipher'].update(origin='artist_composed',category='科技电子',energy='balanced',name='Cipher · 电子科技',enabled=True,license='CC BY 4.0',attribution_required=True,source='https://incompetech.com/music/royalty-free/')
from app.config import ROOT
import json
if (ROOT/'assets/music-library.json').exists():MUSIC.update(json.loads((ROOT/'assets/music-library.json').read_text(encoding='utf8')))
def licensed_music():return {k:v for k,v in MUSIC.items() if v.get('enabled',True) and (ROOT/'renderer/public/audio'/v['file']).exists()}

PLATFORMS = {
 'douyin': {'name':'抖音','aspect':'9:16','form':['问题开场→场景证据→收益→行动','对比解释','清单解说'],'safe_top':.08,'safe_bottom':.18,'safe_right':.13,'trend_status':'常见形式，不是实时热门榜'},
 'shorts': {'name':'YouTube Shorts','aspect':'9:16','form':['单一问题快速解释','先结果后方法','短教程'],'safe_top':.08,'safe_bottom':.18,'safe_right':.13,'trend_status':'常见形式，不是实时热门榜'},
 'youtube': {'name':'YouTube','aspect':'16:9','form':['产品导览','问题→解决方案→证据','品牌叙事'],'safe_top':.06,'safe_bottom':.09,'safe_right':.06,'trend_status':'常见形式，不是实时热门榜'},
}
RECIPES = {
 'push':'单主角缓推，结尾停留；适合核心场景',
 'pull':'从细节拉回全貌；适合揭示场景或品牌',
 'pan':'横向探索宽幅场景；不裁掉重要主体',
 'orbit':'轻微侧向绕行→正视落定；只用于非密集画面',
 'focus':'大图静置并揭示聚焦框；用画框引导而非全屏震动',
 'rise':'从下方抬升揭示；适合空间、建筑和场景',
 'page_scroll':'真实网站截图纵向浏览；不让AI改写页面',
 'split':'左/上真实画面，右/下短主张；密集UI保持正视',
 'brand':'品牌收束，全片最多一次，落定至少1秒',
}

def recent_creatives(project):
 from app import store
 # Return only creative decisions, never other customers' source text or keys.
 result=[]
 for p in store.listing():
  if p['id']==project.get('id') or not p.get('plan'):continue
  plan=p['plan']
  result.append({'platform':p.get('platform'),'music':p.get('music',plan.get('music')),'strategy':plan.get('creative',{}).get('narrative'),'motions':[s.get('motion') for s in plan.get('shots',[])]})
  if len(result)==8:break
 return result

def director_context(project):
 return {'platform':dict(PLATFORMS.get(project.get('platform'),PLATFORMS['youtube']),aspect=project.get('aspect_ratio',PLATFORMS.get(project.get('platform'),PLATFORMS['youtube'])['aspect'])),
         'music_catalog':{k:{field:v[field] for field in ('name','category','bpm','tags','energy','avoid_tags','license','source','origin','instrumental','duration_seconds') if field in v} for k,v in licensed_music().items()},'music_recommendations':__import__('app.music_matching',fromlist=['music_candidates']).music_candidates(project),'voice_catalog':__import__('app.audio_catalog',fromlist=['voice_catalog']).voice_catalog(),'aspect_ratio':project.get('aspect_ratio','16:9'),'platforms':project.get('platforms',[]),'narration_enabled':project.get('narration_enabled',True),'pace':project.get('pace','fast'),'editing_skills':editing_skill_context(),'recipes':RECIPES,'recent_creatives':recent_creatives(project),
         'trend_policy':'只有附来源URL、日期、平台匹配的资料可称趋势参考；用户提供的参考也不等于已核验热门。没有证据时用平台常见形式。',
         'budget':{'image_first':True,'max_generated_images':6,'max_video_clips':2,'video_clip_seconds':5,'max_video_fraction':.4}}

def audit_plan(plan, project):
 shots=plan['shots'];warnings=[]
 counts=Counter(s['motion'] for s in shots if s['motion']!='brand')
 if counts and max(counts.values())>max(2,len(shots)//2):warnings.append('主要运镜重复较多，建议重排运动语法。')
 if project.get('mode')=='website' and len({s.get('screenshot_index') for s in shots if s['source']=='website'})<2:warnings.append('网站证据范围偏少，建议补充功能区块。')
 recent=project.get('creative_context',{}).get('recent_creatives',[])
 signature=[s['motion'] for s in shots]
 duplicate=any(r.get('motions')==signature and r.get('music')==plan.get('music') for r in recent)
 if duplicate:warnings.append('与近期作品的镜头顺序和配乐完全相同，请在对话中要求另一版。')
 return {'warnings':warnings,'matches_recent':duplicate,'image_count':sum(s['source']=='image' and s.get('asset_ref') is None for s in shots),
         'video_count':sum(bool(s.get('video')) for s in shots),'duration':sum(s['duration'] for s in shots),
         'music_credit':MUSIC[plan.get('music','ambient')]['credit'],
         'fingerprint':hashlib.sha256(str((signature,plan.get('music'),plan.get('creative'))).encode()).hexdigest()[:12]}

def editing_skill_context():
 path=ROOT/'skills/director-editing.json'
 return json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
