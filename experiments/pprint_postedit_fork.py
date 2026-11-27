"""Fork the archived first CPython edits and give each probe one fresh decision."""
import argparse
from collections import defaultdict
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess

from experiments import c5_cli_pilot as cli
from experiments import checker_timing_pilot as prior
from experiments import pprint_postedit_probes as fixture

PUBLIC = prior.ROOT / 'analysis/pprint_postedit_20261127'
PRIVATE = prior.ROOT / '.local_private/pprint_postedit_20261127'
DESIGN = 'docs/PPRINT_POSTEDIT_20261127.md'
NAMES = {'single': '1,2', 'mixed': '2,10'}
SOURCE = (DESIGN, 'experiments/pprint_postedit_fork.py', 'experiments/pprint_postedit_probes.py',
          *prior.SOURCES, 'analysis/checker_timing_20261126/results.json',
          'analysis/checker_timing_20261126/plan.json', 'analysis/checker_timing_20261126/calibration.json')


def parents():
    cards, frozen, plan = prior.load()
    ledger = {e['episode_id']: e for e in prior.read(prior.PUBLIC / 'results.json')['episodes']}
    checkpoints = []
    for row in plan['episodes']:
        if row['case'] != 'cpython':
            continue
        key = row['episode_id']
        directory = prior.CAPTURE / 'episodes' / key / 'd1'
        step = prior.score(directory, row, cards['cpython'], frozen['launchers'][row['model']])
        if step != ledger[key]['steps'][0] or step['status'] != 'OK':
            raise ValueError('Prior first decision does not replay')
        answer, _ = cli.extract('codex', (directory/'stdout.bin').read_bytes())
        history = (b'Archived first exchange, already completed.\nFirst request:\n'
                   + (directory/'prompt.txt').read_bytes() + b'First reply:\n' + answer
                   + b'\nEnd of archived exchange.\n')
        checkpoints.append((row, step, history))
    if len(checkpoints) != 16:
        raise ValueError('Expected the complete CPython cohort')
    return checkpoints


def make_prompt(history, variants, inputs, current, options, arm):
    menu = {'keep': 'Retain the current implementation.'}
    menu.update({key: variants[v]['snippet'] for key, v in options.items() if v != current})
    observation = f"Input: {inputs[arm]}\nFormatted output: {variants[current]['outputs'][arm]}"
    text = ('The first choice was applied. Current implementation:\n' + variants[current]['snippet']
            + '\nThe following execution was performed on this CURRENT implementation.\n' + observation
            + '\nYou have exactly one final decision. Keep the current source or choose a replacement '
              'to satisfy the documented behavior.\nAllowed choices:\n' + json.dumps(menu)
            + '\nReturn only one JSON object {"action":"ID"} with an allowed ID. No tools or explanation.\n')
    return history + text.encode()


def materials():
    cal = fixture.calibrate(prior.CACHE)
    rng = random.Random(20261127)
    groups = defaultdict(list)
    prompts = {}
    for row, step, history in parents():
        current = step['after_variant']
        if cal['variants'][current]['correct'] is not step['correct_after']:
            raise ValueError('Starting correctness changed under expanded checks')
        item = {'parent_id':row['episode_id'], 'model':row['model'], 'before_variant':current,
                'before_correct':step['correct_after'], 'options':row['options'],
                'first_response_sha256':step['native_response_sha256'], 'history_sha256':prior.digest(history)}
        hashes = {}
        for arm in NAMES:
            value = make_prompt(history, cal['variants'],cal['inputs'],current,row['options'],arm)
            prompts[row['episode_id'],arm] = value
            hashes[arm] = prior.digest(value)
        item['prompt_sha256'] = hashes
        groups[row['model'],step['correct_after']].append(item)
    blocks = []
    for members in groups.values():
        rng.shuffle(members)
        for n, item in enumerate(members):
            blocks.append({**item, 'order':list(NAMES) if n % 2 == 0 else list(reversed(NAMES))})
    rng.shuffle(blocks)
    plan = {'design':DESIGN,'seed':20261127,'eligible_for_main_analysis':False,
            'source_sha256':{k:cli.file_sha(prior.ROOT/k) for k in SOURCE},
            'calibration_sha256':prior.digest(prior.pretty(cal)), 'blocks':blocks}
    return plan, cal, prompts


def freeze():
    plan, cal, _ = materials()
    prior.persist(PUBLIC/'calibration.json', prior.pretty(cal))
    prior.persist(PUBLIC/'plan.json', prior.pretty(plan))
    launcher = str(Path(shutil.which('codex')).resolve())
    version = subprocess.check_output([launcher,'--version'],text=True).strip()
    meta = {'plan_sha256':cli.file_sha(PUBLIC/'plan.json'), 'launcher':launcher,
            'version':version, 'launcher_sha256':cli.file_sha(Path(launcher))}
    if (PRIVATE/'frozen.json').exists():
        if any(prior.read(PRIVATE/'frozen.json')[k] != v for k,v in meta.items()):
            raise ValueError('Already frozen with different source or launcher')
    else:
        cli.record(PRIVATE/'frozen.json', {**meta,'utc':cli.now()})
    print('Frozen', len(plan['blocks']), 'paired checkpoints;', meta['plan_sha256'])


