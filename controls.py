"""Audited non-withdrawable store credit and revocable Page delegation."""
import time,re,secrets
import integrations

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS credit_ledger(id INTEGER PRIMARY KEY,user_id INTEGER,amount INTEGER,reason TEXT,actor INTEGER,request_id TEXT UNIQUE,created REAL);
 CREATE TABLE IF NOT EXISTS page_shares(user_id INTEGER PRIMARY KEY,owner_id INTEGER,actor INTEGER,created REAL);
 ''')
def balance(c,uid):return c.execute('SELECT COALESCE(SUM(amount),0) FROM credit_ledger WHERE user_id=?',(uid,)).fetchone()[0]
def credit(c,d,actor):
 uid=int(d['user_id']);amount=int(d['amount']);reason=str(d.get('reason','')).strip();key=str(d.get('request_id',''))
 if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise ValueError('User not found')
 if not 0<amount<=10000000 or not 3<=len(reason)<=250 or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',key):raise ValueError('Positive USD cents, reason and request ID required')
 old=c.execute('SELECT * FROM credit_ledger WHERE request_id=?',(key,)).fetchone()
 if old:
  if old['user_id']!=uid or old['amount']!=amount or old['actor']!=actor or old['reason']!=reason:raise ValueError('Credit request ID already used')
  return
 c.execute('INSERT INTO credit_ledger(user_id,amount,reason,actor,request_id,created) VALUES(?,?,?,?,?,?)',(uid,amount,reason,actor,key,time.time()));integrations.audit(c,actor,'credit.grant',uid)
def share(c,d,actor):
 uid=int(d['user_id'])
 if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise ValueError('User not found')
 if d.get('revoke') is True:
  c.execute('DELETE FROM page_shares WHERE user_id=?',(uid,));integrations.audit(c,actor,'facebook.share.revoke',uid);return
 owner=int(d['owner_id']);meta,token=integrations.record(c,'facebook:'+str(owner))
 if uid==owner or not meta or not token or not meta.get('verified') or not meta.get('enabled'):raise ValueError('Select another user and an enabled verified source Page')
 c.execute('INSERT OR REPLACE INTO page_shares VALUES(?,?,?,?)',(uid,owner,actor,time.time()));integrations.audit(c,actor,'facebook.share.grant',uid)
def purchase(c,uid,pid,brief,key):
 if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',str(key)):raise ValueError('Purchase request ID required')
 old=c.execute('SELECT id,product_id FROM orders WHERE receipt=? AND user_id=?',('credit:'+key,uid)).fetchone()
 if old:
  if old['product_id']!=int(pid):raise ValueError('Purchase request ID already used for another product')
  return {'paid':True,'order_id':old['id']}
 p=c.execute('SELECT * FROM products WHERE id=? AND active=1',(int(pid),)).fetchone()
 if not p:raise ValueError('Product unavailable')
 if balance(c,uid)<p['price']:raise ValueError('Insufficient account credit')
 oid=secrets.token_urlsafe(24);now=time.time()
 c.execute('INSERT INTO credit_ledger(user_id,amount,reason,actor,request_id,created) VALUES(?,?,?,?,?,?)',(uid,-p['price'],'Purchase '+oid,uid,'purchase:'+key,now))
 c.execute('INSERT INTO orders(id,user_id,product_id,title,amount,currency,kind,digital_content,provider,mode,status,fulfillment,brief,created,paid,receipt) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,uid,p['id'],p['title'],p['price'],'USD',p['kind'],p['digital_content'],'credit','live','paid','available' if p['kind']=='digital' else 'queued',str(brief)[:4000],now,now,'credit:'+key))
 return {'paid':True,'order_id':oid}
