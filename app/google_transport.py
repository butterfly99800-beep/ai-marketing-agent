"""Use the user's configured Windows proxy for Google APIs only."""
import os

def google_proxy():
 value=os.getenv('YOUTUBE_HTTPS_PROXY','').strip()
 if value.lower() in ('direct','none','off'):return None
 if not value and os.name=='nt':
  try:
   import winreg
   with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
    if not winreg.QueryValueEx(key,'ProxyEnable')[0]:return None
    value=winreg.QueryValueEx(key,'ProxyServer')[0]
  except OSError:return None
 if ';' in value or '=' in value:
  values=dict(item.split('=',1) for item in value.split(';') if '=' in item);value=values.get('https',values.get('http',''))
 return (value if '://' in value else 'http://'+value) if value else None
