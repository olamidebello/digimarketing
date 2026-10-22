"""Encrypted operator-managed provider configuration. Never returns plaintext credentials."""
import os,json,hashlib,re,time,secrets
from pathlib import Path
from cryptography.fernet import Fernet

def cipher(db_path):
    path=Path(os.getenv('DIGI_MASTER_KEY_FILE',str(Path(db_path).parent/'master.key')))
    if not path.exists():
        if os.getenv('DIGI_DEV')!='1':raise ValueError('Integration encryption key is missing. Run the latest deployment first.')
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
        except FileExistsError:pass
    return Fernet(path.read_bytes().strip())

def record(c,name):
    row=c.execute('SELECT * FROM integrations WHERE name=?',(name,)).fetchone()
    return (json.loads(row['metadata']),row['encrypted']) if row else (None,None)

def ai(c,db_path):
    meta,encrypted=record(c,'openai')
    meta=meta or {'enabled':True,'model':os.getenv('OPENAI_MODEL',''),'source':'environment','hourly_quota':20}
    key=(os.getenv('OPENAI_API_KEY','') if meta.get('source')=='environment' else (cipher(db_path).decrypt(encrypted).decode() if encrypted else ''))
    return meta,key

def public_ai(c,db_path):
    meta,key=ai(c,db_path)
    return {**meta,'key_present':bool(key),'ready':bool(meta['enabled'] and key and meta['model']),'fingerprint':hashlib.sha256(key.encode()).hexdigest()[:12] if key else None}

def save_ai(c,db_path,data,actor):
    old,encrypted=record(c,'openai');old=old or {'source':'environment'}
    action=data.get('key_action','keep');source=old.get('source','environment')
    if action=='replace':
        key=str(data.get('key','')).strip()
        if not 16<=len(key)<=1024 or any(ch.isspace() for ch in key):raise ValueError('Enter a valid provider key without whitespace.')
        encrypted=cipher(db_path).encrypt(key.encode());source='vault'
    elif action=='remove':encrypted=None;source='none'
    elif action=='environment':encrypted=None;source='environment'
    elif action!='keep':raise ValueError('Unknown key action')
    model=str(data.get('model','')).strip();quota=int(data.get('hourly_quota',20))
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,120}',model) or not 1<=quota<=100:raise ValueError('Model and hourly limit (1–100) are required.')
    if not isinstance(data.get('enabled'),bool):raise ValueError('Choose enabled or disabled.')
    meta={'enabled':data['enabled'],'model':model,'source':source,'hourly_quota':quota,'updated':time.time()}
    c.execute('INSERT OR REPLACE INTO integrations VALUES(?,?,?)',('openai',json.dumps(meta),encrypted))
    audit(c,actor,'ai.settings.'+action)

def social(c,db_path,uid):
    meta,encrypted=record(c,'mastodon:'+str(uid))
    if meta is None:return None
    return {'Mastodon':{'instance':meta['instance'],'access_token':cipher(db_path).decrypt(encrypted).decode()}} if meta['enabled'] and encrypted else {}

def save_social(c,db_path,data,actor):
    uid=int(data['user_id'])
    if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise ValueError('User not found')
    name='mastodon:'+str(uid);old,encrypted=record(c,name);action=data.get('key_action','keep')
    if action=='environment':
        c.execute('DELETE FROM integrations WHERE name=?',(name,));audit(c,actor,'social.server_file',uid);return
    instance=str(data.get('instance','')).rstrip('/')
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+',instance):raise ValueError('Enter the authorized Mastodon HTTPS instance without a path.')
    if not isinstance(data.get('enabled'),bool):raise ValueError('Choose enabled or disabled.')
    if action=='keep' and old and old.get('instance')!=instance and encrypted:raise ValueError('Replace the token when changing its instance; stored tokens are not forwarded to a different host.')
    if action=='replace':
        token=str(data.get('key','')).strip()
        if not 8<=len(token)<=4096 or any(ch.isspace() for ch in token):raise ValueError('Invalid token')
        encrypted=cipher(db_path).encrypt(token.encode())
    elif action=='remove':encrypted=None
    elif action!='keep':raise ValueError('Unknown token action')
    meta={'user_id':uid,'instance':instance,'enabled':data['enabled'],'updated':time.time()}
    c.execute('INSERT OR REPLACE INTO integrations VALUES(?,?,?)',(name,json.dumps(meta),encrypted));audit(c,actor,'social.settings.'+action,uid)

def public_social(c):
    return [{**json.loads(r['metadata']),'key_present':bool(r['encrypted'])} for r in c.execute("SELECT * FROM integrations WHERE name LIKE 'mastodon:%'")]

def audit(c,actor,action,target=None):
    c.execute('INSERT INTO integration_audit(actor,action,target,created) VALUES(?,?,?,?)',(actor,action,target,time.time()))
