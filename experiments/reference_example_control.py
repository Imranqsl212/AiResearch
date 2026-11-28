"""Frozen, subscription-only reference-example positive control."""
import argparse
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess

from experiments import c5_cli_pilot as cli
from experiments import checker_timing_pilot as prior

ROOT = prior.ROOT
PUBLIC = ROOT / 'analysis/reference_example_20261128'
PRIVATE = ROOT / '.local_private/reference_example_20261128'
DESIGN = 'docs/REFERENCE_EXAMPLE_CONTROL_20261128.md'
SOURCES = (DESIGN, 'experiments/reference_example_control.py', 'experiments/checker_timing_pilot.py',
           'experiments/c5_cli_pilot.py', 'experiments/c5_codex_effort.py', 'analysis/reference_example_report.py')
MODELS = ('gpt-6-luna', 'gpt-6.2-astra')
ARMS = ('none', 'shared', 'target_a', 'target_b')
TASKS = {
    'sort': {
        'description': 'Sort a list of integers. The target uses numeric ascending order or ascending order of decimal text.',
        'code': ('return sorted(x)', 'return sorted(x, key=str)'),
        'examples': [([8, 3, 1], [1, 3, 8], [1, 3, 8]), ([10, 2, 7], [2, 7, 10], [10, 2, 7])],
        'held_out': [([], [], []), ([4], [4], [4]), ([12, 3, 2], [2, 3, 12], [12, 2, 3]),
                     ([3, 11, 3], [3, 3, 11], [11, 3, 3]), ([-2, -10, 1], [-10, -2, 1], [-10, -2, 1]),
                     ([-5, -12, -20], [-20, -12, -5], [-12, -20, -5])]},
    'argmax': {
        'description': 'Return a zero-based index of the maximum integer in a nonempty list. The target uses the first or the last tied maximum.',
        'code': ('return x.index(max(x))', 'return len(x) - 1 - x[::-1].index(max(x))'),
        'examples': [([3, 8, 1], 1, 1), ([8, 1, 8], 0, 2)],
        'held_out': [([0], 0, 0), ([-2, -2], 0, 1), ([9, 4, 9, 9], 0, 3), ([0, 3, 3, 1], 1, 2),
                     ([-2, -1, -3], 1, 1), ([1, 0], 0, 0)]},
    'round': {
        'description': 'Round a nonnegative integer to the nearest multiple of ten. At an exact midpoint the target chooses the lower or the higher multiple.',
        'code': ('return ((x + 4) // 10) * 10', 'return ((x + 5) // 10) * 10'),
        'examples': [(12, 10, 10), (25, 20, 30)],
        'held_out': [(0, 0, 0), (5, 0, 10), (14, 10, 10), (15, 10, 20), (26, 30, 30), (105, 100, 110)]},
}

def other(contract):
    return {'A': 'B', 'B': 'A'}[contract]


def calibration():
    result = {}
    for name, task in TASKS.items():
        checks = {}
        for index, contract in enumerate(('A', 'B')):
            namespace = {}
            # Compile only the fixed implementations declared above.
            exec('def evaluate(x):\n    ' + task['code'][index], namespace)
            run = namespace['evaluate']
            for value, expected_a, expected_b in task['examples'] + task['held_out']:
                if run(value) != (expected_a, expected_b)[index]:
                    raise ValueError(f'Incorrect authored expectation for {name} {contract}')
            results = [run(row[0]) for row in task['held_out']]
            checks[contract] = {target: [answer == row[i + 1] for answer, row in zip(results, task['held_out'])]
                                for i, target in enumerate(('A', 'B'))}
        shared, distinguishing = task['examples']
        examples = [e[0] for e in task['examples']]
        if shared[1] != shared[2] or distinguishing[1] == distinguishing[2] or any(row[0] in examples for row in task['held_out']):
            raise ValueError('Displayed examples failed separation or overlap held-out inputs')
        for contract in ('A', 'B'):
            if not all(checks[contract][contract]) or all(checks[contract][other(contract)]):
                raise ValueError('Held-out checks must identify exactly one passing implementation')
        result[name] = {'shown': task['examples'], 'held_out': task['held_out'], 'checks': checks}
    return result


def prompt(task_name, start, arm):
    task = TASKS[task_name]
    source, replacement = task['code'] if start == 'A' else reversed(task['code'])
    observation = ''
    if arm != 'none':
        value, a, b = task['examples'][0 if arm == 'shared' else 1]
        output = b if arm == 'target_b' else a
        observation = f'Trusted example from the target specification: input {json.dumps(value)}; required output {json.dumps(output)}.\n'
    return (
        task['description'] + '\nExactly one of the two implementations matches the target rule.\n'
        + 'Current implementation:\ndef solve(x):\n    ' + source
        + '\nAlternative implementation:\ndef solve(x):\n    ' + replacement + '\n'
        + observation + 'You have one decision. Keep the current implementation or switch to the alternative. '
        + 'Return only one JSON object {"action":"keep"} or {"action":"switch"}. No tools or explanation.\n'
    ).encode()


