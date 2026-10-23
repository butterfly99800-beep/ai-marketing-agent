"""Run on the server as its service user; preserves account ownership and videos."""
import getpass,sys,secrets
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import ops_auth as auth

def recover(name,password):
 name=name.strip()
 if not 3<=len(name)<=60 or not 8<=len(password)<=128:
  raise ValueError('Account: 3-60 characters; password: 8-128 characters')
 auth.initialize()
 with auth.db() as c:
  row=c.execute('SELECT id FROM ops_users WHERE name=?',(name,)).fetchone()
 if not row:
  auth.register(name,password)
  return 'Account created'
 salt=secrets.token_hex(16)
 with auth.db() as c:
  c.execute('UPDATE ops_users SET salt=?,password=? WHERE id=?',(salt,auth.password_hash(password,salt),row[0]))
  c.execute('DELETE FROM ops_sessions WHERE owner=?',(row[0],))
 return 'Password reset; old sessions revoked; account data preserved'

if __name__=='__main__':
 name=input('Account name: ').strip()
 password=getpass.getpass('New password: ')
 if password!=getpass.getpass('Confirm new password: '):raise SystemExit('Passwords do not match')
 print(recover(name,password))
