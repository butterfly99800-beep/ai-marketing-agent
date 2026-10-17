"""Real technical checks. Does not pretend local rules are human aesthetic review."""
import json,re,subprocess
import imageio_ffmpeg

def check_output(folder,project):
 ff=imageio_ffmpeg.get_ffmpeg_exe();video=folder/'final.mp4'
 r=subprocess.run([ff,'-hide_banner','-i',str(video),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,timeout=90)
 if r.returncode and (project.get('narration_enabled',True) or project.get('bgm',True) or 'does not contain any stream' not in r.stderr.decode(errors='replace')):raise RuntimeError('音频检查失败')
 matches=re.findall(r'max_volume:\s*(-?[\d.]+) dB',r.stderr.decode(errors='replace'))
 peak=float(matches[-1]) if matches else None
 if peak is not None and peak>=-.1:raise RuntimeError('混音接近削波，请降低音量后重新合成')
 frames=[];cursor=0;qa=folder/'qa';qa.mkdir(exist_ok=True)
 for i,s in enumerate(project['plan']['shots']):
  # Mid/settled scene probes from encoded output, not separate mock previews.
  duration=next((r['duration_frames'] for r in project.get('render_timeline',[]) if r['index']==i),s['duration']*30)
  f=cursor+min(duration-8,max(30,duration//2));name=f'shot-{i+1}.jpg'
  r=subprocess.run([ff,'-v','error','-y','-ss',str(f/30),'-i',str(video),'-frames:v','1',str(qa/name)],capture_output=True,timeout=30)
  if r.returncode or not (qa/name).exists():raise RuntimeError('关键帧抽取未通过')
  frames.append({'frame':f,'file':'qa/'+name,'title':s['title']});cursor+=duration
 report={'status':'technical_pass','duration_seconds':cursor/30,'audio_peak_dbfs':peak,'frames':frames,
         'plan_audit':project.get('creative_audit'),
         'scope':'完整解码、音频峰值、关键帧已生成；不等于人工审美或语义核验。',
         'limitations':['未接入实时热门榜','未自动验证第三方网站的完整业务操作','字幕与AI图片事实需人工核对']}
 (folder/'quality-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report