def load():
    plan, cal, prompts = materials()
    meta = prior.read(PRIVATE/'frozen.json')
    if (prior.pretty(plan) != (PUBLIC/'plan.json').read_bytes()
            or prior.pretty(cal) != (PUBLIC/'calibration.json').read_bytes()
            or prior.digest(prior.pretty(plan)) != meta['plan_sha256']):
        raise ValueError('Frozen materials changed')
    return plan, cal, prompts, meta


def outcome(item, arm, path, prompt, cal, meta):
    cur = item['before_variant']
    result = {k:item[k] for k in ('parent_id','model','before_variant','before_correct','history_sha256')}
    result.update(probe=NAMES[arm], prompt_sha256=prior.digest(prompt),choice=None,after_variant=None,
                  after_correct=None,status='INTERRUPTED' if path.exists() else 'UNSTARTED')
    if not (path/'process.json').exists():
        return result
    start = prior.read(path/'start.json')
    argv = prior.command_for(meta['launcher'],item['model'])
    if (start['argv'] != argv or start['arm'] != arm or start['parent_id'] != item['parent_id']
            or start['prompt_sha256'] != result['prompt_sha256'] or prompt != (path/'prompt.txt').read_bytes()):
        raise ValueError('Native request or assignment differs')
    raw, err = ((path/f).read_bytes() for f in ('stdout.bin','stderr.bin'))
    proc = prior.read(path/'process.json')
    if prior.digest(raw) != proc['stdout_sha256'] or prior.digest(err) != proc['stderr_sha256']:
        raise ValueError('Native capture digest differs')
    result.update(native_response_sha256=prior.digest(raw), elapsed_seconds=proc['elapsed_seconds'])
    if proc['error'] or proc['returncode']:
        result['status'] = prior.codex.failure_kind([(raw+err).decode(errors='replace')],proc['error'] or 'CLI_ERROR')
        return result
    try:
        msg, _ = cli.extract('codex',raw)
        obj = cli.base.strict(msg)
        choice = obj['action']
        if set(obj) != {'action'} or not isinstance(choice,str):
            raise ValueError('Invalid response')
        after = cur if choice=='keep' else item['options'][choice]
        if after == cur and choice != 'keep':
            raise ValueError('Unlisted action')
    except (ValueError, TypeError, KeyError):
        result['status']='INVALID_RESPONSE'
        return result
    return {**result,'choice':choice,'after_variant':after,'after_correct':cal['variants'][after]['correct'],'status':'OK'}


def collect():
    plan, cal, prompts, meta = load()
    if meta['launcher_sha256'] != cli.file_sha(Path(meta['launcher'])):
        raise ValueError('Codex launcher changed')
    with (PRIVATE/'.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for item in plan['blocks']:
            for arm in item['order']:
                key = item['parent_id']
                path = PRIVATE/'calls'/key/arm
                p = prompts[key,arm]
                if not path.exists():
                    prior.check_memory()
                    path.mkdir(parents=True,mode=0o700)
                    argv = prior.command_for(meta['launcher'],item['model'])
                    cli.write(path/'prompt.txt', p)
                    cli.record(path/'start.json',{'parent_id':key,'arm':arm,'utc':cli.now(),
                                                 'prompt_sha256':prior.digest(p),'argv':argv})
                    proc = cli._launch(argv,p,path,'codex',prior.TIMEOUT)
                    cli.record(path/'process.json', proc)
                row = outcome(item,arm,path,p,cal,meta)
                if row['status'] != 'INTERRUPTED':
                    prior.persist(path/'event.json',prior.pretty(row))
                print(key,arm,row['status'],flush=True)
                if row['status'] in prior.codex.ACCOUNT_ERRORS:
                    raise RuntimeError(row['status'])


def export():
    plan, cal, prompts, meta = load()
    rows = []
    for item in plan['blocks']:
        for arm in item['order']:
            key = item['parent_id']
            path = PRIVATE/'calls'/key/arm
            row = outcome(item,arm,path,prompts[key,arm],cal,meta)
            if row['status'] not in ('UNSTARTED','INTERRUPTED') and prior.read(path/'event.json') != row:
                raise ValueError('Sealed decision differs from native replay')
            rows.append(row)
    prior.persist(PUBLIC/'results.json',prior.pretty({'plan_sha256':meta['plan_sha256'],
                  'frozen_at_utc':meta['utc'],'cli_version':meta['version'],'rows':rows,
                  'eligible_for_main_analysis':False}))
    print('Replayed',sum(r['status']=='OK' for r in rows),'valid decisions of',len(rows))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','collect','export'))
    args=parser.parse_args()
    {'freeze':freeze,'collect':collect,'export':export}[args.action]()
