import asyncio,json,shutil,subprocess,hashlib,wave
from pathlib import Path
from PIL import Image
import imageio_ffmpeg
from app.config import ROOT,DATA,IMAGE_MODEL,VIDEO_MODEL
from app import store
from app.deepseek import ProviderError
from app.wan import WanProvider
from app.schemas import Plan
from app.speech import SpeechProvider
from app.progress import update,estimate
from app.media import download,speak,NODE,stop_owned
ACTIVE=set()
RENDER_LOCK=asyncio.Lock()
def event(p,message):
    p['events'].append(message);p['events']=p['events'][-30:];store.save(p)
async def tracked_submit(wan,p,record,kind,prompt,vertical,image=None):
    try:return await wan.submit(prompt,vertical,image) if image else await wan.submit(prompt,vertical)
    except ProviderError as exc:
        record[kind+'_submission']='rejected' if getattr(exc,'definitive',False) else 'pending'
        record[kind+'_submission_error']={'code':getattr(exc,'code',None),'status':getattr(exc,'status',None),'message':str(exc)}
        store.save(p);raise

async def prepare_narration(p,folder):
    from app.audio_catalog import VOICE_PROFILES,select_voice
    enabled=p.get('narration_enabled',True);voice_id=p.get('voice') or select_voice(p)
    p['voice']=voice_id;p['voice_lock']={'id':voice_id,'engine':VOICE_PROFILES[voice_id]['engine'],'enabled':enabled}
    event(p,('整片固定音色：'+VOICE_PROFILES[voice_id]['name']) if enabled else '已关闭整片配音，保留字幕和配乐。')
    from app.narration_timeline import prepare_measured
    if await prepare_measured(p,folder,voice_id):return
    p.pop('render_timeline',None);p.pop('render_duration',None)
    from app.continuous_narration import prepare_continuous
    if await prepare_continuous(p,folder,voice_id):return
    # Complete every narration segment before submitting any paid image/video task.
    for i,shot in enumerate(p['plan']['shots']):
        record=p['assets'].setdefault(str(i),{});voice=folder/f'voice{i}.wav'
        signature=hashlib.sha256(json.dumps([shot['narration'],voice_id,shot['duration'],enabled],ensure_ascii=False).encode()).hexdigest()
        if record.get('voice_signature')!=signature or not voice.exists():
            if enabled:
                speech_provider=SpeechProvider(strict_voice=True)
                duration=await speech_provider.generate(shot['narration'],voice,shot['duration']-.15,voice_id)
            else:
                with wave.open(str(voice),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(24000);out.writeframes(bytes(4800))
                duration=0
            record.update(voice_signature=signature,voice_duration=duration,voice_id=voice_id,voice_provider=VOICE_PROFILES[voice_id]['engine'] if enabled else 'disabled');store.save(p)
    event(p,'整片配音预检完成；音色一致。' if enabled else '无配音预检完成。')

class ProductionAgent:
    """Resumable assets → narration/camera/captions → validated MP4."""
    def __init__(self,provider_factory=WanProvider):self.provider_factory=provider_factory
    async def render_file(self,folder,props,filename):
        props_path=folder/(filename+'.json');props_path.write_text(json.dumps(props,ensure_ascii=False),encoding='utf-8')
        target=folder/filename
        command=[NODE,str(ROOT/'renderer/node_modules/@remotion/cli/remotion-cli.js'),'render','src/index.tsx','AgentFilm',str(target),'--props',str(props_path),'--browser-executable',r'C:\Program Files\Google\Chrome\Application\chrome.exe','--concurrency','2','--log','info']
        if target.suffix=='.wav':command.extend(['--codec','wav'])
        frames=sum(s.get('duration_frames',round(s['duration']*30)) for s in props['project']['shots'])
        timeout=max(600,min(1800,int(frames*1.2+120)))
        log_path=folder/(filename+'.render.log')
        with log_path.open('wb') as log:
            proc=await asyncio.create_subprocess_exec(*command,cwd=ROOT/'renderer',stdout=log,stderr=asyncio.subprocess.STDOUT)
            try:await asyncio.wait_for(proc.wait(),timeout)
            except asyncio.TimeoutError:await stop_owned(proc);raise ProviderError(f'视频合成超过{timeout}秒，素材和渲染日志已保留，可继续。')
            except asyncio.CancelledError:await stop_owned(proc);raise
        if proc.returncode:raise ProviderError('视频合成失败；素材与渲染日志已保留，可重试。')
        check=await asyncio.to_thread(subprocess.run,[imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-xerror','-i',str(target),'-f','null','-'],capture_output=True,timeout=60)
        if check.returncode:raise ProviderError('成片解码验证未通过')
    async def render_without_music(self,folder,props):
        # Render only the no-BGM audio; reuse exactly the final encoded video frames.
        await self.render_file(folder,dict(props,bgm=False),'final_no_bgm.wav')
        output=folder/'final_no_bgm.tmp.mp4'
        result=await asyncio.to_thread(subprocess.run,[imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-i',str(folder/'final.mp4'),'-i',str(folder/'final_no_bgm.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(output)],capture_output=True,timeout=90)
        if result.returncode:raise ProviderError('无配乐音轨封装失败，主成片和音轨已保留。')
        output.replace(folder/'final_no_bgm.mp4')

    async def run(self,pid):
        if pid in ACTIVE:return
        ACTIVE.add(pid);p=store.get(pid);folder=DATA/pid/f'rev{p["revision"]}';folder.mkdir(parents=True,exist_ok=True)
        assets=p['assets'];vertical=p.get('aspect_ratio','16:9' if p['platform']=='youtube' else '9:16')=='9:16';wan=self.provider_factory()
        try:
            Plan.model_validate(p['plan'])
            from app.creative import MUSIC,audit_plan
            p['creative_audit']=audit_plan(p['plan'],p)
            p['status']='producing';p.pop('error',None);update(p,'准备素材',0,estimate(p),0,len(p['plan']['shots']));event(p,'开始准备旁白和素材；优先复用已生成内容。')
            from app.creative import licensed_music
            if p.get('bgm',True) and p.get('music','pulse') not in licensed_music():raise ProviderError('所选配乐未获本素材库使用许可，请选择原创或已核验授权配乐。')
            await prepare_narration(p,folder)
            for i,shot in enumerate(p['plan']['shots']):
                if isinstance(wan,WanProvider):
                    def on_poll(status,elapsed,index=i):
                        count=len(p['plan']['shots']);update(p,f'第{index+1}个镜头 · 万相{status} · 已等待{elapsed}秒',int(index/count*70),completed=index,total=count)
                    wan.on_poll=on_poll
                update(p,f'制作第{i+1}个镜头',int(i/len(p['plan']['shots'])*70),completed=i,total=len(p['plan']['shots']));record=assets.setdefault(str(i),{});image=folder/f'image{i}.png';voice=folder/f'voice{i}.wav'
                if shot.get('asset_ref') is not None:
                    reference=shot['asset_ref'];src=folder/f'image{reference}.png'
                    if not src.exists():raise ProviderError('复用镜头的原始素材尚未就绪')
                    await asyncio.to_thread(shutil.copyfile,src,image);record['kind']=assets[str(reference)]['kind'];event(p,f'镜头{i+1}复用素材并采用新的景别/版式。')
                elif shot['source']=='graphic':record['kind']='graphic'
                elif shot['source']=='website':
                    src=DATA/pid/p['site']['pages'][shot['screenshot_index']]['file'];await asyncio.to_thread(shutil.copyfile,src,image);record['kind']='screenshot'
                elif not image.exists():
                    if not record.get('image_task'):
                        if record.get('image_submission')=='pending':raise ProviderError('上次图片提交结果不明，为避免重复扣费已停止。请核对服务商任务后再制作新方案。')
                        record['image_submission']='pending';store.save(p)
                        direction=p['plan'].get('creative') or {}
                        prompt=shot['image_prompt']+'\nVisual continuity: '+direction.get('visual_consistency',p['plan']['style'])+'\nNo text, no watermark, no fake brand logo. Keep subject clear; leave negative space for separate captions.'
                        record['image_task']=await tracked_submit(wan,p,record,'image',prompt,vertical);record['image_submission']='confirmed';record['image_model']=IMAGE_MODEL;store.save(p)
                    await download(await wan.result(record['image_task']),image,15*1024*1024)
                    try:
                        with Image.open(image) as im:im.verify()
                    except Exception as e:
                        image.unlink(missing_ok=True);raise ProviderError('生成图片内容无效') from e
                    record['kind']='ai_image';event(p,f'镜头{i+1}图片已生成')
                if image.exists():
                    record.setdefault('kind','ai_image')
                    with Image.open(image) as im:record['asset_width'],record['asset_height']=im.size
                if p.get('narration_track'):record['voice_duration']=0
                else:
                    with wave.open(str(voice)) as speech:record['voice_duration']=speech.getnframes()/speech.getframerate() if p.get('narration_enabled',True) else 0
                video=folder/f'video{i}.mp4'
                if shot['video']:
                    if not p.get('video_budget'):raise ProviderError('未启用短视频预算')
                    if not record.get('video_task'):
                        if record.get('video_submission')=='pending':raise ProviderError('上次视频提交结果不明，为避免重复扣费已停止。请核对服务商任务后再制作新方案。')
                        record['video_submission']='pending';store.save(p)
                        record['video_task']=await tracked_submit(wan,p,record,'video',shot['image_prompt']+'。主体缓慢自然运动，镜头稳定。',vertical,image);record['video_submission']='confirmed';record['video_model']=VIDEO_MODEL;store.save(p)
                    if not video.exists():await download(await wan.result(record['video_task']),video)
                    record['kind']='ai_video';event(p,f'镜头{i+1}五秒视频已生成')
            public=ROOT/'renderer/public/projects'/pid/f'rev{p["revision"]}';public.mkdir(parents=True,exist_ok=True)
            for f in folder.iterdir():
                if f.suffix in ('.png','.wav','.mp4') and not f.name.startswith('final'):await asyncio.to_thread(shutil.copyfile,f,public/f.name)
            # Music segment is stable across retries; prefer unused tracks through the director's recent history.
            p.setdefault('music_start',0)
            tokens=(p.get('site') or {}).get('design_tokens') or {}
            props={'project':{'id':pid+f'/rev{p["revision"]}','title':p['plan']['title'],'cta':p['plan'].get('cta','了解更多'),'brand_font':(tokens.get('font_family') or 'Microsoft YaHei, Arial, sans-serif')[:300],'brand_weight':str((tokens.get('heading') or {}).get('weight',650)),'style':p['plan']['style'],'creative':p['plan'].get('creative'),'music':p.get('music','ambient'),'music_start':p['music_start'],'is_demo':p.get('is_demo',False),'vertical':vertical,'aspect_ratio':p.get('aspect_ratio','16:9' if not vertical else '9:16'),'platforms':p.get('platforms',[]),'narration_enabled':p.get('narration_enabled',True),'narration_track':p.get('narration_track'),'render_style':p['plan'].get('render_style','legacy'),'pace':p.get('pace','fast'),'music_file':MUSIC[p.get('music','ambient')]['file'],'platform':p.get('platform','youtube'),'shots':[dict(s,duration_frames=next((r['duration_frames'] for r in p.get('render_timeline',[]) if r['index']==i),round(s['duration']*30)),capture_meta=(p.get('site') or {}).get('pages',[{}])[s.get('screenshot_index',0)] if s.get('source')=='website' else None,asset_kind=assets[str(i)]['kind'],voice_duration=assets[str(i)]['voice_duration'],asset_width=assets[str(i)].get('asset_width',1920),asset_height=assets[str(i)].get('asset_height',1080)) for i,s in enumerate(p['plan']['shots'])]},'bgm':p.get('bgm',True)}
            (folder/'production-manifest.json').write_text(json.dumps({'plan':p['plan'],'render':props,'audit':p['creative_audit'],'music_credit':MUSIC[p.get('music','ambient')]['credit'],'music_license':MUSIC[p.get('music','ambient')].get('license'),'voice_lock':p.get('voice_lock')},ensure_ascii=False,indent=2),encoding='utf-8')
            update(p,'等待合成',70,completed=len(p['plan']['shots']),total=len(p['plan']['shots']));event(p,'素材准备完成，正在合成字幕、运镜和声音。')
            async with RENDER_LOCK:
                update(p,'合成宣传片',75)
                await self.render_file(folder,props,'final.tmp.mp4');(folder/'final.tmp.mp4').replace(folder/'final.mp4')
                if p.get('bgm',True):
                    update(p,'输出备用版本',88);event(p,'配乐版完成，正在输出保留旁白和音效的无配乐版。')
                    await self.render_without_music(folder,props)
                update(p,'检查成片',96)
                from app.quality import check_output
                p['quality_report']=await asyncio.to_thread(check_output,folder,p)
            p['no_bgm_url']=f'/api/projects/{pid}/video?bgm=false' if p.get('bgm',True) else None
            p['status']='completed';update(p,'已完成',100);p['video_url']=f'/api/projects/{pid}/video';p.pop('error',None);event(p,'视频已完成并通过完整解码验证。')
        except asyncio.CancelledError:
            p['status']='interrupted';p['error']='服务停止，已保留素材和任务记录。';raise
        except Exception as e:
            p['status']='failed';p['error']=str(e) if isinstance(e,ProviderError) else '任务处理失败，素材已保留，请重试或检查运行环境。';event(p,p['error'])
        finally:store.save(p);ACTIVE.discard(pid)
async def produce(pid):await ProductionAgent().run(pid)

