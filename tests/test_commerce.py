import unittest,json,time,hmac,hashlib
from unittest.mock import patch
import app,commerce
import test_app as base
class CommerceTests(unittest.TestCase):
 setUp=base.Tests.setUp
 tearDown=base.Tests.tearDown
 req=base.Tests.req
 register=base.Tests.register
 def admin(self):
  self.register()
  with app.db() as c:c.execute("UPDATE users SET role='admin'")
 def stripe(self):
  data={'provider':'stripe','mode':'test','enabled':True,'key_action':'replace','secret_key':'sk_test_unit_only_12345678','webhook_secret':'whsec_unit_test_only','current_password':'a-secure-test-password'}
  self.assertEqual(self.req('/api/admin/marketplace/gateway',data)[0],200)
 def checkout(self,pid=1):
  with patch('commerce.request',return_value={'id':'cs_test_unique','url':'https://checkout.stripe.com/test'}):
   code,d=self.req('/api/checkout',{'product_id':pid,'provider':'stripe','accepted_purchase_terms':True,'price':1});self.assertEqual(code,201);return d['order_id']
 def response(self,oid,amount=900):return {'id':'cs_test_unique','client_reference_id':oid,'currency':'usd','amount_total':amount,'livemode':False,'payment_status':'paid','payment_intent':'pi_test_unique'}
 def test_catalog_and_admin_gate(self):
  code,d=self.req('/api/marketplace');self.assertEqual(code,200);self.assertEqual(len(d['products']),8);self.assertFalse(any(g['enabled'] for g in d['gateways']));self.assertNotIn('digital_content',d['products'][0]);self.register();self.assertEqual(self.req('/api/admin/marketplace')[0],403)
 def test_gateway_secrets_encrypted_and_not_returned(self):
  self.admin();self.stripe();status=self.req('/api/admin/marketplace')[1];self.assertNotIn('sk_test_unit_only',json.dumps(status))
  with app.db() as c:self.assertNotIn(b'sk_test_unit_only',c.execute("SELECT encrypted FROM integrations WHERE name='payment:stripe'").fetchone()[0])
 def test_server_price_verification_and_download_entitlement(self):
  self.admin();self.stripe();oid=self.checkout()
  self.assertEqual(self.req('/api/orders/download',{'order_id':oid})[0],403)
  with patch('commerce.request',return_value=self.response(oid,1)):self.assertEqual(self.req('/api/orders/verify',{'order_id':oid})[0],400)
  with patch('commerce.request',return_value=self.response(oid)) as remote:
   self.assertTrue(self.req('/api/orders/verify',{'order_id':oid})[1]['paid']);self.assertTrue(self.req('/api/orders/verify',{'order_id':oid})[1]['paid']);self.assertEqual(remote.call_count,1)
  self.assertEqual(self.req('/api/orders/download',{'order_id':oid})[0],200)
  self.register('other@example.com');self.assertEqual(self.req('/api/orders/download',{'order_id':oid})[0],403);self.assertEqual(self.req('/api/orders/verify',{'order_id':oid})[0],400)
 def test_signed_webhook_and_replay(self):
  self.admin();self.stripe();oid=self.checkout();event={'id':'evt_unit','type':'checkout.session.completed','data':{'object':{'id':'cs_test_unique','client_reference_id':oid}}};raw=json.dumps(event).encode();stamp=str(int(time.time()));digest=hmac.new(b'whsec_unit_test_only',stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
  with app.db() as c:
   with self.assertRaises(ValueError):commerce.stripe_webhook(c,app.DB,raw,'t='+stamp+',v1=bad')
  with patch('commerce.request',return_value=self.response(oid)) as remote:
   with app.db() as c:commerce.stripe_webhook(c,app.DB,raw,'t='+stamp+',v1='+digest)
   with app.db() as c:commerce.stripe_webhook(c,app.DB,raw,'t='+stamp+',v1='+digest)
   self.assertEqual(remote.call_count,1)
 def test_product_edits_preserve_order_price_and_contents(self):
  self.admin();self.stripe();oid=self.checkout()
  with app.db() as c:
   product=dict(c.execute('SELECT * FROM products WHERE id=1').fetchone());product['active']=True;product['price']=2000;product['digital_content']='Replacement template'
   commerce.save_product(c,product,1);order=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone();self.assertEqual(order['amount'],900);self.assertNotEqual(order['digital_content'],'Replacement template')
 def test_paypal_approved_requires_capture_and_exact_amount(self):
  self.admin();uid=self.req('/api/state')[1]['user']['id']
  d={'provider':'paypal','mode':'test','enabled':True,'key_action':'replace','client_id':'unit_client_123','client_secret':'unit_secret_456','current_password':'a-secure-test-password'};self.assertEqual(self.req('/api/admin/marketplace/gateway',d)[0],200)
  with patch('commerce.request',side_effect=[{'access_token':'token'},{'id':'PP-UNIT','links':[{'rel':'approve','href':'https://www.sandbox.paypal.com/checkoutnow?token=PP-UNIT'}]}]):
   code,r=self.req('/api/checkout',{'product_id':1,'provider':'paypal','accepted_purchase_terms':True});self.assertEqual(code,201);oid=r['order_id']
  approved={'id':'PP-UNIT','status':'APPROVED','purchase_units':[{'reference_id':oid,'custom_id':oid}]}
  completed={'id':'PP-UNIT','status':'COMPLETED','purchase_units':[{'reference_id':oid,'custom_id':oid,'payments':{'captures':[{'id':'CAP-UNIT','status':'COMPLETED','amount':{'currency_code':'USD','value':'9.00'}}]}}]}
  with patch('commerce.request',side_effect=[{'access_token':'token'},approved,completed]):self.assertTrue(self.req('/api/orders/verify',{'order_id':oid})[1]['paid'])

 def test_sandbox_checkout_is_admin_only(self):
  self.admin();self.stripe();self.register('customer@example.com')
  with patch('commerce.request') as remote:
   self.assertEqual(self.req('/api/checkout',{'product_id':1,'provider':'stripe','accepted_purchase_terms':True})[0],400);remote.assert_not_called()
