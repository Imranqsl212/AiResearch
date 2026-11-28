"""Prospective direct repetition of the six historical Luna/Matplotlib prompts."""
from argparse import ArgumentParser
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import random

from analysis import matplotlib_order_types as orders
from analysis import production_patch_report as original


DEFAULT = Path(__file__).resolve().parent / 'matplotlib_replication_20261128'
MODEL = 'gpt-6-luna'
SEED = 2026112807
MIXED = [8, 2, 0, 7]
STATES = ('faulty', 'working')
ORIGINAL_FILES = ('plan.json', 'results.json', 'sources.json', 'calibration.json', 'upstream_check.json')


def digest(raw):
    return sha256(raw).hexdigest()


def source_materials(directory):
    raw = {f: (directory / f).read_bytes() for f in ORIGINAL_FILES}
    original.verify(directory)
    data = {f: json.loads(b) for f, b in raw.items()}
    return data, {f: digest(b) for f, b in raw.items()}


def assignments(data):
    rng = random.Random(SEED)
    originals = {b['start']: b for b in data['plan.json']['blocks']
                 if b['model'] == MODEL and b['task'] == 'matplotlib'}
    cases = []
    for wave in range(1, 5):
        group = []
        for start in STATES:
            for arm in original.ARMS:
                ancestor = originals[start]
                h = digest(original.prompt(ancestor, arm, data['sources.json'], data['calibration.json']))
                if h != ancestor['prompt_sha256'][arm]:
                    raise ValueError('Current prompt differs from the discovery prompt')
                group.append({'id': f'repeat{wave}_{start}_{arm}', 'wave': wave, 'model': MODEL,
                              'task': 'matplotlib', 'start': start, 'arm': arm,
                              'original_block': ancestor['id'], 'prompt_sha256': h})
        rng.shuffle(group)
        cases.extend(group)
    return cases


def replay_probes(expr, start, cal):
    task = 'matplotlib'
    run = original.evaluator(task, expr)
    probes = {**original.PROBES[task], 'maintainer': original.ORIGINAL_TEST[task], 'mixed': MIXED}
    result = {}
    for name, inputs in probes.items():
        expected = original.expected(task, inputs)['output']
        try:
            output = run(inputs)['output']
        except ArithmeticError:
            output = None
        row = {'input': inputs, 'output': output, 'expected': expected, 'passes': output == expected}
        if name in original.PROBES[task]:
            shown = cal[task]['starts'][start]['displays'][name]
            row.update(start_output=shown, matches_start=output == shown)
        result[name] = row
    return result


def grade(action, expr, cell, cal):
    task = 'matplotlib'
    if action not in ('keep', 'replace'):
        raise ValueError('Invalid action')
    if action == 'keep' and expr != cal[task]['starts'][cell['start']]['expression']:
        raise ValueError('Kept expression changed')
    results = original.grade(task, expr, cal[task]['held'])
    return {'action': action, 'expression': expr, 'cases_passed': sum(results), 'passes': all(results),
            'probes': replay_probes(expr, cell['start'], cal), 'order_certificate': orders.classify(expr)}


def summarize(rows):
    out = {}
    for start in STATES:
        out[start] = {}
        for arm in original.ARMS:
            s = Counter()
            for row in (r for r in rows if r['start'] == start and r['arm'] == arm):
                s['scheduled'] += 1
                if row['status'] != 'OK':
                    continue
                g = row['grade']
                s['valid'] += 1
                s['passes'] += g['passes']
                s['replacements'] += g['action'] == 'replace'
                if g['passes']:
                    continue
                p = g['probes']
                s['failed'] += 1
                s['maintainer_accepts_failure'] += p['maintainer']['passes']
                s['mixed_catches_failure'] += not p['mixed']['passes']
                signature = not p['shared']['passes'] and p['revealing']['passes']
                s['shared_catches_revealing_misses'] += signature
                s['shared_catches_revealing_and_maintainer_miss'] += signature and p['maintainer']['passes']
                if arm != 'none':
                    s['shown_contract_accepts_failure'] += p[arm]['passes']
                    s['reproduces_starting_display_despite_failure'] += p[arm]['matches_start']
                    s['shown_and_maintainer_accept_failure'] += p[arm]['passes'] and p['maintainer']['passes']
            out[start][arm] = dict(s)
    return out


