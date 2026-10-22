import unittest,tempfile,threading,json,time,os,http.client
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import app
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();app.DB=self.temp.name+'/db';app.init();app.ATTEMPTS.clear();os.environ['DIGI_DEV']='1'
  self.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.cookie='';self.csrf=''
 def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
 def req(self,path,data=None,csrf=True):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);h={'Cookie':self.cookie}
  if data is not None:h.update({'Content-Type':'application/json','X-CSRF-Token':self.csrf if csrf else 'bad'})
  c.request('POST' if data is not None else 'GET',path,json.dumps(data) if data is not None else None,h);r=c.getresponse();code=r.status;cookie=r.getheader('Set-Cookie');body=r.read();c.close()
  if cookie:self.cookie=cookie.split(';')[0]
  try:return code,json.loads(body)
  except Exception:return code,body
 def register(self,email='a@example.com'):
  self.assertEqual(self.req('/api/register',{'email':email,'password':'a-secure-test-password'})[0],200);self.csrf=self.req('/api/state')[1]['csrf']
 def campaign(self,channels=None):
  code,d=self.req('/api/campaigns',{'title':'Real offer','content':'Try our product','channels':channels or ['Mastodon']});self.assertEqual(code,201);return d['id']
 def test_isolation_csrf(self):
  self.assertEqual(self.req('/api/state')[0],401);self.register();cid=self.campaign();self.assertEqual(self.req(f'/api/campaigns/{cid}/delete',{},False)[0],403);self.register('b@example.com');self.assertEqual(self.req('/api/state')[1]['campaigns'],[]);self.assertEqual(self.req(f'/api/campaigns/{cid}/delete',{})[0],404)
 def test_schedule_idempotency(self):
  self.register();cid=self.campaign()
  with patch('app.accounts',return_value={'Mastodon':{}}):
   self.assertEqual(self.req(f'/api/campaigns/{cid}/schedule',{'due':time.time(),'approved':False})[0],400);self.assertEqual(self.req(f'/api/campaigns/{cid}/schedule',{'due':time.time(),'approved':True})[0],200)
  with patch('app.publish',return_value='receipt') as p:app.tick();app.tick();self.assertEqual(p.call_count,1)
  self.assertEqual(self.req('/api/state')[1]['campaigns'][0]['status'],'published')
 def test_unsupported_channel(self):
  self.register();cid=self.campaign(['Facebook']);self.assertEqual(self.req(f'/api/campaigns/{cid}/schedule',{'due':time.time(),'approved':True})[0],409)
 def test_pause_and_failed_delivery(self):
  self.register();cid=self.campaign()
  with app.db() as c:c.execute("UPDATE campaigns SET status='scheduled',due=?",(time.time()-1,));c.execute("INSERT INTO settings VALUES('paused','1')")
  with patch('app.publish',side_effect=ValueError('Provider returned HTTP 429')) as p:
   app.tick();self.assertEqual(p.call_count,0)
   with app.db() as c:c.execute("UPDATE settings SET value='0'")
   app.tick();app.tick();self.assertEqual(p.call_count,1)
  self.assertEqual(self.req('/api/state')[1]['campaigns'][0]['status'],'needs_review')
 def test_delete_account_admin_guard(self):
  self.register();self.campaign();self.assertEqual(self.req('/api/admin/pause',{'paused':True})[0],403);self.assertEqual(self.req('/api/account/delete',{})[0],200);self.assertEqual(self.req('/api/state')[0],401)
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM campaigns').fetchone()[0],0)
 def test_assets_and_no_fake_apk(self):
  for path in ['/','/app.js','/style.css','/brand.png','/terms','/privacy','/copyright','/manifest.json']:self.assertEqual(self.req(path)[0],200,path)
  self.assertFalse(self.req('/api/download')[1]['available']);self.assertEqual(self.req('/downloads/DigiMarketing.apk')[0],404)
 def test_ai_mock_and_no_secret_exposure(self):
  self.register()
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-secret','OPENAI_MODEL':'test-model'}),patch('app.remote',return_value={'output':[{'content':[{'type':'output_text','text':'Real copy'}]}]}):
   code,d=self.req('/api/generate',{'brief':'A product','channels':['Mastodon']});self.assertEqual(code,200);self.assertEqual(d['content'],'Real copy');self.assertNotIn('test-secret',json.dumps(self.req('/api/state')[1]))
 def test_edit_pauses_schedule(self):
  self.register();cid=self.campaign()
  with app.db() as c:c.execute("UPDATE campaigns SET status='scheduled'")
  self.assertEqual(self.req(f'/api/campaigns/{cid}/edit',{'content':'Updated copy'})[0],200);self.assertEqual(self.req('/api/state')[1]['campaigns'][0]['status'],'draft')
if __name__=='__main__':unittest.main()
