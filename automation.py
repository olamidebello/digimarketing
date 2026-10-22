"""Bounded campaign batch runner for Ansible. No shell execution of campaign data."""
import argparse,json,time
import app

def run_batch(max_jobs=None,dry_run=False,max_seconds=120):
    app.init()
    limits=app.automation_limits();size=min(max_jobs or limits['batch_size'],limits['batch_size'])
    if not 1<=size<=100:raise ValueError('Batch must contain 1–100 jobs')
    if dry_run:
        with app.db() as c:due=c.execute("SELECT count(*) FROM campaigns WHERE status='scheduled' AND due<=?",(time.time(),)).fetchone()[0]
        return {'dry_run':True,'due':due,'batch_limit':size}
    started=time.time();processed=0
    with app.db() as c:rid=c.execute("INSERT INTO batch_runs(started,status) VALUES(?,'running')",(started,)).lastrowid
    try:
        while processed<size and time.time()-started<max_seconds:
            if not app.tick():break
            processed+=1
    except Exception:
        with app.db() as c:c.execute("UPDATE batch_runs SET finished=?,processed=?,status='failed' WHERE id=?",(time.time(),processed,rid))
        raise
    with app.db() as c:c.execute("UPDATE batch_runs SET finished=?,processed=?,status='complete' WHERE id=?",(time.time(),processed,rid))
    return {'run_id':rid,'processed':processed,'batch_limit':size,'status':'complete'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--max-jobs',type=int);p.add_argument('--dry-run',action='store_true');args=p.parse_args()
    print(json.dumps(run_batch(args.max_jobs,args.dry_run)))