def render(rows):
    counts = summarize(rows)
    lines = ['# Can the Matplotlib regression be reproduced?', '',
             'Four fresh Luna calls per historical start and display. A repair or preservation passes every one of the 96 frozen checks.', '',
             '| Starting axis setter | Display | Valid / planned | Repairs or preservations / valid | Possible successes / planned | Replacements |',
             '| --- | --- | ---: | ---: | ---: | ---: |']
    for start in STATES:
        for arm in original.ARMS:
            s = Counter(counts[start][arm])
            hi = s['passes'] + s['scheduled'] - s['valid']
            lines.append(f"| {start} | {arm} | {s['valid']}/{s['scheduled']} | {s['passes']}/{s['valid']} | {s['passes']}–{hi}/{s['scheduled']} | {s['replacements']} |")
    lines += ['', '| Start | Display | Failed on held-out | Matches shown starting output | Passes contract at shown input | Passes maintainer | Passes both shown and maintainer | Shared catches, revealing misses | Of these, maintainer misses | Mixed catches |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for start in STATES:
        for arm in original.ARMS:
            s = Counter(counts[start][arm])
            keys = ('reproduces_starting_display_despite_failure', 'shown_contract_accepts_failure', 'maintainer_accepts_failure',
                    'shown_and_maintainer_accept_failure', 'shared_catches_revealing_misses',
                    'shared_catches_revealing_and_maintainer_miss', 'mixed_catches_failure')
            cells = ['—' if arm == 'none' and k in (keys[0], keys[1], keys[3]) else str(s[k]) for k in keys]
            lines.append('| ' + ' | '.join([start, arm, str(s['failed']), *cells]) + ' |')
    certs = Counter(r['grade']['order_certificate']['status'] for r in rows if r['status'] == 'OK')
    lines += ['', 'All diagnostic columns count only final implementations failing the held-out endpoint. The shared and revealing labels refer to the historical parent. A missing display has no displayed-input result.',
              '', 'Order-type certificates for selected decisions: ' + ', '.join(f'{k} {v}' for k, v in sorted(certs.items())) + '.',
              '', 'These exploratory repetitions resample decisions on a single selected model and historical bug. Each program, status, probe output and order-type counterexample appears in results.json.',
              '', 'Reproduce with `python3 -B -m analysis.matplotlib_replication_report --check`.', '']
    return '\n'.join(lines)


def verify(directory=DEFAULT):
    prior, hashes = source_materials(directory.parent / 'production_patch_20261128')
    raw = (directory / 'plan.json').read_bytes()
    plan = json.loads(raw)
    result = json.loads((directory / 'results.json').read_bytes())
    cells = assignments(prior)
    if plan['discovery_files_sha256'] != hashes or plan['assignments'] != cells or digest(raw) != result['plan_sha256']:
        raise ValueError('Changed discovery binding, schedule, prompt or plan')
    source = prior['sources.json']['matplotlib']
    expected_source = {'repository': source['repository'], 'fixed_commit': source['fixed'],
                       'parent_commit': source['parent'], 'path': source['source_path'],
                       'file_sha256': {s: source['versions'][s]['file_sha256'] for s in STATES}}
    if (plan['source'] != expected_source or plan['mixed_unshown_probe'] != MIXED or plan['seed'] != SEED
            or plan['effort'] != 'low'):
        raise ValueError('Source ancestry, probe or model setting differs')
    if len(result['rows']) != len(cells):
        raise ValueError('A scheduled observation is missing')
    for cell, row in zip(cells, result['rows']):
        if any(row[k] != v for k, v in cell.items()):
            raise ValueError('Changed assignment')
        if row['status'] == 'OK':
            g = row['grade']
            if g != grade(g['action'], g['expression'], cell, prior['calibration.json']):
                raise ValueError('Grade differs from the original endpoint or diagnostic replay')
        elif row['grade'] is not None:
            raise ValueError('Unscored observation has a grade')
    if result['summary'] != summarize(result['rows']):
        raise ValueError('Saved counts differ')
    return render(result['rows'])


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = verify(args.directory)
    if args.check and text != (args.directory / 'comparison.md').read_text():
        raise SystemExit('Rendered results differ')
    print(text)
