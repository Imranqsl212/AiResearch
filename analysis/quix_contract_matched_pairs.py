"""Descriptive paired outcomes from the already observed four-algorithm target reversal."""
from argparse import ArgumentParser
import ast
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

from analysis import quix_contract_reversal_report as study


def classify(rows, cal):
    cells = {r['arm']: r for r in rows}
    u, a = (cells[key] for key in study.TARGETS)
    item = {k: u[k] for k in ('block', 'model', 'task', 'start')}
    item['complete_pair'] = u['status'] == a['status'] == 'OK'
    if not item['complete_pair']:
        return item
    start = cal[u['task']]['starts'][u['start']]['implements']
    labels = [r['implements'] for r in (u, a)]
    item.update(targeted_labels=labels, start_contract=start,
                tracks_both=labels == list(study.TARGETS), same_action=u['action'] == a['action'],
                same_syntax=ast.dump(ast.parse(u['expression'].strip(), mode='eval'))
                            == ast.dump(ast.parse(a['expression'].strip(), mode='eval')))
    if len(set(labels)) == 1 and labels[0] in study.TARGETS:
        item['both_choose_start_contract'] = labels[0] == start
    return item


def compute(directory):
    study.verify(directory)
    raw = (directory / 'results.json').read_bytes()
    cal = json.loads((directory / 'calibration.json').read_bytes())
    groups = defaultdict(list)
    provenance = {}
    for row in json.loads(raw)['rows']:
        groups[row['block']].append(row)
        if row['status'] != 'OK':
            continue
        task, expr = row['task'], row['expression']
        syntax = ast.dump(ast.parse(expr.strip(), mode='eval'))
        key = (task, syntax)
        if key not in provenance:
            match = next((state for state, source in cal[task]['starts'].items()
                          if ast.dump(ast.parse(source['expression'].strip(), mode='eval')) == syntax), None)
            provenance[key] = {'task': task, 'expression': expr, 'original_start_if_same_syntax': match, 'uses': 0}
        provenance[key]['uses'] += 1
    pairs = [classify(rs, cal) for rs in groups.values()]
    return {'selection': 'post-hoc descriptive stratification of the prospectively frozen paired endpoint',
            'results_sha256': sha256(raw).hexdigest(), 'pairs': pairs, 'expressions': list(provenance.values())}


def render(result):
    pairs = result['pairs']
    lines = ['# When did the selected contract change?', '',
             'Both sessions in each pair see identical source and the same input. Only the required output changes. Each pair comprises distinct native calls.',
             '', '| Group | Pairs | Both targets followed | Upstream target passed | Alternative target passed | Same selected syntax | Same starting contract on both | Same nonstarting contract on both |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for field in ('all', 'model', 'task', 'start'):
        values = ['all'] if field == 'all' else sorted({p[field] for p in pairs})
        for val in values:
            group = [p for p in pairs if p['complete_pair'] and (field == 'all' or p[field] == val)]
            n = len(group)
            counts = [sum(p['tracks_both'] for p in group),
                      sum(p['targeted_labels'][0] == 'upstream' for p in group),
                      sum(p['targeted_labels'][1] == 'alternative' for p in group),
                      sum(p['same_syntax'] for p in group),
                      sum(p.get('both_choose_start_contract') is True for p in group),
                      sum(p.get('both_choose_start_contract') is False for p in group)]
            lines.append('| ' + ' | '.join([val, str(n), *map(str, counts)]) + ' |')
    lines += ['', 'A pair that implements the same nonstarting contract on both targets changes the starting behavior in both calls. It is one of the ways target-invariant responses can arise. The model, source and task strata share the same 16 pairs. Each model-specific rate describes this benchmark panel in this run.',
              '', '| Task | Selected expression | Matching historical syntax | Decisions |',
              '| --- | --- | --- | ---: |']
    for expression in sorted(result['expressions'], key=lambda p: (p['task'], p['expression'])):
        lines.append('| ' + ' | '.join([expression['task'], expression['expression'],
                     expression['original_start_if_same_syntax'] or 'neither', str(expression['uses'])]) + ' |')
    lines += ['', 'The only additional syntax in this panel is depth >= 0. In the pinned function every step producing a negative depth returns False immediately, so reaching the final return guarantees depth >= 0. At that location the expression is equivalent to the historical return True on any finite parentheses string. The eight other task–expression pairs are the historical sources themselves.',
              '', 'Replay with `python3 -B -m analysis.quix_contract_matched_pairs`.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=study.DEFAULT)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = compute(args.directory)
    for file, data in [('matched_pairs.json', (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()),
                       ('matched_pairs.md', render(result).encode())]:
        path = args.directory / file
        if args.write:
            path.write_bytes(data)
        elif path.read_bytes() != data:
            raise ValueError('Saved paired decomposition differs')
    print(render(result))
