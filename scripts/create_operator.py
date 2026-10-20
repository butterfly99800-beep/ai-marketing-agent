"""Create an operator without storing credentials in shell history or Git."""
import sys,getpass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.ops_auth import register
if __name__=='__main__':
 name=input('Account name: ').strip();password=getpass.getpass('Password (8+ characters): ')
 if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match')
 register(name,password);print('Account created. Credentials were not written to project files.')
