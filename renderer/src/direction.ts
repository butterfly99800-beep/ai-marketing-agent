export type Direction={narrative?:string;energy?:'calm'|'balanced'|'energetic';background?:string;foreground?:string;accent?:string};
export const MUSIC:Record<string,{file:string;seconds:number;trim:number}>= {
  "cipher": {
    "file": "cipher.mp3",
    "seconds": 200,
    "trim": 722
  },
  "ambient": {
    "file": "music.wav",
    "seconds": 30,
    "trim": 0
  },
  "house_vibez": {
    "file": "house-vibez.mp3",
    "seconds": 60,
    "trim": 0
  },
  "cat_walk": {
    "file": "cat-walk.mp3",
    "seconds": 60,
    "trim": 0
  },
  "hiphop": {
    "file": "tonight-hiphop.mp3",
    "seconds": 60,
    "trim": 0
  },
  "urban": {
    "file": "g-eazy-nba-type.mp3",
    "seconds": 60,
    "trim": 0
  },
  "pulse": {
    "file": "original-pulse.wav",
    "seconds": 64,
    "trim": 0
  },
  "daylight": {
    "file": "original-daylight.wav",
    "seconds": 64,
    "trim": 0
  },
  "drive": {
    "file": "original-drive.wav",
    "seconds": 64,
    "trim": 0
  },
  "editorial": {
    "file": "original-editorial.wav",
    "seconds": 64,
    "trim": 0
  },
  "bloom": {
    "file": "original-bloom.wav",
    "seconds": 64,
    "trim": 0
  },
  "launch": {
    "file": "original-launch.wav",
    "seconds": 64,
    "trim": 0
  },
  "precision": {
    "file": "original-precision.wav",
    "seconds": 64,
    "trim": 0
  },
  "horizon": {
    "file": "original-horizon.wav",
    "seconds": 64,
    "trim": 0
  },
  "inspired": {
    "file": "inspired.mp3",
    "seconds": 64,
    "trim": 0
  },
  "voice_over_under": {
    "file": "voice_over_under.mp3",
    "seconds": 64,
    "trim": 0
  },
  "apero_hour": {
    "file": "km-apero_hour.mp3",
    "seconds": 283.04,
    "trim": 0
  },
  "carefree": {
    "file": "km-carefree.mp3",
    "seconds": 205.14,
    "trim": 0
  },
  "cheery_monday": {
    "file": "km-cheery_monday.mp3",
    "seconds": 80.22,
    "trim": 0
  },
  "district_four": {
    "file": "km-district_four.mp3",
    "seconds": 248.24,
    "trim": 0
  },
  "dream_culture": {
    "file": "km-dream_culture.mp3",
    "seconds": 214.36,
    "trim": 0
  },
  "edm_detection": {
    "file": "km-edm_detection.mp3",
    "seconds": 365.69,
    "trim": 0
  },
  "electro_cabello": {
    "file": "km-electro_cabello.mp3",
    "seconds": 190.82,
    "trim": 0
  },
  "envision": {
    "file": "km-envision.mp3",
    "seconds": 85.39,
    "trim": 0
  },
  "life_of_riley": {
    "file": "km-life_of_riley.mp3",
    "seconds": 235.36,
    "trim": 0
  },
  "motivator": {
    "file": "km-motivator.mp3",
    "seconds": 237.82,
    "trim": 0
  },
  "wallpaper": {
    "file": "km-wallpaper.mp3",
    "seconds": 220.06,
    "trim": 0
  }
};
// One stable hash per project. Variation affects composition, never facts or budgets.
export const stableSeed=(value:string)=>[...value].reduce((h,ch)=>Math.imul(h^ch.charCodeAt(0),16777619)>>>0,2166136261);
export function camera(motion:string,p:number,site:boolean,W:number,H:number){
 switch(motion){
  case 'pull':return `scale(${1.14-.14*p})`;
  case 'pan':return `translateX(${(p-.5)*W*.07}px) scale(1.10)`;
  case 'orbit':return `perspective(1800px) rotateY(${-7+7*p}deg) rotateX(${2-2*p}deg) scale(${.97+.03*p})`;
  case 'rise':return `translateY(${(1-p)*H*.06}px) scale(${1.08-.04*p})`;
  case 'focus':return `scale(${1+.12*p})`; // Subject-guided push then true hold; no decorative focus rectangle.
  case 'page_scroll':return 'none';
  case 'split':return `translateY(${(1-p)*24}px)`;
  default:return `scale(${site?1+.025*p:1.01+.09*p})`;
 }
}
