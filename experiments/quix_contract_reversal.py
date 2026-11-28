"""Frozen target-reversal prompts for the four QuixBugs free-expression tasks."""
import argparse
import ast
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess
from analysis import quix_contract_reversal_report as study
from experiments import free_patch as core

prior,cli=core.prior,core.cli
PUBLIC=study.DEFAULT
PRIVATE=core.ROOT/'.local_private/quix_contract_reversal_20261128'
SEED=2026112806
DESIGN='docs/QUIX_CONTRACT_REVERSAL_20261128.md'
BOUND=(DESIGN,'experiments/quix_contract_reversal.py','analysis/quix_contract_reversal_report.py',
       'analysis/free_patch_20261128/sources.json','analysis/free_patch_20261128/upstream_check.json',*core.BOUND)


def materials():
    sources=prior.read(study.base.DEFAULT/'sources.json')
    study.base.check_upstream_receipt(study.base.calibration(sources),prior.read(study.base.DEFAULT/'upstream_check.json'))
    for task in sources['tasks'].values():
        if any(ast.get_docstring(ast.parse(state['source']).body[0]) is not None for state in task.values()):
            raise ValueError('A function docstring could specify the canonical target')
    cal=study.calibration(sources)
    rng=random.Random(SEED)
    names=list(study.RULES)
    rng.shuffle(names)
    combinations=[(m,s) for m in core.MODELS for s in ('faulty','working')]
    rng.shuffle(combinations)
    blocks=[]
    for wave in range(4):
        group=[]
        for i,task in enumerate(names):
            model,state=combinations[(i+wave)%4]
            # Interactions balance rule order within both each model and each task.
            first=(i+core.MODELS.index(model)+(state=='working'))%2
            rule_order=list(study.TARGETS if first==0 else reversed(study.TARGETS))
            b={'id':f'{model}_{task}_{state}','model':model,'start':state,'task':task,'wave':wave+1,
               'order':rng.sample(study.ARMS,3),'rule_order':rule_order}
            prompts={a:study.prompt(b,a,sources,cal) for a in study.ARMS}
            norm=[]
            for target in study.TARGETS:
                mark=(' requires output '+json.dumps(cal[task]['example'][target])+'.\n').encode()
                if prompts[target].count(mark)!=1:raise ValueError('Cannot isolate the required answer')
                norm.append(prompts[target].replace(mark,b' requires output [MASK].\n'))
            if norm[0]!=norm[1]:raise ValueError('Something other than target output changed')
            b['prompt_sha256']={a:prior.digest(v) for a,v in prompts.items()}
            group.append(b)
        rng.shuffle(group)
        blocks.extend(group)
    for field,values in [('model',core.MODELS),('task',names)]:
        for val in values:
            first=[b['rule_order'][0] for b in blocks if b[field]==val]
            if first.count('upstream')*2!=len(first):raise ValueError('Unbalanced rule order')
    plan={'seed':SEED,'design':DESIGN,'eligible_for_main_analysis':False,'effort':'low','included_window_end':core.RESET,
          'source_sha256':{f:cli.file_sha(core.ROOT/f) for f in BOUND},
          'calibration_sha256':prior.digest(prior.pretty(cal)),'blocks':blocks}
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
    print('Frozen 48 prompts',meta['plan_sha256'])


def load():
    plan,sources,cal=materials()
    meta=prior.read(PRIVATE/'frozen.json')
    if prior.pretty(plan)!=(PUBLIC/'plan.json').read_bytes() or meta['plan_sha256']!=cli.file_sha(PUBLIC/'plan.json') or prior.pretty(cal)!=(PUBLIC/'calibration.json').read_bytes():
        raise ValueError('Frozen files changed')
    return plan,sources,cal,meta


def outcome(b,arm,prompt,cal,meta):
    path=PRIVATE/'calls'/b['id']/arm
    row={'block':b['id'],**{k:b[k] for k in ('wave','task','start','model')},'arm':arm,'prompt_sha256':prior.digest(prompt),
         'status':'INTERRUPTED' if path.exists() else 'UNSTARTED','action':None,'expression':None,'implements':None,'passed_counts':None}
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
        counts,implements=study.grades(b['task'],expr,cal)
    except study.base.Rejected:
        return {**row,'status':'INVALID_EXPRESSION'}
    except (KeyError,TypeError,ValueError):
        return {**row,'status':'INVALID_RESPONSE'}
    return {**row,'status':'OK','action':obj['action'],'expression':expr,'implements':implements,'passed_counts':counts}


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
             'eligible_for_main_analysis':False,'rows':rows,'summary':study.summarize(rows,cal)}
    prior.persist(PUBLIC/'results.json',prior.pretty(results))
    text=study.verify()
    prior.persist(PUBLIC/'comparison.md',text.encode())
    print(text)


if __name__=='__main__':
    d={'freeze':freeze,'collect':collect,'export':export}
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=d)
    d[parser.parse_args().action]()
