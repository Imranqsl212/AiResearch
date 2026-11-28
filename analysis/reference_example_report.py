"""Replay the trusted-example positive control using only the three public JSON files."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


def targets(arm):
    return ('A', 'B') if arm in ('none', 'shared') else (arm[-1].upper(),)


def assessments(cal, block, arm, selected):
    checks = cal[block['task']]['checks']
    return [{'target': target, 'before_correct': all(checks[block['start']][target]),
             'after_correct': all(checks[selected][target])} for target in targets(arm)]


def summarize(rows):
    modes = {mode: Counter() for mode in ('none', 'shared', 'revealing')}
    paired = {}
    for row in rows:
        arm = row['arm']
        mode = modes[arm if arm in ('none', 'shared') else 'revealing']
        mode['scheduled_calls'] += 1
        for target in targets(arm):
            before = target == row['start']
            mode['scheduled_preservation' if before else 'scheduled_repair'] += 1
        if arm in ('target_a', 'target_b'):
            paired.setdefault(row['block'], {})[arm] = row
        if row['status'] != 'OK':
            continue
        mode['valid_calls'] += 1
        for value in row['assessments']:
            kind = 'preservation' if value['before_correct'] else 'repair'
            mode['assessed_' + kind] += 1
            mode['correct_' + kind] += value['after_correct']
    primary = Counter({k: 0 for k in ('both_correct', 'both_wrong', 'always_keep', 'always_switch',
                                      'missing_could_succeed', 'missing_known_failure')})
    for arms in paired.values():
        valid = [r for r in arms.values() if r['status'] == 'OK']
        scores = [r['assessments'][0]['after_correct'] for r in valid]
        if len(valid) < 2:
            primary['missing_could_succeed' if all(scores) else 'missing_known_failure'] += 1
        elif sum(scores) == 2:
            primary['both_correct'] += 1
        elif sum(scores) == 0:
            primary['both_wrong'] += 1
        else:
            assert valid[0]['choice'] == valid[1]['choice']
            primary['always_' + valid[0]['choice']] += 1
    return {'modes': modes, 'primary': primary, 'blocks': len(paired),
            'primary_bounds': [primary['both_correct'], primary['both_correct'] + primary['missing_could_succeed']]}


def report(summary):
    modes, counts = summary['modes'], summary['primary']
    result = ['# Response to a trusted reference example', '',
              'Two models each received both starting implementations for three authored tasks. Each distinguishing pair shows the same input and changes only the required output. All scores refer to the six held-out cases for the assigned contract.', '',
              '| Reference example | Valid / scheduled native calls | Defective starts repaired / assessed / scheduled | Working starts preserved / assessed / scheduled |',
              '| --- | ---: | ---: | ---: |']
    for name in ('none', 'shared', 'revealing'):
        mode = modes[name]
        repair = ' / '.join(str(mode.get(f'{k}_repair', 0)) for k in ('correct', 'assessed', 'scheduled'))
        preserve = ' / '.join(str(mode.get(f'{k}_preservation', 0)) for k in ('correct', 'assessed', 'scheduled'))
        result.append(f"| {name} | {mode.get('valid_calls', 0)} / {mode['scheduled_calls']} | {repair} | {preserve} |")
    complete = sum(counts[k] for k in ('both_correct', 'both_wrong', 'always_keep', 'always_switch'))
    lower, upper = summary['primary_bounds']
    result.extend(['', f"Both revealing responses selected the correct implementation in {counts['both_correct']}/{complete} complete blocks. Among {summary['blocks']} scheduled blocks, the lower and upper counts allowing for missing responses are {lower} and {upper}. Both responses were wrong in {counts['both_wrong']} complete blocks. The action was keep both times in {counts['always_keep']} and switch both times in {counts['always_switch']}.",
                   '', 'For the no-example and shared-example controls, each native response is assessed against both possible target contracts. Exactly half of these assessments must pass because each supplied implementation satisfies exactly one contract. This proportion is fixed by the design. The empirical endpoint measures paired, correct responses when the authoritative output changes. The tasks require selecting between two supplied functions. The CPython pilot displayed execution of the current candidate, whereas this control supplies a required output from the target specification.'])
    return '\n'.join(result) + '\n'


def validate(rows, plan, cal):
    expected = {(b['id'], a): b for b in plan['blocks'] for a in b['order']}
    if len(rows) != len(expected) or {(r['block'], r['arm']) for r in rows} != set(expected):
        raise ValueError('Missing or repeated scheduled call')
    if any(sorted(b['order']) != ['none', 'shared', 'target_a', 'target_b'] for b in plan['blocks']):
        raise ValueError('Invalid arm set')
    for row in rows:
        arm = row['arm']
        block = expected[row['block'], arm]
        if any(row[k] != block[k] for k in ('task', 'start', 'model')) or row['prompt_sha256'] != block['prompt_sha256'][arm]:
            raise ValueError('Public assignment differs')
        if row['status'] != 'OK':
            if row['choice'] is not None or row['after'] is not None or row['assessments']:
                raise ValueError('Missing answer cannot be graded')
            continue
        if row['choice'] not in ('keep', 'switch'):
            raise ValueError('Invalid published choice')
        selected = block['start'] if row['choice'] == 'keep' else {'A': 'B', 'B': 'A'}[block['start']]
        if row['after'] != selected or row['assessments'] != assessments(cal, block, arm, selected):
            raise ValueError('Held-out assessment differs')


def verify(directory):
    plan_raw = (directory/'plan.json').read_bytes()
    cal_raw = (directory/'calibration.json').read_bytes()
    plan, cal = json.loads(plan_raw), json.loads(cal_raw)
    results = json.loads((directory/'results.json').read_bytes())
    if results['plan_sha256'] != sha256(plan_raw).hexdigest() or plan['calibration_sha256'] != sha256(cal_raw).hexdigest():
        raise ValueError('Plan or calibration hash differs')
    if len(plan['blocks']) != 12 or len(results['rows']) != 48:
        raise ValueError('Expected 12 blocks and 48 native calls')
    validate(results['rows'], plan, cal)
    summary = summarize(results['rows'])
    if summary != results['summary']:
        raise ValueError('Published summary differs')
    if (directory/'comparison.md').exists() and (directory/'comparison.md').read_text() != report(summary):
        raise ValueError('Published report differs')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    print(report(verify(parser.parse_args().directory)))
