"""Print only included-quota windows and permission, never account identity or credentials."""
import subprocess, json, sys, signal
from datetime import datetime, timezone
signal.alarm(28)
p=subprocess.Popen([sys.argv[1],'app-server','--listen','stdio://'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
def send(obj):
    p.stdin.write(json.dumps(obj)+'\n')
    p.stdin.flush()
def read(i):
    for line in p.stdout:
        item=json.loads(line)
        if item.get('id')==i:
            if 'error' in item: raise RuntimeError(item['error'].get('code'))
            return item['result']
    raise RuntimeError('App server exited')
try:
    send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'research-quota-observer','version':'1','title':None},'capabilities':None}})
    read(1)
    send({'method':'initialized'})
    send({'id':2,'method':'account/rateLimits/read','params':{}})
    r=read(2)
    output={'utc':datetime.now(timezone.utc).isoformat(),'included_allowed':r.get('ordinaryUsageAllowed'),'windows':{}}
    for name,bucket in (r.get('rateLimitsByLimitId') or {'codex':r['rateLimits']}).items():
        output['windows'][name]={k:{f:w.get(f) for f in ('usedPercent','windowDurationMins','resetsAt')} for k in ('primary','secondary') if (w:=bucket.get(k))}
        output['windows'][name]['reason']=bucket.get('rateLimitReachedType')
    print(json.dumps(output))
finally:
    p.terminate()
