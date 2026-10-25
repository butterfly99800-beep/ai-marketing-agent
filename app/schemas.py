from typing import Literal,Annotated
from pydantic import BaseModel,Field,ConfigDict,model_validator
from app.audio_catalog import VOICE_PROFILES
from app.creative import MUSIC
VoiceId=Literal[tuple(VOICE_PROFILES)]
MusicId=Literal[tuple(MUSIC)]
PlatformId=Literal['douyin','youtube','shorts','xiaohongshu','bilibili','instagram']
class Shot(BaseModel):
 model_config=ConfigDict(extra='forbid')
 title:str=Field(min_length=1,max_length=32)
 show_title:bool=True
 narration:str=Field(min_length=1,max_length=64)
 image_prompt:str=Field(min_length=1,max_length=1800)
 video_prompt:str|None=Field(default=None,max_length=1200)
 duration:int=Field(ge=2,le=10)
 asset_ref:int|None=Field(default=None,ge=0,le=29)
 scene:Literal['page_reveal','detail_track','row_embed','section_wipe','parallel_compare','brand_recall']|None=None
 region_index:int|None=Field(default=None,ge=0,le=40)
 composition:Literal['full_bleed','editorial','split','spotlight','collage']='full_bleed'
 motion:Literal['push','pull','pan','orbit','focus','rise','page_scroll','split','brand']='push'
 source:Literal['image','website','graphic']='image'
 layout:Literal['auto','workflow']='auto'
 graphic_labels:list[str]=Field(default_factory=list,max_length=4)
 screenshot_index:int=Field(default=0,ge=0,le=11)
 purpose:str=Field(default='',max_length=250)
 transition:Literal['auto','cut','push','panel','dissolve','iris']='auto'
 focal_x:float=Field(default=.5,ge=.1,le=.9)
 focal_y:float=Field(default=.5,ge=.1,le=.9)
 hold_seconds:float=Field(default=1,ge=.5,le=2)
 video:bool=False
 @model_validator(mode='before')
 @classmethod
 def image_has_no_screenshot(cls,data):
  if isinstance(data,dict) and data.get('source') in ('image','graphic') and data.get('screenshot_index') is None:data=dict(data,screenshot_index=0)
  return data
 evidence:list[str]=Field(default_factory=list,max_length=5)
class CreativeDirection(BaseModel):
 model_config=ConfigDict(extra='forbid')
 narrative:Literal['problem_solution','feature_tour','brand_story','comparison','editorial']='feature_tour'
 energy:Literal['calm','balanced','energetic']='balanced'
 image_style:Literal['photographic','editorial','illustration','3d','minimal']='photographic'
 background:str=Field(default='#071724',pattern=r'^#[0-9a-fA-F]{6}$')
 foreground:str=Field(default='#f6fafc',pattern=r'^#[0-9a-fA-F]{6}$')
 accent:str=Field(default='#62c6c9',pattern=r'^#[0-9a-fA-F]{6}$')
 music_reason:str=Field(default='',max_length=400)
 hook:str=Field(default='',max_length=200)
 visual_consistency:str=Field(default='',max_length=500)
 trend_basis:str=Field(default='平台常见形式，未核验实时热门',max_length=500)
 @model_validator(mode='after')
 def legible_palette(self):
  def luminance(value):
   rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
   linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
   return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
  a,b=sorted((luminance(self.background),luminance(self.foreground)))
  if (b+.05)/(a+.05)<4.5:raise ValueError('前景与背景对比不足，请选择可读色板')
  return self

class NarrationBeat(BaseModel):
 model_config=ConfigDict(extra='forbid')
 text:str=Field(min_length=1,max_length=80)
 shot_indices:list[int]=Field(min_length=1,max_length=3)
 pause_after:float=Field(default=.4,ge=.25,le=.8)

