from pathlib import Path
from app.config import ROOT
VOICE_PROFILES={}
for code,name,gender,language,tags in [
 ('zf_001','中文女声 01 · 品牌讲解','female','zh',['专业','品牌','讲解']),
 ('zf_002','中文女声 02 · 亲切介绍','female','zh',['亲切','服务','教育']),
 ('zf_003','中文女声 03 · 轻快推荐','female','zh',['年轻','消费','活力']),
 ('zf_004','中文女声 04 · 克制叙事','female','zh',['叙事','审美','生活']),
 ('zm_010','中文男声 10 · 企业介绍','male','zh',['企业','物流','工业']),
 ('zm_011','中文男声 11 · 产品讲解','male','zh',['科技','产品','专业']),
 ('zm_012','中文男声 12 · 稳健叙事','male','zh',['叙事','品牌','沉稳']),
 ('af_maple','Maple · 英文女声','female','en',['英文','商务','产品']),
 ('af_sol','Sol · 英文女声','female','en',['英文','年轻','活力']),
 ('bf_vale','Vale · 英式女声','female','en',['英文','英式','叙事'])]:
 VOICE_PROFILES['kokoro_'+code]={'name':name,'speaker':code,'engine':'kokoro','gender':gender,'language':language,'tags':tags,'license':'Apache-2.0','source':'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh'}
for key,name,gender in [('Ethan','云端 Ethan','male'),('Cherry','云端 Cherry','female'),('Serena','云端 Serena','female'),('local','Windows 系统音色（兼容）','female')]:
 VOICE_PROFILES[key]={'name':name,'engine':'windows' if key=='local' else 'qwen','language':'multi','gender':gender,'tags':['兼容'],'license':'系统/服务商条款'}
def kokoro_ready():
 return all((ROOT/'models/kokoro'/f).exists() for f in ('kokoro-v1.1-zh.onnx','voices-v1.1-zh.bin','config.json')) and (ROOT/'.runtime/voice_deps/kokoro_onnx').exists()
def voice_catalog():
 return {k:dict(v,available=kokoro_ready() if v['engine']=='kokoro' else k!='local',preview_url='/api/voices/'+k+'/preview') for k,v in VOICE_PROFILES.items()}
def select_voice(p):
 requested=(p.get('sound_preferences') or {}).get('voice')
 if requested in VOICE_PROFILES:return requested
 proposed=(p.get('plan') or {}).get('voice')
 if proposed and proposed.startswith('kokoro_') and kokoro_ready():return proposed
 content=' '.join(m.get('content','') for m in p.get('messages',[]) if m.get('role')=='user')
 english=sum('a'<=c.lower()<='z' for c in content)>sum('\u4e00'<=c<='\u9fff' for c in content)*2
 if kokoro_ready():return 'kokoro_af_maple' if english else 'kokoro_zm_010' if '男声' in content or any(x in content for x in ('物流','制造','工业')) else 'kokoro_zf_001'
 return proposed or 'Cherry'
