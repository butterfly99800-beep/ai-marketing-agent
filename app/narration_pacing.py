"""Add bounded breathing room at existing silence, without changing the speaker."""
import wave,array,sys

def add_breathing_room(path,limit):
 with wave.open(str(path),'rb') as w:
  channels=w.getnchannels();width=w.getsampwidth();rate=w.getframerate();params=w.getparams();raw=w.readframes(w.getnframes())
 if width!=2:return []
 samples=array.array('h');samples.frombytes(raw)
 if sys.byteorder!='little':samples.byteswap()
 duration=len(samples)/channels/rate;budget=min(1.8,max(0,limit-duration-.25))
 if budget<.08:return []
 block=max(1,int(rate*.02))*channels;runs=[];start=None
 for i in range(0,len(samples),block):
  chunk=samples[i:i+block];quiet=bool(chunk) and sum(abs(v) for v in chunk)/len(chunk)<150
  if quiet and start is None:start=i
  if not quiet and start is not None:
   a=start/channels/rate;b=i/channels/rate
   if b-a>=.1 and a>.35 and b<duration-.35:runs.append((start,i,b-a))
   start=None
 # Longest natural phrase breaks first; never add noise or simulated inhalations.
 selected=[]
 for a,b,length in sorted(runs,key=lambda r:r[2],reverse=True):
  t=a/channels/rate
  if any(abs(t-x[0]/channels/rate)<1.3 for x in selected):continue
  selected.append((a,b,min(.16,budget)));budget-=min(.16,budget)
  if len(selected)>=8 or budget<.08:break
 inserts=[];offset=0
 for a,b,extra in sorted(selected):
  position=((a+b)//2)//channels*channels
  inserts.append({'at':position/channels/rate+offset,'seconds':extra});offset+=extra
 for a,b,extra in sorted(selected,reverse=True):
  position=((a+b)//2)//channels*channels;samples[position:position]=array.array('h',[0])*(int(extra*rate)*channels)
 if selected:
  if sys.byteorder!='little':samples.byteswap()
  with wave.open(str(path),'wb') as w:w.setparams(params);w.writeframes(samples.tobytes())
 return inserts