class Plan(BaseModel):
 narration_beats:list[NarrationBeat]=Field(default_factory=list,max_length=16)
 render_style:Literal['legacy','content_directed']='content_directed'
 voiceover_script:str|None=Field(default=None,max_length=700,description='整片连贯广告旁白，先写完整句子再安排画面，不逐镜头念标题；无配音可为null。')
 model_config=ConfigDict(extra='forbid')
 title:str=Field(min_length=1,max_length=100)
 cta:str=Field(default='了解更多',min_length=1,max_length=32)
 style:str=Field(min_length=1,max_length=400)
 voice:VoiceId='kokoro_zf_001'
 music:MusicId='pulse'
 creative:CreativeDirection|None=None
 audience:str=Field(min_length=1,max_length=300)
 rationale:str=Field(min_length=1,max_length=1000)
 shots:list[Shot]=Field(min_length=3,max_length=30)
 @model_validator(mode='after')
 def duration_bound(self):
  if sum(s.source in ('image','website') for s in self.shots)<2:raise ValueError('至少两个图片或网站镜头，避免纯字卡')
  if sum(s.source=='image' and s.asset_ref is None for s in self.shots)>6:raise ValueError('生成图片最多6张，其余请用真实截图或简洁图形')
  if sum(s.motion=='brand' for s in self.shots)>1:raise ValueError('品牌收尾仅使用一次')
  for index,shot in enumerate(self.shots):
   if shot.asset_ref is not None and (shot.asset_ref>=index or self.shots[shot.asset_ref].source not in ('image','website') or self.shots[shot.asset_ref].video or shot.source!=self.shots[shot.asset_ref].source or shot.video):raise ValueError('复用素材必须引用此前同类图片/截图镜头，不能复用AI视频')
   units=lambda value:sum(2 if ord(ch)>255 or ch in 'WMwm@#%&' else 1.5 if ch.isalpha() else 1 for ch in value)
   if units(shot.title)>32 or units(shot.narration)>64:raise ValueError('镜头文字过长，请精简标题和旁白')
   if shot.motion=='brand' and len(shot.title)>20:raise ValueError('品牌压印标题最多20字符，确保完整入场与停留')
   if shot.source=='graphic' and shot.layout!='workflow' and shot.motion!='brand':raise ValueError('图形镜头应使用服务图形或品牌收尾')
   if shot.layout=='workflow' and (shot.source!='graphic' or not 2<=len(shot.graphic_labels)<=4 or any(len(label)>10 for label in shot.graphic_labels)):raise ValueError('流程镜头需要2–4个简短资料标签')
   if shot.source!='image' and shot.video:raise ValueError('网站截图用代码运镜，不能用AI视频改写界面')
   if shot.motion=='brand' and shot.video:raise ValueError('品牌收尾使用图片或图形，不花费短视频预算')
   if shot.motion=='page_scroll' and shot.source!='website':raise ValueError('页面浏览镜头只能使用网站截图')
   if shot.video and shot.duration!=5:raise ValueError('视频镜头必须为5秒，避免实际占比超预算')
  if not 15<=sum(s.duration for s in self.shots)<=60:raise ValueError('总时长须15–60秒')
  if sum(s.video for s in self.shots)>2:raise ValueError('最多两段短视频')
  if sum(s.video for s in self.shots)*5>sum(s.duration for s in self.shots)*.4:raise ValueError('AI视频时长不能超过总片长40%')
  if self.narration_beats:
   order=[i for b in self.narration_beats for i in b.shot_indices]
   if order!=list(range(len(self.shots))):raise ValueError('narration_beats必须按顺序覆盖所有镜头且不重复')
  return self
class Clarification(BaseModel):
 model_config=ConfigDict(extra='forbid')
 id:str=Field(min_length=1,max_length=40,pattern=r'^[a-zA-Z0-9_-]+$')
 question:str=Field(min_length=1,max_length=250)
 options:list[Annotated[str,Field(min_length=1,max_length=120)]]=Field(min_length=2,max_length=3)

class DirectorReply(BaseModel):
 model_config=ConfigDict(extra='forbid')
 reply:str=Field(min_length=1,max_length=4000)
 ready:bool=False
 plan:Plan|None=None

 questions:list[Clarification]=Field(default_factory=list,max_length=3)

 @model_validator(mode='after')
 def unique_questions(self):
  if len({q.id for q in self.questions})!=len(self.questions):raise ValueError('补充问题id不可重复')
  return self
