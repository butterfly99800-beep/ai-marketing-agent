// Sentence boundaries are measured from audio; phrase timing within them is estimated.
export function phraseAt(text:string,start:number,end:number,time:number,vertical:boolean){
 const limit=vertical?28:64;
 const tokens=text.match(/[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*|\s+|[^\x00-\x7F]|./gu)||[];
 const chunks:string[]=[];let current='',units=0;
 for(const token of tokens){
  const size=Array.from(token).reduce((n,c)=>n+(c.charCodeAt(0)>255?2:1),0);
  if(current&&units+size>limit&&!/^[，。！？；,.!?;]$/.test(token)){chunks.push(current.trim());current='';units=0;}
  current+=token;units+=size;
  if(/[，。！？；,.!?;]$/.test(token)&&units>=limit*.45){chunks.push(current.trim());current='';units=0;}
 }
 if(current.trim())chunks.push(current.trim());
 const weights=chunks.map(c=>Math.max(1,c.replace(/\s/g,'').length));const total=weights.reduce((a,b)=>a+b,0);
 const target=Math.max(0,Math.min(.999999,(time-start)/Math.max(.01,end-start)))*total;
 let sum=0;for(let i=0;i<chunks.length;i++){sum+=weights[i];if(target<sum)return chunks[i];}
 return chunks[chunks.length-1]||text;
}
