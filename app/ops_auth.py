"""Local workbench accounts. OAuth secrets never enter the browser or AI context."""
import secrets,hashlib,hmac,time,json,os,threading
from contextvars import ContextVar
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app import store
from app.config import ROOT
CURRENT_USER=ContextVar('ops_user',default=None)
KEY_LOCK=threading.Lock()

def db():
 c=store.connection();return c

def initialize():
 with db() as c:
  c.executescript('''
  CREATE TABLE IF NOT EXISTS ops_users(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL, created REAL);
  CREATE TABLE IF NOT EXISTS ops_sessions(id TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL);
  CREATE TABLE IF NOT EXISTS ops_states(id TEXT PRIMARY KEY, session TEXT NOT NULL, verifier TEXT NOT NULL, expires REAL NOT NULL);
  CREATE TABLE IF NOT EXISTS ops_channels(id TEXT PRIMARY KEY, owner TEXT NOT NULL, channel_id TEXT NOT NULL, title TEXT NOT NULL, token TEXT NOT NULL, created REAL, UNIQUE(owner,channel_id));
  CREATE TABLE IF NOT EXISTS ops_jobs(id TEXT PRIMARY KEY, owner TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, updated REAL);
  ''')

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password_hash(value,salt):return hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),600000).hex()

def register(name,password):
 initialize();name=name.strip()
 if not 3<=len(name)<=60 or not 8<=len(password)<=128:raise HTTPException(400,'账号需3–60字，密码需8–128字。')
 uid=secrets.token_hex(16);salt=secrets.token_hex(16);hashed=password_hash(password,salt)
 with store.LOCK,db() as c:
  first=c.execute('SELECT COUNT(*) FROM ops_users').fetchone()[0]==0
  try:c.execute('INSERT INTO ops_users VALUES(?,?,?,?,?)',(uid,name,salt,hashed,time.time()))
  except Exception:raise HTTPException(409,'账号名已存在。')
  if first:
   # The initial local operator owns existing local-workspace projects.
   rows=c.execute('SELECT id,payload FROM projects').fetchall()
   for pid,raw in rows:
    p=json.loads(raw)
    if not p.get('owner_id'):p['owner_id']=uid;c.execute('UPDATE projects SET payload=? WHERE id=?',(json.dumps(p,ensure_ascii=False),pid))
 return uid

FAILURES={}
def login(name,password,remote='local'):
 initialize();key=remote+':'+name;attempts=[t for t in FAILURES.get(key,[]) if t>time.time()-300]
 if len(attempts)>=8:raise HTTPException(429,'登录尝试过多，请5分钟后再试。')
 with db() as c:row=c.execute('SELECT id,salt,password FROM ops_users WHERE name=?',(name.strip(),)).fetchone()
 hashed=password_hash(password,row[1] if row else '0'*32)
 if not row or not hmac.compare_digest(hashed,row[2]):FAILURES[key]=attempts+[time.time()];raise HTTPException(401,'账号或密码不正确。')
 FAILURES.pop(key,None);return row[0]

def session(uid):
 initialize();token=secrets.token_urlsafe(40)
 with db() as c:c.execute('INSERT INTO ops_sessions VALUES(?,?,?)',(digest(token),uid,time.time()+7*86400))
 return token

def current(request):
 initialize();token=request.cookies.get('ops_session','')
 if not token:return None
 with db() as c:row=c.execute('SELECT u.id,u.name FROM ops_sessions s JOIN ops_users u ON u.id=s.owner WHERE s.id=? AND s.expires>?',(digest(token),time.time())).fetchone()
 return {'id':row[0],'name':row[1]} if row else None

def require(request):
 user=current(request)
 if not user:raise HTTPException(401,'请先登录发布工作台。')
 return user

def cipher():
 path=ROOT/'work/operations-key.bin'
 with KEY_LOCK:
  if not path.exists():
   key=Fernet.generate_key()
   if os.name=='nt':key=protect(key,False)
   path.write_bytes(key)
   if os.name!='nt':path.chmod(0o600)
  raw=path.read_bytes()
 return Fernet(protect(raw,True) if os.name=='nt' else raw)

def protect(data,decrypt):
 import ctypes
 from ctypes import wintypes
 class BLOB(ctypes.Structure):_fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_byte))]
 buf=ctypes.create_string_buffer(data);src=BLOB(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte)));out=BLOB()
 dll=ctypes.windll.crypt32
 ok=dll.CryptUnprotectData(ctypes.byref(src),None,None,None,None,1,ctypes.byref(out)) if decrypt else dll.CryptProtectData(ctypes.byref(src),'Marketing OAuth',None,None,None,1,ctypes.byref(out))
 if not ok:raise RuntimeError('Windows令牌保护不可用')
 try:return ctypes.string_at(out.pbData,out.cbData)
 finally:ctypes.windll.kernel32.LocalFree(out.pbData)

def encrypt(value):return cipher().encrypt(json.dumps(value).encode()).decode()
def decrypt(value):return json.loads(cipher().decrypt(value.encode()))
