"""Freeze, collect, and replay the two-case diagnostic-timing pilot."""
import argparse
from collections import Counter
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

from experiments import c5_cli_pilot as cli
from experiments import c5_codex_effort as codex
from experiments import checker_timing_dateutil, checker_timing_pprint

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.local_private/c5_external_20261124'
CAPTURE = ROOT / '.local_private/checker_timing_20261126'
PUBLIC = ROOT / 'analysis/checker_timing_20261126'
DESIGN = 'docs/CHECKER_TIMING_PILOT_20261126.md'
SOURCES = (DESIGN, 'external_checker_audit_20261124/sources.json', 'experiments/checker_timing_pilot.py',
           'experiments/checker_timing_dateutil.py', 'experiments/checker_timing_pprint.py',
           'experiments/c5_cli_pilot.py', 'experiments/c5_codex_effort.py', 'experiments/c5_evidence_challenge.py')
SEED = 20261126
TIMEOUT = 120


def read(path):
    return json.loads(path.read_bytes())


def pretty(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def digest(data):
    return sha256(data).hexdigest()


def cards():
    return {'dateutil': checker_timing_dateutil.cards(CACHE), 'cpython': checker_timing_pprint.cards(CACHE)}


def persist(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Published or frozen file differs: {path.name}')
    else:
        cli.write(path, data)


def build_plan(material, access):
    if access.get('gpt-6.2-astra') != 'AVAILABLE':
        raise ValueError('Primary model unavailable')
    other = 'sonnet' if access.get('sonnet') == 'AVAILABLE' else 'gpt-6-luna'
    if access.get(other) != 'AVAILABLE':
        raise ValueError('Second family unavailable')
    roster = ['gpt-6.2-astra', other]
    rng = random.Random(SEED)
    blocks = []
    for group, model in enumerate(roster):
        for c, case in enumerate(('dateutil', 'cpython')):
            card = material[case]
            for s, state in enumerate(('correct', 'defective')):
                for repeat in (1, 2):
                    variants = sorted(card['variants'])
                    rng.shuffle(variants)
                    options = {f'v{i}': v for i, v in enumerate(variants, 1)}
                    timings = ['early', 'late'] if (repeat + group + c + s) % 2 else ['late', 'early']
                    blocks.append([{'episode_id': f'{model}_{case}_{state}_r{repeat}_{timing}', 'model': model,
                                    'case': case, 'state': state, 'repeat': repeat, 'timing': timing,
                                    'start_variant': card['starts'][state], 'options': options} for timing in timings])
    rng.shuffle(blocks)
    return {'design': DESIGN, 'status': 'EXPLORATORY_BEFORE_HUMAN_REVIEW', 'eligible_for_main_analysis': False,
            'access': access, 'roster': roster, 'source_sha256': {p: cli.file_sha(ROOT / p) for p in SOURCES},
            'cards_sha256': digest(pretty(material)), 'seed': SEED,
            'episodes': [row for block in blocks for row in block]}


def freeze():
    material = cards()
    plan = build_plan(material, read(CAPTURE / 'access/summary.json'))
    persist(PUBLIC / 'calibration.json', pretty(material))
    persist(PUBLIC / 'plan.json', pretty(plan))
    launchers = {}
    for model in plan['roster']:
        provider = 'claude' if model == 'sonnet' else 'codex'
        launcher = Path(shutil.which(provider)).resolve()
        version = subprocess.check_output([str(launcher), '--version'], text=True).strip()
        launchers[model] = {'path': str(launcher), 'sha256': cli.file_sha(launcher), 'version': version, 'provider': provider}
    frozen = CAPTURE / 'frozen.json'
    if not frozen.exists():
        cli.record(frozen, {'utc': cli.now(), 'plan_sha256': digest(pretty(plan)), 'launchers': launchers})
    else:
        initial = read(frozen)
        if initial['plan_sha256'] != digest(pretty(plan)) or initial['launchers'] != launchers:
            raise ValueError('Previously frozen plan or launcher differs')
    print('Frozen', len(plan['episodes']), 'episodes;', digest(pretty(plan)), flush=True)


def load(replay_calibration=False):
    material = read(PUBLIC / 'calibration.json')
    initial = read(CAPTURE / 'frozen.json')
    plan = read(PUBLIC / 'plan.json')
    if initial['plan_sha256'] != digest(pretty(plan)) or plan != build_plan(material, read(CAPTURE / 'access/summary.json')):
        raise ValueError('Frozen protocol, calibration, roster or schedule differs')
    if replay_calibration and material != cards():
        raise ValueError('Measured upstream behavior changed')
    return material, initial, plan


def command_for(launcher, model):
    if model == 'sonnet':
        return cli.command('claude', 'sonnet', launcher)
    return codex.command(launcher, model, 'low')


def prompt(card, episode, first=None):
    start = episode['start_variant']
    current = first['after_variant'] if first else start
    witness = card['variants'][start]['diagnostic']
    early = episode['timing'] == 'early'
    lines = [card['task'], 'The legacy test reported FAIL on the initial source.',
             'Initial implementation:', card['variants'][start]['snippet']]
    if first:
        lines += ['The first decision has been applied.', 'First choice: ' + first['choice'],
                  'Current implementation:', card['variants'][current]['snippet'],
                  'Observation about the INITIAL source, before the first choice:', witness,
                  'This is decision 2 of 2, your final choice.']
    else:
        lines += ['Observation about the INITIAL source, before the first choice:',
                  witness if early else 'The independent measurement will be shown after this choice.',
                  'This is decision 1 of 2. Your choice is applied now and you may keep or revise it on decision 2.']
    menu = {'keep': 'Retain the current implementation.'}
    menu.update({label: card['variants'][target]['snippet']
                 for label, target in episode['options'].items() if target != current})
    lines += ['Choose the source that should be used to satisfy the documented behavior.',
              'Allowed choices and their code:', json.dumps(menu, ensure_ascii=False),
              'Respond only with one JSON object of the form {"action":"ID"}, using one of the allowed IDs. No tools or explanation.']
    return ('\n'.join(lines)+'\n').encode(), menu


def score(path, row, card, tool, first=None):
    n = 2 if first else 1
    current = first['after_variant'] if first else row['start_variant']
    expected, menu = prompt(card, row, first)
    launch = read(path/'start.json')
    process = read(path/'process.json')
    argv = command_for(tool['path'], row['model'])
    if (expected != (path/'prompt.txt').read_bytes() or launch['prompt_sha256'] != digest(expected)
            or launch['episode_id'] != row['episode_id'] or launch['decision'] != n or launch['argv'] != argv):
        raise ValueError('Assignment or prompt does not replay')
    raw = (path/'stdout.bin').read_bytes()
    err = (path/'stderr.bin').read_bytes()
    if process['stdout_sha256'] != digest(raw) or process['stderr_sha256'] != digest(err):
        raise ValueError('Native output digest differs')
    result = {'decision': n, 'before_variant': current, 'correct_before': card['variants'][current]['correct'],
              'observed_diagnostic_before': row['timing']=='early' or n==2, 'seconds': process['elapsed_seconds'],
              'status': 'OK', 'choice': None, 'action': None, 'after_variant': None, 'correct_after': None,
              'native_response_sha256': digest(raw), 'prompt_sha256': digest(expected)}
    if process['returncode'] or process['error']:
        result['status'] = codex.failure_kind([(raw+err).decode(errors='replace')], process['error'] or 'CLI_ERROR')
        return result
    try:
        msg, _ = cli.extract(tool['provider'], raw)
        obj = cli.base.strict(msg)
        if set(obj) != {'action'} or not isinstance(obj['action'], str) or obj['action'] not in menu:
            raise ValueError('Disallowed action')
    except (ValueError, TypeError, KeyError):
        result['status'] = 'INVALID_RESPONSE'
        return result
    choice = obj['action']
    action = 'keep' if choice == 'keep' else row['options'][choice]
    after = current if action == 'keep' else action
    return {**result, 'choice': choice, 'action': action, 'after_variant': after,
            'correct_after': card['variants'][after]['correct']}


def check_memory():
    if sys.platform != 'darwin':
        return
    while True:
        pressure = subprocess.check_output(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'], text=True).strip()
        if pressure in ('1', '2'):
            return
        if pressure != '4':
            raise ValueError('Cannot read the operating system memory pressure')
        print('Waiting for critical system memory pressure to clear', flush=True)
        time.sleep(15)


def collect():
    material, frozen, plan = load()
    with (CAPTURE / '.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checked = set()
        for row in plan['episodes']:
            card = material[row['case']]
            first = None
            tool = frozen['launchers'][row['model']]
            if tool['path'] not in checked:
                if cli.file_sha(Path(tool['path'])) != tool['sha256']:
                    raise ValueError('Launcher changed after freeze')
                checked.add(tool['path'])
            for n in (1, 2):
                path = CAPTURE / 'episodes' / row['episode_id'] / f'd{n}'
                if not path.exists():
                    check_memory()
                    path.mkdir(parents=True, mode=0o700)
                    data, _ = prompt(card, row, first)
                    argv = command_for(tool['path'], row['model'])
                    cli.write(path/'prompt.txt', data)
                    cli.record(path/'start.json', {'episode_id': row['episode_id'], 'decision': n,
                               'prompt_sha256': digest(data), 'utc': cli.now(), 'argv': argv})
                    proc = cli._launch(argv, data, path, tool['provider'], TIMEOUT)
                    cli.record(path/'process.json', proc)
                if not (path/'process.json').exists():
                    print('Interrupted reservation', row['episode_id'], n, flush=True)
                    break
                step = score(path,row,card,tool,first)
                receipt = path/'event.json'
                if not receipt.exists():
                    cli.record(receipt, step)
                    print(row['episode_id'], n, step['status'], flush=True)
                elif read(receipt) != step:
                    raise ValueError('Stored decision differs from raw replay')
                if step['status'] in ('ACCOUNT_AUTH','ACCOUNT_QUOTA','NETWORK_UNAVAILABLE'):
                    raise RuntimeError('Provider unavailable: '+step['status'])
                if step['status'] != 'OK':
                    break
                first = step


def export():
    material, frozen, plan = load(replay_calibration=True)
    episodes = []
    for row in plan['episodes']:
        steps = []
        card = material[row['case']]
        for n in (1,2):
            path = CAPTURE / 'episodes' / row['episode_id'] / f'd{n}'
            if not (path/'event.json').exists():
                break
            step = score(path,row,card,frozen['launchers'][row['model']],steps[0] if steps else None)
            if read(path/'event.json') != step:
                raise ValueError('Stored decision differs from raw replay')
            steps.append(step)
            if step['status'] != 'OK':
                break
        episodes.append({k:v for k,v in row.items() if k!='options'} | {'steps':steps})
    public = {'protocol':DESIGN,'eligible_for_main_analysis':False,'plan_sha256':frozen['plan_sha256'],
              'frozen_at_utc':frozen['utc'], 'roster':plan['roster'], 'access':plan['access'],
              'launchers':{m:t['version'] for m,t in frozen['launchers'].items()}, 'episodes':episodes}
    persist(PUBLIC/'results.json', pretty(public))
    print('Exported episode lengths:', dict(Counter(len(r['steps']) for r in episodes)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('freeze','collect','export'))
    args = p.parse_args()
    {'freeze':freeze, 'collect':collect, 'export':export}[args.action]()
