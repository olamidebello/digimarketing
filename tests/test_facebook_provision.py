import importlib.util,unittest,json
from pathlib import Path
from unittest.mock import patch
import test_integrations as base
import app
spec=importlib.util.spec_from_file_location('provision',Path(__file__).parents[1]/'scripts/provision-facebook.py');provision=importlib.util.module_from_spec(spec);spec.loader.exec_module(provision)
class ProvisionTests(unittest.TestCase):
 setUp=base.IntegrationTests.setUp
 tearDown=base.IntegrationTests.tearDown
 req=base.IntegrationTests.req
 register=base.IntegrationTests.register
 admin=base.IntegrationTests.admin
 def test_reuse_idempotency_and_disable(self):
  self.admin()
  with app.db() as c:
   with patch('facebook.request',return_value={'id':'1448088625044064','name':'DigiMarketing'}):
    a=provision.provision(c,app.DB,'a@example.com','1448088625044064','v26.0',False,'test-page-token-secret')
    self.assertTrue(a['changed'])
    self.assertFalse(provision.provision(c,app.DB,'a@example.com','1448088625044064','v26.0')['changed'])
    self.assertTrue(provision.provision(c,app.DB,'a@example.com','1448088625044064','v26.0',True)['publishing_enabled'])
    self.assertTrue(provision.provision(c,app.DB,'a@example.com','1448088625044064','v26.0')['changed'])
 def test_failure_rolls_back(self):
  self.admin()
  with patch('facebook.request',return_value={'id':'wrong'}):
   with self.assertRaises(ValueError):
    with app.db() as c:provision.provision(c,app.DB,'a@example.com','1448088625044064','v26.0',False,'test-page-token-secret')
  with app.db() as c:self.assertIsNone(c.execute("SELECT * FROM integrations WHERE name LIKE 'facebook:%'").fetchone())
 def test_protected_file(self):
  p=Path(self.temp.name)/'token';p.write_text('test-page-token-secret');p.chmod(0o644)
  with self.assertRaises(ValueError):provision.read_token(str(p))
