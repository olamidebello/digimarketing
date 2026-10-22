import unittest
import app
import test_app as base
class LegalTests(unittest.TestCase):
 setUp=base.Tests.setUp
 tearDown=base.Tests.tearDown
 req=base.Tests.req
 register=base.Tests.register
 def test_registration_requires_current_acceptance(self):
  d={'email':'new@example.com','password':'a-secure-test-password'}
  self.assertEqual(self.req('/api/register',d)[0],400)
  self.assertEqual(self.req('/api/register',{**d,'accepted_terms':True,'privacy_acknowledged':True,'legal_version':'old'})[0],400)
  self.assertEqual(self.req('/api/register',{**d,'accepted_terms':True,'privacy_acknowledged':True,'legal_version':app.LEGAL_VERSION})[0],200)
  with app.db() as c:
   r=c.execute('SELECT * FROM legal_acceptances').fetchone();self.assertEqual(r['terms_version'],app.LEGAL_VERSION);self.assertGreater(r['accepted'],0)
 def test_legal_pages_are_public_and_linked(self):
  self.assertEqual(self.req('/api/legal')[1]['version'],app.LEGAL_VERSION)
  for path,content in [('/terms',b'Batch publishing'),('/privacy',b'delivery attempts'),('/copyright',b'Copyright')]:
   code,body=self.req(path);self.assertEqual(code,200);self.assertIn(content,body)
  body=self.req('/')[1]
  for path in ['/terms','/privacy','/copyright']:self.assertIn(('href="'+path+'"').encode(),body)
 def test_account_deletion_removes_acceptance_and_attempts(self):
  self.register()
  with app.db() as c:
   uid=c.execute('SELECT id FROM users').fetchone()[0];c.execute('INSERT INTO attempts VALUES(?,?,?,?)',(None,uid,'Mastodon',1))
  self.assertEqual(self.req('/api/account/delete',{})[0],200)
  with app.db() as c:
   for table in ['legal_acceptances','attempts']:self.assertEqual(c.execute('SELECT count(*) FROM '+table).fetchone()[0],0)

 def test_deleted_identity_is_never_reused_for_social_credentials(self):
  self.register('first@example.com');old=self.req('/api/state')[1]['user']['id']
  self.assertEqual(self.req('/api/account/delete',{})[0],200)
  self.register('second@example.com');new=self.req('/api/state')[1]['user']['id']
  self.assertGreater(new,old)
