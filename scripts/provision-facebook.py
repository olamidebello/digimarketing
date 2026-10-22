"""Provision one existing workspace's Page using saved ciphertext or a root-only token file."""
import argparse,json,os,stat,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,facebook,integrations
from cryptography.fernet import InvalidToken

def provision(c,db,owner,page,version,enable=False,token=None):
    user=c.execute('SELECT id,role FROM users WHERE email=?',(owner.lower().strip(),)).fetchone()
    if not user or user['role']!='admin':raise ValueError('ADMIN_NOT_FOUND: The selected owner must be an existing super admin')
    uid=user['id'];old,encrypted=integrations.record(c,'facebook:'+str(uid))
    if token is None and not encrypted:raise ValueError('TOKEN_MISSING: Save a Page token in the GUI or supply a protected token file')
    changed=not old or old['page_id']!=page or old['version']!=version
    if token is not None:
        changed=changed or not encrypted or integrations.cipher(db).decrypt(encrypted).decode()!=token
    if changed:
        facebook.save(c,db,{'user_id':uid,'page_id':page,'version':version,'enabled':False,'key_action':'replace' if token is not None else 'keep','key':token},uid)
    meta,encrypted=integrations.record(c,'facebook:'+str(uid))
    # Verify every run, but persist a new verification only when configuration or identity changes.
    result=facebook.request(meta,integrations.cipher(db).decrypt(encrypted).decode(),'me?fields=id,name')
    if str(result.get('id'))!=page:raise ValueError('PAGE_ID_MISMATCH: Token belongs to a different Page or is a user token; save the correct Page token and Graph Page ID')
    verified_change=not meta.get('verified') or meta.get('page_name')!=str(result.get('name',''))[:200]
    if verified_change:
        import time
        meta.update(verified=time.time(),page_name=str(result.get('name',''))[:200])
        c.execute('UPDATE integrations SET metadata=? WHERE name=?',(json.dumps(meta),'facebook:'+str(uid)))
        integrations.audit(c,uid,'facebook.provision.verify',uid)
    if meta['enabled']!=enable:
        facebook.save(c,db,{'user_id':uid,'page_id':page,'version':version,'enabled':enable,'key_action':'keep'},uid);changed=True
    if changed:integrations.audit(c,uid,'facebook.provision',uid)
    return {'changed':bool(changed or verified_change),'page_id':page,'user_id':uid,'identity_verified':True,'publishing_enabled':enable}

def read_token(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd) as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077:raise ValueError('Token file must be a root-owned regular file with mode 0600')
        token=f.read(8194).strip()
        if not 16<=len(token)<=8192 or any(x.isspace() for x in token):raise ValueError('Token file must contain only a valid Page token')
        return token

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--owner',default='dobcalldemo@gmail.com');p.add_argument('--page',default='1448088625044064');p.add_argument('--version',default='v26.0');p.add_argument('--token-file');p.add_argument('--enable',action='store_true');args=p.parse_args()
    try:
        if not Path(app.DB).is_file():raise ValueError('DATABASE_MISSING: Deploy the application and create the super admin first')
        keypath=Path(os.getenv('DIGI_MASTER_KEY_FILE','/etc/digimarketing/master.key'))
        if not keypath.is_file():raise ValueError('MASTER_KEY_MISSING: Restore the original integration encryption key; do not generate a replacement')
        # Validate URL path inputs even when reusing an existing record.
        import re
        if not re.fullmatch(r'[0-9]{5,30}',args.page) or not re.fullmatch(r'v[0-9]{1,3}\.0',args.version):raise ValueError('Invalid Page ID or API version')
        token=read_token(args.token_file) if args.token_file else None
        with app.db() as c:
            c.execute('BEGIN IMMEDIATE')
            result=provision(c,app.DB,args.owner,args.page,args.version,args.enable,token)
        print(json.dumps(result))
    except Exception as exc:
        safe=['ADMIN_NOT_FOUND','TOKEN_MISSING','PAGE_ID_MISMATCH','DATABASE_MISSING','MASTER_KEY_MISSING','META_TOKEN_INVALID_OR_EXPIRED','META_PERMISSION_DENIED','META_INVALID_PAGE_OR_REQUEST','META_HTTP_ERROR','META_NETWORK_ERROR','META_RESPONSE_INVALID']
        code=str(exc).split(':',1)[0]
        if isinstance(exc,InvalidToken):code='TOKEN_DECRYPT_FAILED'
        if code not in safe+['TOKEN_DECRYPT_FAILED']:code='LOCAL_CONFIGURATION_ERROR'
        print(json.dumps({'changed':False,'error_code':code,'committed':False}));sys.exit(1)
