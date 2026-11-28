"""Freeze and collect free expressions for two source-bound maintenance cases."""
import argparse
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from analysis import production_patch_report as study
from experiments import free_patch as core

prior,cli=core.prior,core.cli
PUBLIC=study.DEFAULT
PRIVATE=core.ROOT/'.local_private/production_patch_20261128'
DESIGN='docs/PRODUCTION_PATCH_20261128.md'
SEED=2026112805
BOUND=(DESIGN,'experiments/production_patch.py','analysis/production_patch_report.py',*core.BOUND)
HASHES={
    'matplotlib':{'faulty':'d3aa55854960e9c9063102c6b8bd9afc954fd288f65e56be8715fad7bf3ad2b1','working':'f094a2d41b8b5da475ad94e546ee4ddc5dcb01f85799c9b9653e5314fcd70e58'},
    'tqdm':{'faulty':'205b5254a0cb1b7c2f86362a2b49cc39e125a50adb023ec02b398fb7a638ca77','working':'a1945e32fc8264d4b09a1da2eea2fcb22ef6b3f52107f8eecaa50d6fd48f6438'}}
AXIS_FIXTURE="""
from types import SimpleNamespace
def run(args):
    a,b,x,y=args
    get,set_=_make_getset_interval('view','fixture','endpoints')
    axis=SimpleNamespace(axes=SimpleNamespace(fixture=SimpleNamespace(endpoints=(a,b))))
    set_(axis,x,y)
    return {'output':list(get(axis)),'wrapped':None}
"""
ENUM_FIXTURE="""
def run(args):
    items,start=args
    wrappers=[]
    class Progress:
        def __init__(self, seq, *ignored, **options):
            self.seq,self.options,self.visited=seq,options,False
            wrappers.append(self)
        def __iter__(self):
            self.visited=True
            return iter(self.seq)
    output=list(tenumerate(items,start=start,tqdm_class=Progress, disable=True))
    wrapped=len(wrappers)==1 and wrappers[0].visited and wrappers[0].seq is items and wrappers[0].options=={'disable':True}
    return {'output':output,'wrapped':wrapped}
"""


def audit_upstream():
    sources=prior.read(PUBLIC/'sources.json')
    receipt={}
    for name,card in sources.items():
        receipt[name]={}
        api=card['repository'].replace('github.com/','api.github.com/repos/')+'/commits/'+card['fixed']
        commit=json.load(urllib.request.urlopen(api,timeout=20))
        if [c['sha'] for c in commit['parents']]!=[card['parent']]:
            raise ValueError('The control must be the direct maintainer commit')
        testpatch=next(f['patch'] for f in commit['files'] if f['filename']==card['test_path'])
        if card['fix_test_diff']!=testpatch:raise ValueError('Maintainer test patch differs')
        for st,v in card['versions'].items():
            rev=card['parent' if st=='faulty' else 'fixed']
            raw=card['repository'].replace('github.com','raw.githubusercontent.com')+'/'+rev+'/'
            data=urllib.request.urlopen(raw+card['source_path'],timeout=20).read()
            if prior.digest(data)!=v['file_sha256'] or v['file_sha256']!=HASHES[name][st]:
                raise ValueError('Full upstream source bytes differ')
            test_bytes=urllib.request.urlopen(raw+card['test_path'],timeout=20).read()
            if prior.digest(test_bytes)!=v['test_file_sha256']:
                raise ValueError('Upstream test bytes differ')
            lines=data.decode().splitlines()
            i=v['first_line']-1
            code=v['function_source']
            if lines[i:i+len(code.splitlines())]!=code.splitlines():
                raise ValueError('Function not present at recorded line')
            fixture=AXIS_FIXTURE if name=='matplotlib' else ENUM_FIXTURE
            script='tqdm_auto=None\n'+code+'\n'+fixture+'\nimport json,sys\nprint(json.dumps([run(a) for a in json.load(sys.stdin)]))\n'
            args=study.all_inputs(name)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'test_upstream.py'
                path.write_text(script)
                outputs=json.loads(subprocess.check_output([sys.executable,'-I','-S',str(path)],input=json.dumps(args).encode(),timeout=10))
            receipt[name][st]={'inputs':len(args),'outputs_sha256':study.base.output_digest(outputs)}
    study.check_native(study.calibration(sources),receipt)
    prior.persist(PUBLIC/'upstream_check.json',prior.pretty(receipt))


