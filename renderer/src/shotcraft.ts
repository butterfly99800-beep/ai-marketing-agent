// Adapted motion grammar: establish -> accelerated move -> true hold.
// Inspired by video-shotcraft spotlight-hero-card; no contour/lighting replica.
export function shotcraftProgress(frame:number,duration:number,holdFrames:number){
 const hold=Math.min(Math.max(holdFrames,Math.min(30,duration*.25)),duration*.5);
 const establish=Math.min(12,duration*.12);
 const end=Math.max(establish+1,duration-hold);
 const t=Math.max(0,Math.min(1,(frame-establish)/(end-establish)));
 return t*t*(3-2*t);
}
