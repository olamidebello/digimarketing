import unittest
from unittest.mock import patch
import app,controls
import test_integrations as base
class ControlsTests(unittest.TestCase):
 setUp=base.IntegrationTests.setUp
 tearDown=base.IntegrationTests.tearDown
 req=base.IntegrationTests.req
 register=base.IntegrationTests.register
 admin=base.IntegrationTests.admin
 def test_credit_checkout_and_replay(self):
  self.admin();d={'user_id':1,'amount':2000,'reason':'Promotional grant','request_id':'grant-request-12345','current_password':'a-secure-test-password'}
  self.assertEqual(self.req('/api/admin/credits',d,False)[0],403)
  self.assertEqual(self.req('/api/admin/credits',d)[0],200);self.assertEqual(self.req('/api/admin/credits',d)[0],200)
  self.assertEqual(self.req('/api/state')[1]['balance'],2000)
  buy={'provider':'credit','product_id':1,'request_id':'purchase-request-12345','accepted_purchase_terms':True}
  a=self.req('/api/checkout',buy);self.assertEqual(a[0],201);self.assertEqual(a,self.req('/api/checkout',buy));self.assertEqual(self.req('/api/state')[1]['balance'],1100)
  self.assertEqual(self.req('/api/orders/download',{'order_id':a[1]['order_id']})[0],200)
  self.assertEqual(self.req('/api/checkout',{**buy,'request_id':'other-request-12345','product_id':5})[0],400)
 def test_sharing_is_revocable_and_scoped(self):
  self.admin();self.register('second@example.com')
  self.assertEqual(self.req('/api/admin/page-shares',{'user_id':2,'owner_id':1})[0],403)
  with app.db() as c:
   import facebook
   facebook.save(c,app.DB,{'user_id':1,'page_id':'1448088625044064','version':'v26.0','enabled':False,'key_action':'replace','key':'test-page-token-secret'},1)
   with patch('facebook.request',return_value={'id':'1448088625044064','name':'DigiMarketing'}):facebook.verify(c,app.DB,1,1)
   facebook.save(c,app.DB,{'user_id':1,'page_id':'1448088625044064','version':'v26.0','enabled':True,'key_action':'keep'},1)
   controls.share(c,{'user_id':2,'owner_id':1},1)
   self.assertEqual(app.uid_for_channel(c,2,'Facebook'),1)
  self.assertIn('Facebook',app.accounts(2));self.assertNotIn('Facebook',app.accounts(3))
  with app.db() as c:controls.share(c,{'user_id':2,'revoke':True},1)
  self.assertNotIn('Facebook',app.accounts(2))
