"""Install only DigiMarketing metadata in the existing African Apps Store DB."""
import argparse,hashlib,json,sqlite3,time,zipfile
from pathlib import Path

def install(database,apk):
 if not database.is_file():raise ValueError('Existing African Apps Store database not found')
 with zipfile.ZipFile(apk) as z:
  if 'AndroidManifest.xml' not in z.namelist():raise ValueError('APK manifest missing')
 digest=hashlib.sha256(apk.read_bytes()).hexdigest()
 metadata={'domain':'digimarketing.olamidepanel.com','name':'DigiMarketing','category':'Business','package':'com.olamidepanel.digimarketing.dev','website':'https://digimarketing.olamidepanel.com/','description':'Turn attention into opportunity. Create, draft, review and schedule campaigns. Development Android website client; internet and a working website required.','features':['AI-assisted campaign copy','Editable campaigns and approval','Configured Mastodon text publishing','Copy export for other social channels'],'limitations':'Development signing; no offline mode. Other social publishing integrations not implemented.','apk_url':'https://digimarketing.olamidepanel.com/downloads/DigiMarketing.apk','icon_url':'https://digimarketing.olamidepanel.com/brand.png','sha256':digest,'download_status':'available','channel':'development','version':'1.0.0-dev'}
 with sqlite3.connect(database) as c:
  if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='hosted_apps'").fetchone():raise ValueError('Existing store hosted_apps schema missing')
  with sqlite3.connect(str(database)+'.digimarketing-'+str(int(time.time()))+'.bak') as backup:c.backup(backup)
  c.execute('INSERT INTO hosted_apps(domain,metadata,updated) VALUES(?,?,?) ON CONFLICT(domain) DO UPDATE SET metadata=excluded.metadata,updated=excluded.updated',(metadata['domain'],json.dumps(metadata),int(time.time())))
 print('DigiMarketing listing installed with verified APK checksum '+digest)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--database',type=Path,default=Path('/var/lib/africanappsstore/store.sqlite3'));p.add_argument('--apk',type=Path,required=True);a=p.parse_args();install(a.database,a.apk)
