"""DigiMarketing single-merchant catalog and verified hosted payments."""
import json,time,secrets,hashlib,hmac,base64,re
from decimal import Decimal
from urllib.request import Request,urlopen
from urllib.parse import urlencode,quote,urlparse
from urllib.error import HTTPError
import integrations
BASE='https://digimarketing.olamidepanel.com'
CATALOG=[
 ('Caption Template Kit','Templates',900,'digital','10 adaptable caption templates. Instant text download after confirmed payment.','Instant download','1. Meet [product]: [benefit]. Explore [link].\n2. Solving [problem]? Try [service].\n3. Built for [audience], designed for [benefit].\n4. Three things to know: [facts].\n5. Behind the scenes: [real story].\n6. Your questions answered: [verified FAQ].\n7. New this week: [offer and terms].\n8. Customer story: [permission-approved quote].\n9. Compare your options: [substantiated features].\n10. Ready for [goal]? Start at [link].'),
 ('AI Copy Review Pack','Copywriting',1900,'service','10 AI-assisted captions reviewed for your supplied brief. Includes one revision.','2 business days',''),
 ('Brand Creative Brief','Branding',2900,'service','A written audience, messaging and visual-direction brief. Includes one revision.','3 business days',''),
 ('Campaign Launch Plan','Campaigns',4900,'service','One campaign plan with 15 caption drafts and a channel checklist. Advertising spend excluded.','3 business days',''),
 ('30-Day Growth Campaign Plan','Campaigns',14900,'service','A 30-day plan, 30 caption ideas and four written progress reviews. No follower, revenue or reach guarantee. Advertising spend excluded.','30 days',''),
 ('Landing Page Audit','Consulting',3900,'service','A written 20-point review of one landing page covering message clarity, conversion flow and mobile usability.','2 business days',''),
 ('Short Video Script Pack','Video',2500,'service','Three short-form video scripts based on your brief. Video recording and production excluded.','2 business days',''),
 ('30-Day Content Calendar Kit','Templates',1200,'digital','Reusable calendar prompts for planning a month of content. Instant text download.','Instant download','Week 1: Introduce your brand, problem, solution, founder story, FAQ, useful tip, weekly recap.\nWeek 2: Demonstration, feature spotlight, tutorial, comparison with evidence, behind the scenes, customer story with permission, recap.\nWeek 3: Industry lesson, checklist, common mistake, product use case, honest limitation, Q&A, recap.\nWeek 4: Offer with clear terms, reminder, benefit, team story, verified testimonial, FAQ, next steps.\nDays 29–30: Review actual results and plan your next experiment.')]

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,title TEXT,category TEXT,price INTEGER,kind TEXT,description TEXT,delivery TEXT,digital_content TEXT,active INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,user_id INTEGER,product_id INTEGER,title TEXT,amount INTEGER,currency TEXT,kind TEXT,digital_content TEXT,provider TEXT,mode TEXT,provider_id TEXT UNIQUE,checkout_url TEXT,status TEXT,fulfillment TEXT,brief TEXT,created REAL,paid REAL,receipt TEXT UNIQUE);
 CREATE TABLE IF NOT EXISTS payment_events(id TEXT PRIMARY KEY,created REAL);
 ''')
 for i,values in enumerate(CATALOG,1):c.execute('INSERT OR IGNORE INTO products VALUES(?,?,?,?,?,?,?,?,1)',(i,*values))

def request(url,method='GET',payload=None,headers=None,form=False):
 data=None if payload is None else (urlencode(payload).encode() if form else json.dumps(payload).encode())
 headers={'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json',**(headers or {})}
 try:
  with urlopen(Request(url,data,headers,method=method),timeout=30) as r:return json.load(r)
 except HTTPError as e:raise ValueError('Payment provider returned HTTP '+str(e.code)) from None

def gateway(c,db,provider,require_enabled=True):
 if provider not in ['stripe','paypal']:raise ValueError('Unsupported gateway')
 meta,encrypted=integrations.record(c,'payment:'+provider)
 if not meta or not encrypted or (require_enabled and not meta['enabled']):raise ValueError('Payment gateway is not enabled and configured.')
 return meta,json.loads(integrations.cipher(db).decrypt(encrypted))

def public_gateways(c):
 result=[]
 for provider in ['stripe','paypal']:
  meta,encrypted=integrations.record(c,'payment:'+provider)
  result.append({'provider':provider,'enabled':bool(meta and meta['enabled'] and encrypted),'mode':meta['mode'] if meta else 'test','configured':bool(encrypted)})
 return result

def save_gateway(c,db,d,actor):
 provider=d['provider']
 if provider not in ['stripe','paypal'] or d['mode'] not in ['test','live'] or not isinstance(d['enabled'],bool):raise ValueError('Invalid gateway settings')
 old,encrypted=integrations.record(c,'payment:'+provider);action=d.get('key_action','keep')
 if action=='replace':
  keys={key:str(d.get(key,'')).strip() for key in (['secret_key','webhook_secret'] if provider=='stripe' else ['client_id','client_secret'])}
  if any(not 8<=len(v)<=4096 or any(ch.isspace() for ch in v) for v in keys.values()):raise ValueError('Complete both credential fields for the selected gateway.')
  if provider=='stripe' and not keys['secret_key'].startswith('sk_'+d['mode']+'_'):raise ValueError('Stripe key must match the chosen test/live mode.')
  encrypted=integrations.cipher(db).encrypt(json.dumps(keys).encode())
 elif action=='remove':encrypted=None
 elif action!='keep':raise ValueError('Unknown credential action')
 if action=='keep' and old and old['mode']!=d['mode'] and encrypted:raise ValueError('Replace credentials when switching payment mode.')
 if d['enabled'] and not encrypted:raise ValueError('Add credentials before enabling this gateway.')
 c.execute('INSERT OR REPLACE INTO integrations VALUES(?,?,?)',('payment:'+provider,json.dumps({'enabled':d['enabled'],'mode':d['mode']}),encrypted));integrations.audit(c,actor,'payment.settings.'+provider+'.'+action)

def paypal_auth(meta,keys):
 host='https://api-m.paypal.com' if meta['mode']=='live' else 'https://api-m.sandbox.paypal.com'
 auth=base64.b64encode((keys['client_id']+':'+keys['client_secret']).encode()).decode()
 token=request(host+'/v1/oauth2/token','POST',{'grant_type':'client_credentials'},{'Authorization':'Basic '+auth},True)['access_token']
 return host,{'Authorization':'Bearer '+token}

def start_checkout(c,db,uid,email,product_id,provider,brief):
 product=c.execute('SELECT * FROM products WHERE id=? AND active=1',(int(product_id),)).fetchone()
 if not product:raise ValueError('Product is unavailable')
 meta,keys=gateway(c,db,provider)
 if meta['mode']=='test' and c.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()['role']!='admin':raise ValueError('Sandbox checkout is restricted to administrators. Live payments are not yet enabled.')
 count=c.execute('SELECT count(*) FROM orders WHERE user_id=? AND created>?',(uid,time.time()-3600)).fetchone()[0]
 if count>=10:raise ValueError('Checkout limit reached. Use your existing pending orders or try later.')
 oid=secrets.token_urlsafe(24)
 c.execute('INSERT INTO orders(id,user_id,product_id,title,amount,currency,kind,digital_content,provider,mode,status,fulfillment,brief,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,uid,product['id'],product['title'],product['price'],'USD',product['kind'],product['digital_content'],provider,meta['mode'],'creating','not_started',str(brief)[:4000],time.time()))
 # Persist the order before the network call, including when the provider response is lost.
 c.commit()
 try:
  if provider=='stripe':
   fields={'mode':'payment','client_reference_id':oid,'success_url':BASE+'/checkout/return?order='+oid,'cancel_url':BASE+'/checkout/return?order='+oid,'customer_email':email,'line_items[0][quantity]':'1','line_items[0][price_data][currency]':'usd','line_items[0][price_data][unit_amount]':str(product['price']),'line_items[0][price_data][product_data][name]':product['title']}
   r=request('https://api.stripe.com/v1/checkout/sessions','POST',fields,{'Authorization':'Bearer '+keys['secret_key'],'Idempotency-Key':oid},True);pid=r['id'];url=r['url'];allowed=['checkout.stripe.com']
  else:
   host,headers=paypal_auth(meta,keys);headers['PayPal-Request-Id']=oid
   payload={'intent':'CAPTURE','purchase_units':[{'reference_id':oid,'custom_id':oid,'amount':{'currency_code':'USD','value':f"{product['price']/100:.2f}"}}],'application_context':{'return_url':BASE+'/checkout/return?order='+oid,'cancel_url':BASE+'/checkout/return?order='+oid,'user_action':'PAY_NOW'}}
   r=request(host+'/v2/checkout/orders','POST',payload,headers);pid=r['id'];url=next(x['href'] for x in r['links'] if x['rel']=='approve');allowed=['www.paypal.com','www.sandbox.paypal.com']
  if urlparse(url).scheme!='https' or urlparse(url).hostname not in allowed:raise ValueError('Unexpected provider checkout URL')
  c.execute("UPDATE orders SET provider_id=?,checkout_url=?,status='pending' WHERE id=?",(pid,url,oid))
 except Exception:
  c.execute("UPDATE orders SET status='checkout_error' WHERE id=?",(oid,));c.commit();raise
 return {'order_id':oid,'checkout_url':url,'mode':meta['mode']}

def verify(c,db,oid,uid=None,capture=False):
 row=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
 if not row or (uid is not None and row['user_id']!=uid):raise ValueError('Order not found')
 if row['status']=='paid':return {'paid':True,'order_id':oid}
 if not row['provider_id']:raise ValueError('Order has no checkout session. Review before starting another payment.')
 meta,keys=gateway(c,db,row['provider'],False)
 if meta['mode']!=row['mode']:raise ValueError('Order payment mode differs from current gateway. Administrator review required.')
 if row['provider']=='stripe':
  r=request('https://api.stripe.com/v1/checkout/sessions/'+quote(row['provider_id'],safe=''),headers={'Authorization':'Bearer '+keys['secret_key']})
  if r['id']!=row['provider_id'] or r.get('client_reference_id')!=oid or r.get('currency','').upper()!=row['currency'] or r.get('amount_total')!=row['amount'] or r.get('livemode',False)!=(row['mode']=='live'):raise ValueError('Payment reference, mode, amount or currency mismatch')
  paid=r.get('payment_status')=='paid';receipt=r.get('payment_intent')
 else:
  host,headers=paypal_auth(meta,keys);url=host+'/v2/checkout/orders/'+quote(row['provider_id'],safe='');r=request(url,headers=headers)
  if r.get('status')=='APPROVED' and capture:
   headers['PayPal-Request-Id']=oid+'-capture';r=request(url+'/capture','POST',{},headers)
  unit=r['purchase_units'][0];captures=unit.get('payments',{}).get('captures',[])
  if r['id']!=row['provider_id'] or unit.get('custom_id')!=oid or unit.get('reference_id')!=oid:raise ValueError('PayPal order reference mismatch')
  paid=r.get('status')=='COMPLETED' and len(captures)==1 and captures[0].get('status')=='COMPLETED'
  receipt=None
  if paid:
   cap=captures[0]
   if cap['amount']['currency_code']!=row['currency'] or Decimal(cap['amount']['value'])*100!=row['amount']:raise ValueError('PayPal amount or currency mismatch')
   receipt=cap['id']
 if paid:
  if not receipt:raise ValueError('Payment receipt missing')
  c.execute("UPDATE orders SET status='paid',paid=?,receipt=?,fulfillment=? WHERE id=? AND status!='paid'",(time.time(),receipt,'available' if row['kind']=='digital' else 'queued',oid))
 return {'paid':paid,'order_id':oid}

def stripe_webhook(c,db,body,signature):
 meta,keys=gateway(c,db,'stripe',False)
 parts=[p.split('=',1) for p in signature.split(',') if '=' in p];stamp=next((v for k,v in parts if k=='t'),'')
 if not stamp.isdigit() or abs(time.time()-int(stamp))>300:raise ValueError('Invalid webhook timestamp')
 digest=hmac.new(keys['webhook_secret'].encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
 if not any(k=='v1' and hmac.compare_digest(v,digest) for k,v in parts):raise ValueError('Invalid webhook signature')
 event=json.loads(body)
 if c.execute('SELECT 1 FROM payment_events WHERE id=?',(event['id'],)).fetchone():return
 if event['type'] in ['checkout.session.completed','checkout.session.async_payment_succeeded']:
  session=event['data']['object'];oid=session.get('client_reference_id');order=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
  if order:
   if order['provider']!='stripe' or session['id']!=order['provider_id']:raise ValueError('Webhook order mismatch')
   verify(c,db,oid)
 c.execute('INSERT INTO payment_events VALUES(?,?)',(event['id'],time.time()))

def public_orders(c,uid=None):
 sql='SELECT id,user_id,title,amount,currency,kind,provider,mode,checkout_url,status,fulfillment,brief,created,paid FROM orders'
 return [dict(r) for r in c.execute(sql+(' WHERE user_id=?' if uid is not None else '')+' ORDER BY created DESC LIMIT 200',(uid,) if uid is not None else ())]

def save_product(c,d,actor):
 title=str(d['title']).strip();price=int(d['price']);kind=d['kind'];active=d['active']
 if not title or len(title)>150 or not 100<=price<=1000000 or kind not in ['digital','service'] or not isinstance(active,bool):raise ValueError('Invalid product, price ($1–$10,000), or type')
 values=(title,str(d['category'])[:60],price,kind,str(d['description'])[:2000],str(d['delivery'])[:100],str(d.get('digital_content',''))[:20000],int(active))
 if kind=='digital' and not values[6].strip():raise ValueError('Digital products need downloadable text content')
 if d.get('id'):
  if not c.execute('SELECT 1 FROM products WHERE id=?',(int(d['id']),)).fetchone():raise ValueError('Product not found')
  c.execute('UPDATE products SET title=?,category=?,price=?,kind=?,description=?,delivery=?,digital_content=?,active=? WHERE id=?',(*values,int(d['id'])))
 else:c.execute('INSERT INTO products(title,category,price,kind,description,delivery,digital_content,active) VALUES(?,?,?,?,?,?,?,?)',values)
 integrations.audit(c,actor,'marketplace.product.save')
