import json,sqlite3,threading
from contextlib import contextmanager
from datetime import datetime,timezone
from uuid import uuid4
from app.config import ROOT,DATA
LOCK=threading.RLock()
DB=ROOT/'work/studio.sqlite'
def now():return datetime.now(timezone.utc).isoformat()
@contextmanager
def connection():
 c=sqlite3.connect(DB)
 try:
  with c:yield c
 finally:c.close()
def initialize():
 with connection() as c:c.execute('CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)')
def save(p):
 with LOCK,connection() as c:
  p['updated_at']=now();c.execute('INSERT INTO projects VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',(p['id'],json.dumps(p,ensure_ascii=False),p['updated_at']))
def get(i):
 with connection() as c:row=c.execute('SELECT payload FROM projects WHERE id=?',(i,)).fetchone()
 if not row:raise KeyError('项目不存在')
 return json.loads(row[0])
def listing():
 with connection() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM projects ORDER BY updated DESC')]
def create(mode,source,platform,target_duration=30):
 p={'id':str(uuid4()),'mode':mode,'source':source,'platform':platform,'target_duration':target_duration,'messages':[],'status':'draft','revision':0,'plan':None,'assets':{},'events':[],'created_at':now()};save(p);(DATA/p['id']).mkdir(exist_ok=True);return p
initialize()

def summaries():
 keys=('title','mode','platform','status','updated_at','target_duration','work','deleted_at')
 fields=','.join("json_extract(payload,'$."+key+"')" for key in keys)
 with connection() as c:rows=c.execute('SELECT id,'+fields+' FROM projects ORDER BY updated DESC').fetchall()
 result=[]
 for row in rows:
  item=dict(zip(('id',)+keys,row))
  if isinstance(item.get('work'),str):item['work']=json.loads(item['work'])
  result.append(item)
 return result
