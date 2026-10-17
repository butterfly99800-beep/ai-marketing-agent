import React from 'react';
import {AbsoluteFill,Img,Easing,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import {PageCam,CamKey} from './PageCam';
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const ink='#1d2129',accent='#0e7386',bg='#f5f7fa';
type Region={x:number;y:number;w:number;h:number;tag?:string;text?:string};
export function ContentScene({shot,index,project}:{shot:any;index:number;project:any}){
 const frame=useCurrentFrame(),{width,height,fps}=useVideoConfig();const duration=shot.duration_frames??Math.round(shot.duration*fps),hold=Math.max(Math.round(.55*fps),duration-20);const meta=shot.capture_meta||{};const pageH=meta.pageH||((shot.asset_height||1080)/(shot.asset_width||1920)*1920);const regions:Region[]=meta.regions||[];const rowRegions=regions.filter(r=>r.tag==='TR').slice(1,6);const file=`projects/${project.id}/image${index}.png`;const src=staticFile(file);
 const scene=shot.scene||(/brand/.test(shot.motion)?'brand_recall':shot.motion==='page_scroll'?'detail_track':shot.motion==='focus'?'section_wipe':'page_reveal');
 // Camera geometry comes from captured DOM coordinates, never a prose prompt.
 let cx=960,cy=pageH/2,zoom=Math.min(.89,850/pageH);let region=shot.region_index!=null?regions[shot.region_index]:null;if(region&&region.h>1200)region=regions.find(r=>r.tag==='H1')||null;
 if(region){cx=region.x+region.w/2;cy=region.y+region.h/2;zoom=Math.min(1.65,1500/Math.max(400,region.w),740/Math.max(250,region.h));}
 if(!region&&scene==='detail_track'&&pageH<1500){zoom=pageH>1200?.95:1.12;cx=960+(shot.focal_x-.5)*350;cy=Math.min(pageH-420,Math.max(480,pageH*.52));}
 if(!region&&pageH>1500){cx=960;cy=480;zoom=1.02;}
 if(scene==='section_wipe'&&pageH>1500&&region?.tag==='H1'){cx=960;cy=410;zoom=1.16;}
 const intro=interpolate(frame,[0,Math.min(18,duration/4)],[0,1],{...clamp,easing:Easing.bezier(0,0,.2,1)});
 const keys:CamKey[]=[{frame:0,cx:cx-(scene==='detail_track'?75:0),cy:cy+(scene==='detail_track'?35:0),zoom:zoom*(scene==='page_reveal'?.96:1),rotY:scene==='page_reveal'?-3:0,rotX:0},{frame:hold,cx,cy,zoom,rotY:0,rotX:0},{frame:duration,cx,cy,zoom,rotY:0,rotX:0}];
 if(scene==='parallel_compare'){const previous=staticFile(`projects/${project.id}/image${Math.max(0,index-1)}.png`);const a=interpolate(frame,[0,18],[0,1],{...clamp,easing:Easing.bezier(0,0,.2,1)});return <AbsoluteFill style={{background:bg,fontFamily:project.brand_font||'Microsoft YaHei'}}><div style={{position:'absolute',width:1920,height:1080,transform:`scale(${width/1920})`,transformOrigin:'0 0'}}><div style={{position:'absolute',left:96,top:74,fontSize:56,fontWeight:650,color:ink}}>选好的方案，接着往下走。</div><div style={{position:'absolute',left:96,top:200,width:790,height:480,overflow:'hidden',borderRadius:12,boxShadow:'0 20px 45px #17394218'}}><Img src={previous} style={{width:'100%',height:'100%',objectFit:'contain',objectPosition:'top',opacity:.68}}/></div><div style={{position:'absolute',left:1028,top:200,width:790,height:480,overflow:'hidden',borderRadius:12,boxShadow:'0 20px 45px #17394218',opacity:a,transform:`translateX(${(1-a)*90}px)`}}><Img src={src} style={{width:'100%',height:'100%',objectFit:'contain',objectPosition:'top',opacity:.68}}/></div><div style={{position:'absolute',left:925,top:435,color:accent,fontSize:62,opacity:a}}>→</div><div style={{position:'absolute',left:96,top:740,fontSize:42,color:accent}}>产品报价</div><div style={{position:'absolute',left:1028,top:740,fontSize:42,color:accent}}>订舱运输</div><div style={{position:'absolute',left:48,bottom:26,fontSize:32,color:'#75828e'}}>公开产品体验页 · 演示数据</div></div></AbsoluteFill>;}
 const wrapper:React.CSSProperties={position:'absolute',width:1920,height:1080,transform:`scale(${width/1920})`,transformOrigin:'0 0',overflow:'hidden',background:bg};
 if(scene==='brand_recall')return <AbsoluteFill style={{background:bg,fontFamily:project.brand_font||'Microsoft YaHei',color:ink}}><div style={wrapper}>
  <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse at 50% 30%,#d9eff3,transparent 70%)'}}/>
  {(project.shots as any[]).map((s,j)=>({s,j})).filter(({s})=>s.source==='website').slice(1,7).map(({j},k)=>{const a=interpolate(frame,[k*3,30+k*3],[0,1],{...clamp,easing:Easing.bezier(.16,1,.3,1)});return <Img key={j} src={staticFile(`projects/${project.id}/image${j}.png`)} style={{position:'absolute',width:350,height:210,objectFit:'contain',left:155+(k%3)*600,top:70+Math.floor(k/3)*440,borderRadius:12,opacity:a*.3,transform:`translateY(${(1-a)*(k%2?65:-65)}px) rotate(${k%2?3:-3}deg)`}}/>})}
  <div style={{position:'absolute',inset:'33% 8% auto',textAlign:'center',opacity:intro,transform:`translateY(${(1-intro)*20}px)`}}><div style={{fontSize:108,fontWeight:700,letterSpacing:6}}>DREWES</div><div style={{fontSize:52,color:accent,marginTop:22}}>让全球物流，更简单、更透明。</div><div style={{fontSize:38,marginTop:40}}>suiyizou.xyz/showcase</div><div style={{fontSize:32,color:'#6c7580',marginTop:18}}>查看产品体验页</div></div>
 </div></AbsoluteFill>;
 return <AbsoluteFill style={{background:bg,fontFamily:project.brand_font||'Microsoft YaHei'}}><div style={wrapper}>
  <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse at 50% 0%,#e5f0f3,transparent 80%)'}}/>
  <div style={{position:'absolute',inset:0,transform:'translateY(-56px)',opacity:scene==='section_wipe'?1:intro,clipPath:scene==='section_wipe'?`inset(0 ${(1-intro)*100}% 0 0)`:undefined}}>
   <PageCam src={file} pageH={pageH} keys={keys}>
    {scene==='row_embed'&&rowRegions.map((r,k)=>{
     // Adapted from exact RowEmbed demo: cue grid, 12f flight and 4f press retained.
     const cue=[12,22,31,39,46][k],land=cue+12,air=1-interpolate(frame,[cue,land],[0,1],{...clamp,easing:Easing.bezier(.5,0,.8,.75)}),patch=interpolate(frame,[land,land+2],[1,0],clamp);const scale=frame<land?1.06-.065*(1-air):interpolate(frame,[land,land+4],[.995,1],{...clamp,easing:Easing.out(Easing.quad)});
     return <React.Fragment key={k}>{patch>0&&<div style={{position:'absolute',left:r.x-1,top:r.y-1,width:r.w+2,height:r.h+2,background:k%2?'#f7f9fb':'#fff',opacity:patch,zIndex:1}}/>}{frame>=cue&&frame<land+4&&<div style={{position:'absolute',left:r.x,top:r.y,width:r.w,height:r.h,zIndex:2,opacity:interpolate(frame,[cue,cue+3],[0,1],clamp),transform:`perspective(900px) translateY(${-120*air}px) rotateX(${16*air}deg) scale(${scale})`,backgroundImage:`url(${src})`,backgroundSize:`1920px ${pageH}px`,backgroundPosition:`-${r.x}px -${r.y}px`,boxShadow:`0 ${12*air}px ${30*air}px #16343b20`}}/>}{frame>=land&&frame<land+8&&<div style={{position:'absolute',left:r.x,top:r.y+r.h-2,width:r.w,height:2,background:accent,zIndex:3,opacity:interpolate(frame,[land,land+8],[.8,0],clamp),transform:`scaleX(${interpolate(frame,[land,land+5],[0,1],clamp)})`}}/>}</React.Fragment>
    })}
   </PageCam>
  </div>
  <div style={{position:'absolute',left:38,top:22,padding:'10px 16px',borderRadius:8,background:'#f5f7faed',color:accent,fontSize:32,opacity:intro}}>{meta.label||shot.title}</div>
  <div style={{position:'absolute',bottom:0,height:170,left:0,right:0,background:'linear-gradient(0deg,#f5f7fa 72%,#f5f7fa00)'}}/>
  <div style={{position:'absolute',left:48,bottom:26,fontSize:32,color:'#75828e'}}>公开产品体验页 · 演示数据</div>
 </div></AbsoluteFill>;
}