def materials():
    cal = calibration()
    blocks = []
    rng = random.Random(20261128)
    for model in MODELS:
        for task in TASKS:
            for start in ('A', 'B'):
                order = list(ARMS)
                rng.shuffle(order)
                blocks.append({'id': f'{model}_{task}_{start}', 'model': model, 'task': task, 'start': start,
                               'order': order, 'prompt_sha256': {arm: prior.digest(prompt(task,start,arm)) for arm in ARMS}})
    rng.shuffle(blocks)
    plan = {'design': DESIGN, 'seed': 20261128, 'eligible_for_main_analysis': False,
            'effort': 'low', 'blocks': blocks, 'calibration_sha256': prior.digest(prior.pretty(cal)),
            'source_sha256': {path: cli.file_sha(ROOT/path) for path in SOURCES}}
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
            'launcher_sha256': cli.file_sha(Path(launcher)), 'version': version, 'login': 'CHATGPT'}
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


def outcome(block, arm, path, cal, meta):
    from analysis.reference_example_report import assessments
    data = prompt(block['task'], block['start'], arm)
    row = {'block': block['id'], 'model': block['model'], 'task': block['task'], 'start': block['start'],
           'arm': arm, 'prompt_sha256': prior.digest(data), 'choice': None, 'after': None, 'assessments': [],
           'status': 'INTERRUPTED' if path.exists() else 'UNSTARTED'}
    if row['prompt_sha256'] != block['prompt_sha256'][arm]:
        raise ValueError('Prompt drift')
    if not (path/'process.json').exists():
        return row
    init = prior.read(path/'start.json')
    argv = prior.command_for(meta['launcher'], block['model'])
    if (init['argv'] != argv or init['arm'] != arm or init['block'] != block['id']
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
    return {**row, 'status': 'OK', 'choice': action, 'after': selected,
            'assessments': assessments(cal, block, arm, selected)}


def collect():
    plan, cal, meta = load()
    if cli.file_sha(Path(meta['launcher'])) != meta['launcher_sha256']:
        raise ValueError('Launcher changed after freeze')
    with (PRIVATE/'.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for block in plan['blocks']:
            for arm in block['order']:
                path = PRIVATE/'calls'/block['id']/arm
                if not path.exists():
                    prior.check_memory()
                    data = prompt(block['task'], block['start'], arm)
                    argv = prior.command_for(meta['launcher'], block['model'])
                    path.mkdir(mode=0o700, parents=True)
                    cli.write(path/'prompt.txt', data)
                    cli.record(path/'start.json', {'argv': argv, 'arm': arm, 'block': block['id'],
                                                  'prompt_sha256': prior.digest(data), 'utc': cli.now()})
                    proc = cli._launch(argv, data, path, 'codex', prior.TIMEOUT)
                    cli.record(path/'process.json', proc)
                row = outcome(block, arm, path, cal, meta)
                if row['status'] != 'INTERRUPTED':
                    prior.persist(path/'event.json', prior.pretty(row))
                print(block['id'], arm, row['status'], flush=True)
                if row['status'] in prior.codex.ACCOUNT_ERRORS:
                    raise RuntimeError(row['status'])


def export():
    from analysis.reference_example_report import summarize, report, validate
    plan, cal, meta = load()
    rows = []
    for block in plan['blocks']:
        for arm in block['order']:
            directory = PRIVATE/'calls'/block['id']/arm
            row = outcome(block, arm, directory, cal, meta)
            if row['status'] not in ('UNSTARTED', 'INTERRUPTED') and row != prior.read(directory/'event.json'):
                raise ValueError('Native response does not replay')
            rows.append(row)
    validate(rows, plan, cal)
    summary = summarize(rows)
    data = {'plan_sha256': meta['plan_sha256'], 'cli_version': meta['version'], 'frozen_at_utc': meta['utc'],
            'eligible_for_main_analysis': False, 'rows': rows, 'summary': summary}
    prior.persist(PUBLIC/'results.json', prior.pretty(data))
    prior.persist(PUBLIC/'comparison.md', report(summary).encode())
    print(report(summary))


if __name__ == '__main__':
    actions = {'freeze': freeze, 'collect': collect, 'export': export}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=actions)
    actions[parser.parse_args().action]()