def materials():
    sources=prior.read(PUBLIC/'sources.json')
    cal=study.calibration(sources)
    study.check_native(cal,prior.read(PUBLIC/'upstream_check.json'))
    rng=random.Random(SEED)
    groups=[]
    for n,name in enumerate(study.NAMES):
        for m,model in enumerate(core.MODELS):
            for s,st in enumerate(('faulty','working')):
                wave=1+(n+m+s)%2
                arms=list(study.ARMS)
                rng.shuffle(arms)
                b={'id':f'{model}_{name}_{st}','wave':wave,'task':name,'start':st,'model':model,'order':arms}
                b['prompt_sha256']={a:prior.digest(study.prompt(b,a,sources,cal)) for a in arms}
                groups.append(b)
    rng.shuffle(groups)
    plan={'seed':SEED,'design':DESIGN,'eligible_for_main_analysis':False,'effort':'low','included_window_end':core.RESET,
          'source_sha256':{f:cli.file_sha(core.ROOT/f) for f in BOUND},'sources_sha256':cli.file_sha(PUBLIC/'sources.json'),
          'upstream_check_sha256':cli.file_sha(PUBLIC/'upstream_check.json'),'calibration_sha256':prior.digest(prior.pretty(cal)),
          'blocks':sorted(groups,key=lambda b:b['wave'])}
    return plan,sources,cal


def freeze():
    plan,_,cal=materials()
    exe=str(Path(shutil.which('codex')).resolve())
    login=subprocess.run([exe,'login','status'],capture_output=True,text=True,check=True,env=cli.child_environment('codex'))
    if 'logged in using chatgpt' not in (login.stdout+login.stderr).lower():raise ValueError('Subscription login required')
    prior.persist(PUBLIC/'plan.json',prior.pretty(plan))
    prior.persist(PUBLIC/'calibration.json',prior.pretty(cal))
    meta={'plan_sha256':cli.file_sha(PUBLIC/'plan.json'),'launcher':exe,'launcher_sha256':cli.file_sha(Path(exe)),
          'version':subprocess.check_output([exe,'--version'],text=True).strip(),'auth':'CHATGPT_LOGIN'}
    path=PRIVATE/'frozen.json'
    if path.exists():
        if any(prior.read(path)[k]!=v for k,v in meta.items()):raise ValueError('Different frozen launcher')
    else:cli.record(path,{**meta,'utc':cli.now()})
    print('Frozen 24 prompts',meta['plan_sha256'])


def load():
    plan,sources,cal=materials()
    meta=prior.read(PRIVATE/'frozen.json')
    if prior.pretty(plan)!=(PUBLIC/'plan.json').read_bytes() or meta['plan_sha256']!=cli.file_sha(PUBLIC/'plan.json') or prior.pretty(cal)!=(PUBLIC/'calibration.json').read_bytes():
        raise ValueError('Frozen files changed')
    return plan,sources,cal,meta


