"""Three-second render without generated images, TTS, accounts or paid APIs."""
import sys,asyncio
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from app.producer import ProductionAgent
async def main():
 folder=root/'work/deploy-render-smoke';folder.mkdir(parents=True,exist_ok=True)
 props={'project':{'id':'deploy-smoke','title':'Deployment check','style':'minimal','vertical':False,'platform':'youtube','music':'ambient','narration_enabled':False,'shots':[{'title':'Deployment check','narration':'','duration':3,'motion':'brand','source':'graphic','asset_kind':'graphic','graphic_labels':['Deployment check'],'focal_x':.5,'focal_y':.5}]},'bgm':True}
 await ProductionAgent().render_file(folder,props,'smoke.mp4');print('RENDER_SMOKE_OK')
if __name__=='__main__':asyncio.run(main())
