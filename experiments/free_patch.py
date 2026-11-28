"""Collect a frozen expression-authoring comparison on pinned QuixBugs tasks."""
import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

from analysis import free_patch_report as study
from experiments import checker_timing_pilot as prior

ROOT, cli = prior.ROOT, prior.cli
PUBLIC=study.DEFAULT
PRIVATE=ROOT/'.local_private/free_patch_20261128'
QUOTA=ROOT/'.local_private/feedback_cycle_quota'
MODELS=('gpt-6-luna','gpt-6.2-astra')
SEED=2026112804
RESET=1795890789
DESIGN='docs/FREE_PATCH_20261128.md'
BOUND=(DESIGN,'experiments/free_patch.py','analysis/free_patch_report.py',
       'experiments/checker_timing_pilot.py','experiments/c5_cli_pilot.py','experiments/c5_codex_effort.py','experiments/c5_evidence_challenge.py')


def materials():
    sources=prior.read(PUBLIC/'sources.json')
    cal=study.calibration(sources)
    rng=random.Random(SEED)
    names=list(study.TASKS)
    rng.shuffle(names)
    combinations=[(m,s) for m in MODELS for s in ('faulty','working')]
    rng.shuffle(combinations)
    order=list(study.ARMS)
    rng.shuffle(order)
    blocks=[]
    for wave in range(4):
        cohort=[]
        for index, name in enumerate(names):
            model, state=combinations[(index+wave)%4]
            start=(index+wave)%3
            positions=order[start:]+order[:start]
            block={'id':f"{model}_{name}_{state}",'task':name,'start':state,'model':model,'wave':wave+1,'order':positions}
            block['prompt_sha256']={arm:prior.digest(study.prompt(block,arm,sources,cal)) for arm in study.ARMS}
            cohort.append(block)
        rng.shuffle(cohort)
        blocks.extend(cohort)
    plan={'seed':SEED,'design':DESIGN,'effort':'low','eligible_for_main_analysis':False,
          'included_window_end':RESET,'sources_sha256':cli.file_sha(PUBLIC/'sources.json'),
          'source_sha256':{name:cli.file_sha(ROOT/name) for name in BOUND},
          'calibration_sha256':prior.digest(prior.pretty(cal)),
          'upstream_check_sha256':cli.file_sha(PUBLIC/'upstream_check.json'),'blocks':blocks}
    return plan,sources,cal


def audit_upstream(checkout):
    """Only the original, commit-addressed QuixBugs files run here, never a model response."""
    import tempfile
    sources=prior.read(PUBLIC/'sources.json')
    revision='4257f44b0ff1181dedaedee6a447e133219fcebf'
    if sources['revision']!=revision:
        raise ValueError('Upstream revision drifted')
    cal=study.calibration(sources)
    result={}
    with tempfile.TemporaryDirectory() as folder:
        testfile=Path(folder)/'native_quixbugs_case.py'
        for task, records in sources['tasks'].items():
            result[task]={}
            args=[case['input'] for case in cal[task]['held']]+[study.TASKS[task]['shared'],study.TASKS[task]['revealing']]
            for state, source in records.items():
                subdir='python_programs' if state=='faulty' else 'correct_python_programs'
                blob=subprocess.check_output(['git','-C',str(checkout),'show',f'{revision}:{subdir}/{task}.py'])
                if prior.digest(blob)!=source['sha256'] or blob.decode()!=source['source']:
                    raise ValueError('Upstream program bytes differ')
                harness=f"\nimport json, sys\nprint(json.dumps([{task}(*v) for v in json.load(sys.stdin)]))\n"
                testfile.write_bytes(blob+harness.encode())
                native=subprocess.check_output([sys.executable,'-I',str(testfile)],input=json.dumps(args).encode(),timeout=12)
                result[task][state]={'inputs':len(args),'outputs_sha256':study.output_digest(json.loads(native))}
    study.check_upstream_receipt(cal,result)
    prior.persist(PUBLIC/'upstream_check.json',prior.pretty(result))


def freeze():
    plan,_,cal=materials()
    study.check_upstream_receipt(cal,prior.read(PUBLIC/'upstream_check.json'))
    program=str(Path(shutil.which('codex')).resolve())
    auth=subprocess.run([program,'login','status'],capture_output=True,text=True,check=True,env=cli.child_environment('codex'))
    if 'logged in using chatgpt' not in (auth.stdout+auth.stderr).lower():
        raise ValueError('Subscription login required')
    prior.persist(PUBLIC/'plan.json',prior.pretty(plan))
    prior.persist(PUBLIC/'calibration.json',prior.pretty(cal))
    meta={'plan_sha256':cli.file_sha(PUBLIC/'plan.json'),'launcher':program,'launcher_sha256':cli.file_sha(Path(program)),
          'version':subprocess.check_output([program,'--version'],text=True).strip(),'auth':'CHATGPT_LOGIN'}
    path=PRIVATE/'frozen.json'
    if path.exists():
        if any(prior.read(path)[k]!=v for k,v in meta.items()):
            raise ValueError('Different frozen launcher')
    else:
        cli.record(path,{**meta,'utc':cli.now()})
    print('Frozen 48 prompts',meta['plan_sha256'])


def load():
    plan,sources,cal=materials()
    meta=prior.read(PRIVATE/'frozen.json')
    if prior.pretty(plan)!=(PUBLIC/'plan.json').read_bytes() or prior.pretty(cal)!=(PUBLIC/'calibration.json').read_bytes() or meta['plan_sha256']!=cli.file_sha(PUBLIC/'plan.json'):
        raise ValueError('Frozen design drifted')
    return plan,sources,cal,meta


