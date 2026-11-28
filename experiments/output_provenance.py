"""Compare labels on identical output values under a locally frozen subscription protocol."""
import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess
import time

from experiments import c5_cli_pilot as cli
from experiments import checker_timing_pilot as prior
from experiments import feedback_factorial as factorial
from experiments import output_provenance_tasks as tasks
from experiments.reference_example_control import other

ROOT = prior.ROOT
PUBLIC = ROOT/'analysis/output_provenance_20261128'
PRIVATE = ROOT/'.local_private/output_provenance_20261128'
DESIGN = 'docs/OUTPUT_PROVENANCE_20261128.md'
SOURCES = (DESIGN,'experiments/output_provenance.py','experiments/output_provenance_tasks.py',
           'experiments/feedback_factorial.py','experiments/c5_cli_pilot.py','experiments/c5_codex_effort.py',
           'experiments/checker_timing_pilot.py','experiments/c5_evidence_challenge.py','experiments/reference_example_control.py')
MODELS = ('gpt-6-luna','gpt-6.2-astra','gpt-6.2-sol','gpt-6.1-terra')
LABELS = ('required','anonymous','named')
SEED = 2026112804


def prompt(task_name, start, label, value):
    task = tasks.TASKS[task_name]
    source, alternative = task['code'] if start == 'A' else reversed(task['code'])
    diagnostic = task['diagnostic']
    lines = [task['description'], 'Exactly one of the implementations matches this installation.',
             'Current implementation:', 'def solve(x):','    '+source,
             'Alternative implementation:', 'def solve(x):','    '+alternative,
             'Diagnostic input: '+json.dumps(diagnostic[0])]
    if label != 'none':
        who = 'current' if start == value else 'alternative'
        caption = {'required':'Required output of the target installation',
                   'anonymous':'Observed output of one of the two candidate implementations',
                   'named':f'Observed output of the {who} implementation'}[label]
        lines.append(caption + ': ' + json.dumps(diagnostic[1 + int(value == 'B')]))
    lines.append('You have one decision. Keep the current implementation or switch to the alternative. '
                 'Return only one JSON object {"action":"keep"} or {"action":"switch"}. No tools or explanation.')
    return ('\n'.join(lines)+'\n').encode()


