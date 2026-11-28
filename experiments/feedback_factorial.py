"""Cross actual and required output in a frozen subscription-only experiment."""
import argparse
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
from collections import Counter

from experiments import reference_example_control as reference

from experiments import c5_cli_pilot as cli
from experiments import checker_timing_pilot as prior

ROOT = prior.ROOT
PUBLIC = ROOT / 'analysis/feedback_factorial_20261128'
PRIVATE = ROOT / '.local_private/feedback_factorial_20261128'
DESIGN = 'docs/FEEDBACK_FACTORIAL_20261128.md'
SOURCES = (DESIGN, 'experiments/feedback_factorial.py','experiments/reference_example_control.py',
           'experiments/checker_timing_pilot.py','experiments/c5_cli_pilot.py',
           'experiments/c5_codex_effort.py','experiments/c5_evidence_challenge.py')
RULES = {'sort': ('numeric ascending order','ascending order of decimal text'),
         'argmax': ('the first index attaining the maximum','the last index attaining the maximum'),
         'round': ('the lower multiple at an exact midpoint','the higher multiple at an exact midpoint')}
ARMS = ('none','actual','required','both')
SEED = 2026112803


def prompt(task_name, start, wording, arm, target):
    task = reference.TASKS[task_name]
    x, a, b = task['examples'][1]
    out = {'A': a,'B': b}
    source, replacement = task['code'] if start == 'A' else reversed(task['code'])
    lines = [task['description'], 'Exactly one of these implementations matches this installation.']
    if wording == 'explicit':
        lines.append('This installation requires ' + RULES[task_name][int(target == 'B')] + '.')
    lines.extend(['Current implementation:', 'def solve(x):', '    '+source,
                  'Alternative implementation:', 'def solve(x):', '    '+replacement,
                  'Diagnostic input: ' + json.dumps(x)])
    if arm in ('actual','both'):
        lines.append('Actual output of the current implementation: ' + json.dumps(out[start]))
    if arm in ('required','both'):
        lines.append('Required output of the target installation: ' + json.dumps(out[target]))
    lines.append('You have one decision. Keep the current implementation or switch to the alternative. '
                 'Return only one JSON object {"action":"keep"} or {"action":"switch"}. No tools or explanation.')
    return (chr(10).join(lines)+chr(10)).encode()


def materials():
    cal = reference.calibration()
    rng = random.Random(SEED)
    waves = [[],[]]
    for task in reference.TASKS:
        offset = rng.randrange(2)
        for index, model in enumerate(reference.MODELS):
            for wave in range(2):
                start = ('A','B')[(index + offset + wave) % 2]
                block = {'id':f'{model}_{task}_{start}', 'task':task, 'model':model,
                         'start':start,'wave':wave+1,'calls':[]}
                for wording in ('hidden','explicit'):
                    for arm in ARMS:
                        pooled = wording == 'hidden' and arm in ('none','actual')
                        for targets in ([['A','B']] if pooled else [['A'],['B']]):
                            data = prompt(task,start,wording,arm,targets[0])
                            if any(prompt(task,start,wording,arm,t) != data for t in targets):
                                raise ValueError('Distinct target prompts cannot be pooled')
                            block['calls'].append({'id':f"{wording}_{arm}_{''.join(targets)}",
                                                   'wording':wording,'arm':arm,'targets':targets,
                                                   'prompt_sha256':prior.digest(data)})
                if len({q['prompt_sha256'] for q in block['calls']}) != 14:
                    raise ValueError('Unexpected within-block duplication')
                rng.shuffle(block['calls'])
                waves[wave].append(block)
    for wave in waves:
        rng.shuffle(wave)
    plan = {'design': DESIGN, 'seed': SEED, 'effort':'low','eligible_for_main_analysis':False,
            'blocks':waves[0]+waves[1], 'calibration_sha256':prior.digest(prior.pretty(cal)),
            'source_sha256':{p:cli.file_sha(ROOT/p) for p in SOURCES}}
    return plan,cal


def quota():
    script = ROOT/'.local_private/feedback_cycle_quota/read.py'
    q = json.loads(subprocess.check_output([sys.executable,str(script)],text=True,timeout=35))
    windows = [w for w in q['windows']['codex'].values() if isinstance(w,dict)]
    window, = [w for w in windows if w.get('windowDurationMins') == 10080]
    if q['included_allowed'] is not True or window['usedPercent'] >= 100:
        raise RuntimeError('Included usage exhausted')
    return window['resetsAt']


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
            'quota_reset_epoch': quota()}
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
    arm, targets = call['arm'], call['targets']
    data = prompt(block['task'],block['start'],call['wording'],arm,targets[0])
    row = {'block': block['id'], 'model': block['model'], 'task': block['task'], 'start': block['start'],
           'arm':arm,'wording':call['wording'],'call_id':call['id'],'targets':targets,
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
    selected = block['start'] if action == 'keep' else reference.other(block['start'])
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
                    if new_block and quota() != meta['quota_reset_epoch']:
                        raise RuntimeError('Subscription window changed')
                    new_block = False
                    if time.time()+prior.TIMEOUT >= meta['quota_reset_epoch']:
                        raise RuntimeError('Subscription window closing')
                    prior.check_memory()
                    data = prompt(block['task'],block['start'],call['wording'],call['arm'],call['targets'][0])
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
