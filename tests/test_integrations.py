import unittest,json,os
from pathlib import Path
from unittest.mock import patch
import app
import test_app as base
class IntegrationTests(unittest.TestCase):
 def setUp(self):
  base.Tests.setUp(self);self.masterpatch=patch.dict(os.environ,{'DIGI_MASTER_KEY_FILE':self.temp.name+'/master.key'});self.masterpatch.start()
 def tearDown(self):
  self.masterpatch.stop();base.Tests.tearDown(self)
 req=base.Tests.req
 register=base.Tests.register
 def admin(self):
  self.register()
  with app.db() as c:c.execute("UPDATE users SET role='admin'")
 def ai_data(self,**changes):return {'model':'test-model','enabled':True,'hourly_quota':7,'key_action':'replace','key':'unit-test-secret-key-123456789','current_password':'a-secure-test-password',**changes}
 def test_requires_admin_password_and_csrf(self):
  self.register()
  self.assertEqual(self.req('/api/admin/integrations')[0],403)
  self.assertEqual(self.req('/api/admin/integrations/ai',self.ai_data())[0],403)
  with app.db() as c:c.execute("UPDATE users SET role='admin'")
  self.assertEqual(self.req('/api/admin/integrations/ai',self.ai_data(current_password='wrong'))[0],403)
  self.assertEqual(self.req('/api/admin/integrations/ai',self.ai_data(),False)[0],403)
 def test_key_encrypted_redacted_and_used_in_generation(self):
  self.admin();data=self.ai_data();self.assertEqual(self.req('/api/admin/integrations/ai',data)[0],200)
  with app.db() as c:stored=c.execute("SELECT encrypted FROM integrations WHERE name='openai'").fetchone()[0]
  self.assertNotIn(data['key'].encode(),stored)
  status=self.req('/api/admin/integrations')[1];self.assertNotIn(data['key'],json.dumps(status));self.assertTrue(status['ai']['ready'])
  with patch('app.remote',return_value={'output':[{'content':[{'type':'output_text','text':'Marketing copy'}]}]}) as remote:
   self.assertEqual(app.generate('real product',['Mastodon']),'Marketing copy');self.assertEqual(remote.call_args.args[2],data['key'])
 def test_remove_does_not_fall_back_to_environment(self):
  self.admin()
  with patch.dict(os.environ,{'OPENAI_API_KEY':'server-test-only','OPENAI_MODEL':'test-model'}):
   self.req('/api/admin/integrations/ai',self.ai_data());self.assertEqual(self.req('/api/admin/integrations/ai',self.ai_data(key_action='remove',key=''))[0],200)
   state=self.req('/api/admin/integrations')[1]['ai'];self.assertFalse(state['key_present']);self.assertEqual(state['source'],'none')
 def test_environment_reuse_disable_and_test(self):
  self.admin()
  with patch.dict(os.environ,{'OPENAI_API_KEY':'server-test-only','OPENAI_MODEL':'test-model'}):
   self.assertEqual(self.req('/api/admin/integrations/ai',self.ai_data(key_action='environment',key=''))[0],200)
   with patch('app.remote',return_value={'output':[]}) as remote:
    self.assertEqual(self.req('/api/admin/integrations/test',{'current_password':'a-secure-test-password'})[0],200);self.assertEqual(remote.call_args.args[2],'server-test-only')
    self.assertEqual(self.req('/api/admin/integrations/test',{'current_password':'a-secure-test-password'})[0],429)
   self.req('/api/admin/integrations/ai',self.ai_data(key_action='keep',enabled=False,key=''))
   with self.assertRaises(ValueError):app.generate('brief',['Mastodon'])
 def test_social_token_is_user_scoped_and_redacted(self):
  self.admin();uid=self.req('/api/state')[1]['user']['id'];data={'user_id':uid,'instance':'https://mastodon.social','enabled':True,'key_action':'replace','key':'unit-test-social-token','current_password':'a-secure-test-password'}
  self.assertEqual(self.req('/api/admin/integrations/social',data)[0],200);self.assertEqual(app.accounts(uid)['Mastodon']['access_token'],data['key']);self.assertNotIn(data['key'],json.dumps(self.req('/api/admin/integrations')[1]));self.assertEqual(app.accounts(uid+1),{})
  self.assertEqual(self.req('/api/admin/integrations/social',{**data,'key_action':'keep','instance':'https://different.example'})[0],400)
  self.assertEqual(self.req('/api/admin/integrations/social',{**data,'key_action':'remove','key':''})[0],200);self.assertEqual(app.accounts(uid),{})
