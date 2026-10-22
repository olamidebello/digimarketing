"""Operator-managed Facebook Page connections. Tokens never leave the server API."""
import json,re,time,urllib.request,urllib.parse
import integrations

def request(config,token,path,fields=None):
    url='https://graph.facebook.com/'+config['version']+'/'+path
    body=urllib.parse.urlencode(fields).encode() if fields is not None else None
    req=urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
    except Exception:raise ValueError('Facebook request failed. Check Page token, permissions, expiry and provider status.') from None

def save(c,db,data,actor):
    uid=int(data['user_id'])
    if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise ValueError('User not found')
    name='facebook:'+str(uid);old,encrypted=integrations.record(c,name)
    page=str(data.get('page_id',''));version=str(data.get('version','v26.0'))
    if not re.fullmatch(r'[0-9]{5,30}',page) or not re.fullmatch(r'v[0-9]{1,3}\.0',version):raise ValueError('Numeric Page ID and Graph version required')
    if not isinstance(data.get('enabled'),bool):raise ValueError('Select publishing status')
    action=data.get('key_action','keep')
    if action=='replace':
        token=str(data.get('key','')).strip()
        if not 16<=len(token)<=8192 or any(x.isspace() for x in token):raise ValueError('Invalid Page token')
        encrypted=integrations.cipher(db).encrypt(token.encode())
    elif action=='remove':encrypted=None
    elif action!='keep':raise ValueError('Invalid token action')
    changed=not old or old['page_id']!=page or old['version']!=version or action!='keep'
    if old and old['page_id']!=page and action=='keep' and encrypted:raise ValueError('Replace the token when changing Page ID')
    verified=0 if changed else old.get('verified',0)
    if data['enabled'] and (not encrypted or not verified):raise ValueError('Save disabled, then verify the Page connection before enabling publishing')
    meta={'user_id':uid,'page_id':page,'version':version,'enabled':data['enabled'],'verified':verified,'page_name':old.get('page_name','') if old and not changed else '', 'updated':time.time()}
    c.execute('INSERT OR REPLACE INTO integrations VALUES(?,?,?)',(name,json.dumps(meta),encrypted));integrations.audit(c,actor,'facebook.settings.'+action,uid)

def verify(c,db,uid,actor):
    name='facebook:'+str(int(uid));meta,encrypted=integrations.record(c,name)
    if not meta or not encrypted:raise ValueError('Save a Page token first')
    token=integrations.cipher(db).decrypt(encrypted).decode()
    result=request(meta,token,'me?fields=id,name')
    if str(result.get('id'))!=meta['page_id']:raise ValueError('Token identity does not match the saved Page ID')
    meta.update(verified=time.time(),page_name=str(result.get('name',''))[:200])
    c.execute('UPDATE integrations SET metadata=? WHERE name=?',(json.dumps(meta),name));integrations.audit(c,actor,'facebook.verify',int(uid))

def public(c):
    return [{**json.loads(r['metadata']),'key_present':bool(r['encrypted'])} for r in c.execute("SELECT * FROM integrations WHERE name LIKE 'facebook:%'")]

def account(c,db,uid):
    meta,encrypted=integrations.record(c,'facebook:'+str(uid))
    if not meta or not meta['enabled'] or not meta.get('verified') or not encrypted:return {}
    return {'Facebook':{**meta,'access_token':integrations.cipher(db).decrypt(encrypted).decode()}}

def publish(config,content):
    if len(content)>60000:raise ValueError('Facebook post exceeds the supported text limit')
    result=request(config,config['access_token'],config['page_id']+'/feed',{'message':content})
    if not result.get('id'):raise ValueError('Facebook returned no post receipt. Review before retrying.')
    return str(result['id'])
