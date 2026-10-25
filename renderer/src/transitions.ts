export type TransitionKind='cut'|'push'|'panel'|'dissolve'|'iris';
export type TransitionShot={source:string;motion:string;layout?:string;asset_kind:string;transition?:'auto'|TransitionKind};
export function planTransitions(shots:TransitionShot[],platform='youtube',energy='balanced'){
 const fast=energy!=='calm';let panelUsed=false;let irisUsed=false;
 return shots.map((shot,index)=>{
  let kind:TransitionKind='cut';let reason='开场';
  if(index){
   const before=shots[index-1];
   if(shot.transition&&shot.transition!=='auto'&&(shot.transition!=='iris'||!irisUsed)){kind=shot.transition;reason='执行导演按该镜头信息关系选择的转场';if(kind==='iris')irisUsed=true;}
   else if(shot.motion==='brand'){kind='dissolve';reason='品牌落定，降低运动能量';}
   else if(shot.asset_kind==='ai_video'&&before.asset_kind==='ai_image'){kind='cut';reason='图片进入动态镜头，保留主体构图';}
   else if(!panelUsed&&(shot.layout==='workflow'||before.layout==='workflow')){kind='panel';panelUsed=true;reason='明确的信息段落变化，仅一次层次揭示';}
   else if(shot.source==='website'&&before.source==='website'){kind='cut';reason='真实页面按证据直切，不机械轮换推页';}
   else {kind='cut';reason='主体/动作关系优先，默认直切，不自动制造转场';}
  }
  const frames=kind==='cut'?0:kind==='dissolve'?(fast?8:16):kind==='panel'?(fast?6:12):(fast?5:10);
  return {kind,frames:Math.round(frames*(energy==='calm'?1.2:energy==='energetic'?.85:1)),reason};
 });
}