def outcome(b,arm,prompt,cal,meta):
    path=PRIVATE/'calls'/b['id']/arm
    row={'block':b['id'],**{k:b[k] for k in ('wave','task','start','model')},'arm':arm,'prompt_sha256':prior.digest(prompt),
         'status':'INTERRUPTED' if path.exists() else 'UNSTARTED','action':None,'expression':None,'passes':None,'passed_count':None}
    if not (path/'process.json').exists():
        return row
    proc=prior.read(path/'process.json')
    launch=prior.read(path/'start.json')
    if launch['argv']!=prior.command_for(meta['launcher'],b['model']) or launch['prompt_sha256']!=row['prompt_sha256'] or launch['block']!=b['id'] or launch['arm']!=arm or prompt!=(path/'prompt.txt').read_bytes():
        raise ValueError('Native assignment differs')
    raw=(path/'stdout.bin').read_bytes()
    err=(path/'stderr.bin').read_bytes()
    if proc['stdout_sha256']!=prior.digest(raw) or proc['stderr_sha256']!=prior.digest(err):
        raise ValueError('Native response changed')
    row.update(native_response_sha256=prior.digest(raw),elapsed_seconds=proc['elapsed_seconds'])
    if proc['error'] or proc['returncode']:
        row['status']=prior.codex.failure_kind([(raw+err).decode(errors='replace')],proc['error'] or 'CLI_ERROR')
        return row
    try:
        msg,_=cli.extract('codex',raw)
        obj=cli.base.strict(msg)
        if obj=={'action':'keep'}:
            expr=cal[b['task']]['starts'][b['start']]['expression']
        elif isinstance(obj,dict) and set(obj)=={'action','expression'} and obj['action']=='replace':
            expr=obj['expression']
        else:raise ValueError('Unexpected response')
        checks=study.grade(b['task'],expr,cal[b['task']]['held'])
    except study.base.Rejected:
        return {**row,'status':'INVALID_EXPRESSION'}
    except (KeyError,TypeError,ValueError):
        return {**row,'status':'INVALID_RESPONSE'}
    return {**row,'status':'OK','action':obj['action'],'expression':expr,'passes':all(checks),'passed_count':sum(checks)}


def collect():
    plan,sources,cal,meta=load()
    if cli.file_sha(Path(meta['launcher']))!=meta['launcher_sha256']:raise ValueError('Frozen launcher changed')
    with (core.QUOTA/'native.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for b in plan['blocks']:
            for arm in b['order']:
                path=PRIVATE/'calls'/b['id']/arm
                prompt=study.prompt(b,arm,sources,cal)
                if not path.exists():
                    prior.check_memory()
                    core.require_remaining()
                    argv=prior.command_for(meta['launcher'],b['model'])
                    path.mkdir(parents=True,mode=0o700)
                    cli.write(path/'prompt.txt',prompt)
                    cli.record(path/'start.json',{'utc':cli.now(),'argv':argv,'block':b['id'],'arm':arm,'prompt_sha256':prior.digest(prompt)})
                    cli.record(path/'process.json',cli._launch(argv,prompt,path,'codex',prior.TIMEOUT))
                row=outcome(b,arm,prompt,cal,meta)
                if row['status']!='INTERRUPTED':
                    prior.persist(path/'event.json',prior.pretty(row))
                print(b['wave'],b['id'],arm,row['status'],flush=True)
                if row['status'] in prior.codex.ACCOUNT_ERRORS or row['status']=='MODEL_UNAVAILABLE':
                    raise RuntimeError(row['status'])


def export():
    plan,sources,cal,meta=load()
    rows=[]
    for b in plan['blocks']:
        for arm in b['order']:
            row=outcome(b,arm,study.prompt(b,arm,sources,cal),cal,meta)
            if row['status'] not in ('UNSTARTED','INTERRUPTED') and row!=prior.read(PRIVATE/'calls'/b['id']/arm/'event.json'):
                raise ValueError('Native replay differs')
            rows.append(row)
    results={'plan_sha256':meta['plan_sha256'],'frozen_at_utc':meta['utc'],'cli_version':meta['version'],
             'eligible_for_main_analysis':False,'rows':rows,'summary':study.base.summarize(rows,cal)}
    prior.persist(PUBLIC/'results.json',prior.pretty(results))
    text=study.verify()
    prior.persist(PUBLIC/'comparison.md',text.encode())
    print(text)


if __name__=='__main__':
    d={'freeze':freeze,'collect':collect,'export':export,'audit-upstream':audit_upstream}
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=d)
    d[parser.parse_args().action]()
