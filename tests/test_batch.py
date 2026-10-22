import unittest,tempfile,os,time,fcntl
from pathlib import Path
from unittest.mock import patch
import app,automation
import test_app as base

class BatchTests(unittest.TestCase):
 setUp=base.Tests.setUp
 tearDown=base.Tests.tearDown
 req=base.Tests.req
 register=base.Tests.register
 campaign=base.Tests.campaign
 def test_batch_schedule_is_atomic_and_requires_approval(self):
  self.register();a=self.campaign();b=self.campaign(['Facebook'])
  with patch('app.accounts',return_value={'Mastodon':{}}):
   self.assertEqual(self.req('/api/campaigns/batch',{'ids':[a,b],'due':time.time(),'approved':True})[0],409)
   self.assertEqual(self.req('/api/state')[1]['campaigns'][1]['status'],'draft')
   self.assertEqual(self.req('/api/campaigns/batch',{'ids':[a],'due':time.time(),'approved':False})[0],400)
   self.assertEqual(self.req('/api/campaigns/batch',{'ids':[a],'due':time.time(),'approved':True})[0],200)
 def test_admin_controls_and_bounds(self):
  self.register();limits=dict(app.DEFAULT_LIMITS)
  self.assertEqual(self.req('/api/admin/automation',limits)[0],403)
  with app.db() as c:c.execute("UPDATE users SET role='admin'")
  self.assertEqual(self.req('/api/admin/automation',{**limits,'interval':0})[0],400)
  self.assertEqual(self.req('/api/admin/automation',{**limits,'hourly':3})[0],200)
  self.assertEqual(app.automation_limits()['hourly'],3)
 def test_rate_limit_retry_is_bounded(self):
  self.register();cid=self.campaign()
  for number in range(3):
   with app.db() as c:
    c.execute("UPDATE campaigns SET status='scheduled',due=? WHERE id=?",(time.time()-1,cid))
    c.execute('UPDATE attempts SET created=created-61')
   with patch('app.publish',side_effect=app.ProviderError(429,120)):self.assertTrue(app.tick())
   row=self.req('/api/state')[1]['campaigns'][0]
   self.assertEqual(row['status'],'scheduled' if number<2 else 'needs_review')
   if number<2:self.assertGreater(row['due'],time.time()+100)
 def test_account_spacing_and_dry_run(self):
  self.register();self.campaign();self.campaign()
  with app.db() as c:c.execute("UPDATE campaigns SET status='scheduled',due=?",(time.time()-1,))
  with patch('app.publish',return_value='receipt') as p:
   self.assertEqual(automation.run_batch(dry_run=True)['due'],2);p.assert_not_called()
   result=automation.run_batch();self.assertEqual(result['processed'],1);self.assertEqual(p.call_count,1)
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM batch_runs').fetchone()[0],1)
 def test_overlapping_worker_cannot_claim(self):
  self.register();self.campaign()
  with app.db() as c:c.execute("UPDATE campaigns SET status='scheduled',due=0")
  with open(app.DB+'.worker.lock','a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with patch('app.publish') as p:self.assertFalse(app.tick());p.assert_not_called()
 def test_initialization_does_not_reset_active_jobs(self):
  self.register();self.campaign()
  with app.db() as c:c.execute("UPDATE campaigns SET status='publishing'")
  app.init()
  self.assertEqual(self.req('/api/state')[1]['campaigns'][0]['status'],'publishing')
