import unittest,tempfile,sqlite3,json,zipfile
from pathlib import Path
from scripts.install_store_listing import install
class StoreTests(unittest.TestCase):
 def test_installer_preserves_other_apps_and_visibility(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);database=p/'store.sqlite3';apk=p/'app.apk'
   with zipfile.ZipFile(apk,'w') as z:z.writestr('AndroidManifest.xml','test fixture')
   with sqlite3.connect(database) as c:
    c.execute('CREATE TABLE hosted_apps(domain TEXT PRIMARY KEY,metadata TEXT,visible INTEGER DEFAULT 1,updated INTEGER)');c.execute("INSERT INTO hosted_apps VALUES('other.example','{}',1,0)");c.execute("INSERT INTO hosted_apps VALUES('digimarketing.olamidepanel.com','{}',0,0)")
   install(database,apk)
   with sqlite3.connect(database) as c:
    self.assertEqual(c.execute('SELECT count(*) FROM hosted_apps').fetchone()[0],2)
    row=c.execute("SELECT metadata,visible FROM hosted_apps WHERE domain='digimarketing.olamidepanel.com'").fetchone();self.assertEqual(row[1],0);self.assertEqual(json.loads(row[0])['name'],'DigiMarketing')
 def test_missing_database_fails_without_creation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'missing'
   with self.assertRaises(ValueError):install(p,p)
   self.assertFalse(p.exists())