def outcome(b,arm,sources,cal,meta):
    path=PRIVATE/'calls'/b['id']/arm
    prompt=study.prompt(b,arm,sources,cal)
    row={'block':b['id'],**{k:b[k] for k in ('wave','model','task','start')},'arm':arm,
         'prompt_sha256':prior.digest(prompt),'status':'INTERRUPTED' if path.exists() else 'UNSTARTED',
         'expression':None,'action':None,'passes':None,'passed_count':None}
    if not (path/'process.json').exists():
        return row
    init=prior.read(path/'start.json')
    if (init['argv']!=prior.command_for(meta['launcher'],b['model']) or init['arm']!=arm or init['block']!=b['id']
            or init['prompt_sha256']!=row['prompt_sha256'] or prompt!=(path/'prompt.txt').read_bytes()):
        raise ValueError('Native prompt differs from assignment')
    proc=prior.read(path/'process.json')
    raw=(path/'stdout.bin').read_bytes()
    err=(path/'stderr.bin').read_bytes()
    if prior.digest(raw)!=proc['stdout_sha256'] or prior.digest(err)!=proc['stderr_sha256']:
        raise ValueError('Native capture differs')
    row.update(native_response_sha256=prior.digest(raw),elapsed_seconds=proc['elapsed_seconds'])
    if proc['error'] or proc['returncode']:
        row['status']=prior.codex.failure_kind([(raw+err).decode(errors='replace')],proc['error'] or 'CLI_ERROR')
        return row
    try:
        message,_=cli.extract('codex',raw)
        obj=cli.base.strict(message)
        if obj=={'action':'keep'}:
            text=cal[b['task']]['starts'][b['start']]['expression']
        elif isinstance(obj,dict) and set(obj)=={'action','expression'} and obj['action']=='replace':
            text=obj['expression']
        else:
            raise ValueError('Unknown action')
        passed=study.grade(b['task'],text,cal[b['task']]['held'])
    except study.Rejected:
        return {**row,'status':'INVALID_EXPRESSION'}
    except (ValueError, KeyError, TypeError):
        return {**row,'status':'INVALID_RESPONSE'}
    return {**row,'status':'OK','action':obj['action'],'expression':text,'passes':all(passed),'passed_count':sum(passed)}


def require_remaining():
    if time.time()+prior.TIMEOUT+5>=RESET:
        raise RuntimeError('WINDOW_END')
    snap=json.loads(subprocess.check_output([sys.executable,str(QUOTA/'read.py')],text=True,timeout=35))
    buckets=snap['windows']
    w=buckets.get('codex')
    limits=[w[key] for key in ('primary','secondary') if w and key in w]
    weekly=[entry for entry in limits if entry['windowDurationMins']==10080]
    if snap['included_allowed'] is not True or len(weekly)!=1 or weekly[0]['resetsAt']!=RESET:
        raise RuntimeError('INCLUDED_WINDOW_UNAVAILABLE')
    if w.get('reason') or any(entry['usedPercent']>=100 for entry in limits):
        raise RuntimeError('ACCOUNT_QUOTA')


def collect(max_waves):
    plan,sources,cal,meta=load()
    if cli.file_sha(Path(meta['launcher']))!=meta['launcher_sha256']:
        raise ValueError('Launcher drifted')
    with (QUOTA/'native.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for b in plan['blocks']:
            if b['wave']>max_waves:
                return
            for arm in b['order']:
                path=PRIVATE/'calls'/b['id']/arm
                if not path.exists():
                    prior.check_memory()
                    require_remaining()
                    prompt=study.prompt(b,arm,sources,cal)
                    argv=prior.command_for(meta['launcher'],b['model'])
                    path.mkdir(parents=True,mode=0o700)
                    cli.write(path/'prompt.txt',prompt)
                    cli.record(path/'start.json',{'argv':argv,'block':b['id'],'arm':arm,'utc':cli.now(),'prompt_sha256':prior.digest(prompt)})
                    proc=cli._launch(argv,prompt,path,'codex',prior.TIMEOUT)
                    cli.record(path/'process.json',proc)
                row=outcome(b,arm,sources,cal,meta)
                if row['status']!='INTERRUPTED':
                    prior.persist(path/'event.json',prior.pretty(row))
                print(b['wave'],b['task'],b['model'],arm,row['status'],flush=True)
                if row['status'] in prior.codex.ACCOUNT_ERRORS or row['status']=='MODEL_UNAVAILABLE':
                    raise RuntimeError(row['status'])


def export():
    plan,sources,cal,meta=load()
    rows=[]
    for b in plan['blocks']:
        for arm in b['order']:
            row=outcome(b,arm,sources,cal,meta)
            if row['status'] not in ('UNSTARTED','INTERRUPTED') and row!=prior.read(PRIVATE/'calls'/b['id']/arm/'event.json'):
                raise ValueError('Native outcome changed')
            rows.append(row)
    results={'plan_sha256':meta['plan_sha256'],'frozen_at_utc':meta['utc'],'cli_version':meta['version'],
             'eligible_for_main_analysis':False,'rows':rows,'summary':study.summarize(rows,cal)}
    prior.persist(PUBLIC/'results.json',prior.pretty(results))
    report=study.verify()
    prior.persist(PUBLIC/'comparison.md',report.encode())
    print(report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('audit-upstream','freeze','collect','export'))
    p.add_argument('--waves',type=int,choices=range(1,5),default=4)
    p.add_argument('--checkout',type=Path)
    args=p.parse_args()
    if args.action=='collect':
        collect(args.waves)
    elif args.action=='audit-upstream':
        if not args.checkout:
            p.error('--checkout must name the pinned QuixBugs repository')
        audit_upstream(args.checkout)
    elif args.action=='freeze':
        freeze()
    else:
        export()
