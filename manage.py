"""Run on the server as the service user with DIGI_DB configured."""
import argparse, getpass, sqlite3
import app
p=argparse.ArgumentParser(); p.add_argument('action',choices=['create-admin']); p.add_argument('email'); args=p.parse_args()
secret=getpass.getpass('New admin password (12+ characters): ')
if len(secret)<12: raise SystemExit('Use at least 12 characters')
app.init()
with app.db() as c:
    try: c.execute('INSERT INTO users(email,password,role) VALUES(?,?,?)',(args.email.lower().strip(),app.password(secret),'admin'))
    except sqlite3.IntegrityError: raise SystemExit('Account exists; refusing to overwrite it. Review account ownership before promotion.')
print('Administrator created.')
