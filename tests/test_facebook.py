import json
from unittest.mock import patch
import test_integrations as base
import unittest
import app,facebook
class FacebookTests(unittest.TestCase):
 setUp=base.IntegrationTests.setUp
 tearDown=base.IntegrationTests.tearDown
 req=base.IntegrationTests.req
 register=base.IntegrationTests.register
 admin=base.IntegrationTests.admin
 def payload(self,**kw):
  return {'user_id':self.req('/api/state')[1]['user']['id'],'page_id':'1448088625044064','version':'v26.0','enabled':False,'key_action':'replace','key':'test-page-token-123456789','current_password':'a-secure-test-password',**kw}
 def test_page_lifecycle_and_publish(self):
  self.admin();d=self.payload();endpoint='/api/admin/integrations/facebook'
  self.assertEqual(self.req(endpoint,{**d,'current_password':'wrong'})[0],403)
  self.assertEqual(self.req(endpoint,d,False)[0],403)
  self.assertEqual(self.req(endpoint,d)[0],200)
  self.assertNotIn(d['key'],json.dumps(self.req('/api/admin/integrations')[1]))
  self.assertNotIn('Facebook',app.accounts(d['user_id']))
  self.assertEqual(self.req(endpoint,{**d,'enabled':True,'key_action':'keep'})[0],400)
  with patch('facebook.request',return_value={'id':'wrong'}):self.assertEqual(self.req(endpoint+'/verify',d)[0],400)
  with patch('facebook.request',return_value={'id':d['page_id'],'name':'DigiMarketing'}):self.assertEqual(self.req(endpoint+'/verify',d)[0],200)
  self.assertEqual(self.req(endpoint,{**d,'enabled':True,'key_action':'keep'})[0],200)
  self.assertNotIn('Facebook',app.accounts(d['user_id']+1))
  with patch('facebook.request',return_value={'id':'page_post'}) as remote:
   self.assertEqual(app.publish(d['user_id'],'Facebook','approved copy',1),'page_post');self.assertEqual(remote.call_args.args[3],{'message':'approved copy'})
  self.assertEqual(self.req(endpoint,{**d,'page_id':'999999','key_action':'keep'})[0],400)
  self.assertEqual(self.req(endpoint,{**d,'key_action':'remove'})[0],200)
  self.assertNotIn('Facebook',app.accounts(d['user_id']))
 def test_non_admin_cannot_manage_facebook(self):
  self.register();self.assertEqual(self.req('/api/admin/integrations/facebook',self.payload())[0],403)