def materials():
    cal = tasks.calibrate()
    rng = random.Random(SEED)
    roster = list(tasks.TASKS)
    models = list(MODELS)
    rng.shuffle(roster)
    rng.shuffle(models)
    blocks = []
    for wave in range(8):
        members = []
        for i, task in enumerate(roster):
            model = models[(i+wave) % 4]
            start = ('A','B')[(i//4+wave//4) % 2]
            block = {'id': f'{model}_{task}_{start}', 'wave':wave+1, 'task':task,'start':start,'model':model,'calls':[]}
            for label, value in [('none',None)] + [(label,v) for label in LABELS for v in ('A','B')]:
                data = prompt(task,start,label,value)
                block['calls'].append({'id':label if value is None else f'{label}_{value}','label':label,
                                       'value_contract':value,'targets':[value] if label=='required' else ['A','B'],
                                       'prompt_sha256':prior.digest(data)})
            rng.shuffle(block['calls'])
            members.append(block)
        rng.shuffle(members)
        blocks.extend(members)
    if len({b['id'] for b in blocks}) != 64:
        raise ValueError('Duplicate model–task–start block')
    plan = {'design':DESIGN,'seed':SEED,'effort':'low','eligible_for_main_analysis':False,'blocks':blocks,
            'calibration_sha256':prior.digest(prior.pretty(cal)), 'source_sha256': {p:cli.file_sha(ROOT/p) for p in SOURCES}}
    return plan, cal


def freeze():
    plan, cal = materials()
    launcher = str(Path(shutil.which('codex')).resolve())
    auth = subprocess.run([launcher, 'login', 'status'], capture_output=True, text=True, check=True,
                          env=cli.child_environment('codex'))
    if 'logged in using chatgpt' not in (auth.stdout + auth.stderr).lower():
        raise ValueError('Subscription login required')
    version = subprocess.check_output([launcher, '--version'], text=True).strip()
    prior.persist(PUBLIC/'calibration.json', prior.pretty(cal))
    prior.persist(PUBLIC/'plan.json', prior.pretty(plan))
    core = {'plan_sha256': cli.file_sha(PUBLIC/'plan.json'), 'launcher': launcher,
            'launcher_sha256': cli.file_sha(Path(launcher)), 'version': version, 'login': 'CHATGPT',
            'quota_reset_epoch': factorial.quota()}
    path = PRIVATE/'frozen.json'
    if path.exists():
        if any(prior.read(path)[k] != v for k, v in core.items()):
            raise ValueError('Frozen CLI or plan changed')
    else:
        cli.record(path, {**core, 'utc': cli.now()})
    print('Frozen', len(plan['blocks']), 'blocks;', core['plan_sha256'])


def load():
    plan, cal = materials()
    meta = prior.read(PRIVATE/'frozen.json')
    if prior.pretty(plan) != (PUBLIC/'plan.json').read_bytes() or prior.pretty(cal) != (PUBLIC/'calibration.json').read_bytes():
        raise ValueError('Frozen plan or calibration changed')
    if meta['plan_sha256'] != cli.file_sha(PUBLIC/'plan.json'):
        raise ValueError('Receipt differs from frozen plan')
    return plan, cal, meta


def outcome(block, call, path, cal, meta):
    targets = call['targets']
    data = prompt(block['task'],block['start'],call['label'],call['value_contract'])
    row = {'block': block['id'], 'model': block['model'], 'task': block['task'], 'start': block['start'],
           'label':call['label'],'value_contract':call['value_contract'],'call_id':call['id'],'targets':targets,
           'prompt_sha256': prior.digest(data), 'choice': None, 'after': None, 'assessments': [],
           'status': 'INTERRUPTED' if path.exists() else 'UNSTARTED'}
    if row['prompt_sha256'] != call['prompt_sha256']:
        raise ValueError('Prompt drift')
    if not (path/'process.json').exists():
        return row
    init = prior.read(path/'start.json')
    argv = prior.command_for(meta['launcher'], block['model'])
    if (init['argv'] != argv or init['call_id'] != call['id'] or init['block'] != block['id']
            or init['prompt_sha256'] != row['prompt_sha256'] or data != (path/'prompt.txt').read_bytes()):
        raise ValueError('Native request differs from assignment')
    proc = prior.read(path/'process.json')
    raw = (path/'stdout.bin').read_bytes()
    err = (path/'stderr.bin').read_bytes()
    if prior.digest(raw) != proc['stdout_sha256'] or prior.digest(err) != proc['stderr_sha256']:
        raise ValueError('Native capture changed')
    row.update(native_response_sha256=prior.digest(raw), elapsed_seconds=proc['elapsed_seconds'])
    if proc['error'] or proc['returncode']:
        row['status'] = prior.codex.failure_kind([(raw+err).decode(errors='replace')], proc['error'] or 'CLI_ERROR')
        return row
    try:
        msg, _ = cli.extract('codex', raw)
        decoded = cli.base.strict(msg)
        if not isinstance(decoded, dict) or set(decoded) != {'action'} or decoded['action'] not in ('keep', 'switch'):
            raise ValueError('Invalid action')
    except (ValueError, TypeError, KeyError):
        row['status'] = 'INVALID_RESPONSE'
        return row
    action = decoded['action']
    selected = block['start'] if action == 'keep' else other(block['start'])
    checks = cal[block['task']]['checks']
    grades = [{'target':t,'before_correct':all(checks[block['start']][t]),
               'after_correct':all(checks[selected][t])} for t in targets]
    return {**row, 'status':'OK', 'choice':action, 'after':selected,'assessments':grades}


def run(stage, max_blocks=None):
    plan, cal, meta = load()
    collect = stage == 'collect'
    if collect and cli.file_sha(Path(meta['launcher'])) != meta['launcher_sha256']:
        raise ValueError('Launcher changed')
    rows = []
    with (PRIVATE/'.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for i,block in enumerate(plan['blocks']):
            if collect and max_blocks is not None and i >= max_blocks:
                break
            new_block = True
            for call in block['calls']:
                path = PRIVATE/'calls'/block['id']/call['id']
                if collect and not path.exists():
                    if new_block and factorial.quota() != meta['quota_reset_epoch']:
                        raise RuntimeError('Subscription window changed')
                    new_block = False
                    if time.time()+prior.TIMEOUT >= meta['quota_reset_epoch']:
                        raise RuntimeError('Subscription window closing')
                    prior.check_memory()
                    data = prompt(block['task'],block['start'],call['label'],call['value_contract'])
                    if prior.digest(data) != call['prompt_sha256']:
                        raise ValueError('Assigned prompt changed')
                    argv = prior.command_for(meta['launcher'], block['model'])
                    path.mkdir(mode=0o700,parents=True)
                    cli.write(path/'prompt.txt',data)
                    cli.record(path/'start.json',{'block':block['id'],'call_id':call['id'],
                                                  'argv':argv,'prompt_sha256':call['prompt_sha256'],'utc':cli.now()})
                    cli.record(path/'process.json',cli._launch(argv,data,path,'codex',prior.TIMEOUT))
                row = outcome(block,call,path,cal,meta)
                if row['status'] not in ('UNSTARTED','INTERRUPTED'):
                    if collect:
                        prior.persist(path/'event.json',prior.pretty(row))
                    elif row != prior.read(path/'event.json'):
                        raise ValueError('Native replay differs')
                rows.append(row)
                if collect:
                    print(len(rows),block['id'],call['id'],row['status'],flush=True)
                    if row['status'] in prior.codex.ACCOUNT_ERRORS:
                        raise RuntimeError(row['status'])
        if not collect:
            statuses = Counter(r['status'] for r in rows)
            path = PUBLIC/'results.json' if stage == 'export' else PRIVATE/'snapshots'/f"{len(rows)-statuses['UNSTARTED']}.json"
            prior.persist(path,prior.pretty({'rows':rows,'plan_sha256':meta['plan_sha256'],
                          'cli_version':meta['version'],'auth_mode':meta['login'],'frozen_at_utc':meta['utc'],
                          'eligible_for_main_analysis':False}))
            print('Replayed',dict(statuses),path.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','collect','snapshot','export'))
    parser.add_argument('--max-blocks',type=int)
    args = parser.parse_args()
    if args.action == 'freeze':
        freeze()
    else:
        run(args.action,args.max_blocks)
