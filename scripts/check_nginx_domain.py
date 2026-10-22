"""Fail with filenames if DigiMarketing hostname is shared or declared elsewhere."""
import argparse,re,subprocess
from pathlib import Path

def names(text):
 text=re.sub(r'#.*','',text)
 return [x for m in re.finditer(r'\bserver_name\s+([^;]+);',text) for x in m.group(1).split()]

def check(domain,canonical,dump):
 if canonical.exists():
  others=set(names(canonical.read_text()))-{domain}
  if others:raise ValueError('Refusing to overwrite a shared site file: '+str(canonical)+'; additional hosts: '+', '.join(sorted(others)))
 sections=re.split(r'^# configuration file (.+):\s*$',dump,flags=re.M)
 conflicts=[]
 for index in range(1,len(sections),2):
  path=Path(sections[index]);text=sections[index+1]
  if domain in names(text) and path.resolve()!=canonical.resolve():conflicts.append(str(path))
 if conflicts:raise ValueError('DigiMarketing host is also declared in these active files; resolve duplicate routing first: '+', '.join(conflicts))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('domain');args=p.parse_args()
 result=subprocess.run(['nginx','-T'],capture_output=True,text=True)
 if result.returncode:raise SystemExit('Nginx configuration is invalid; inspect nginx -t before deployment.')
 try:check(args.domain,Path('/etc/nginx/sites-available')/args.domain,result.stdout)
 except ValueError as e:raise SystemExit(str(e))
 print('DigiMarketing host configuration is isolated.')
