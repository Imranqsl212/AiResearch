"""Decide equality with the interval contract for conservative min/max expressions."""
import argparse
import ast
from collections import defaultdict
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from analysis import production_patch_report as study


def rank_tuple(values):
    ranks = {value: i for i, value in enumerate(sorted(set(values)))}
    return tuple(ranks[value] for value in values)


def weak_orders():
    return sorted({rank_tuple(v) for v in product(range(4), repeat=4) if v[0] != v[1]})


def lattice_term(node):
    if isinstance(node, ast.Name):
        return node.id in study.MATVARS
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ('min', 'max') and 2 <= len(node.args) <= 4
            and not node.keywords and all(lattice_term(arg) for arg in node.args))


def classify(expression):
    root = study.parse(expression)
    if not (isinstance(root, (ast.Tuple, ast.List)) and len(root.elts) == 2
            and all(lattice_term(arg) for arg in root.elts)):
        return {'status': 'OUTSIDE_MIN_MAX_FRAGMENT'}

    run = study.evaluator('matplotlib', expression)
    orders = weak_orders()
    failed = []
    for representative in orders:
        actual = run(representative)['output']
        expected = study.expected('matplotlib', representative)['output']
        if actual != expected:
            failed.append({'input': list(representative), 'actual': actual, 'expected': expected})
    return {'status': 'COUNTEREXAMPLE' if failed else 'ALL_ORDER_TYPES_PASS',
            'total_order_types': len(orders), 'passed_order_types': len(orders) - len(failed),
            'failures': failed}


def evaluate(directory):
    raw = (directory / 'results.json').read_bytes()
    study.verify(directory)
    expressions = defaultdict(list)
    for row in json.loads(raw)['rows']:
        if row['task'] == 'matplotlib' and row['status'] == 'OK':
            expressions[row['expression']].append({'block': row['block'], 'arm': row['arm']})
    return {
        'scope': 'Finite real scalar endpoints with unequal old endpoints, under ordinary min/max and exact order comparisons.',
        'results_sha256': sha256(raw).hexdigest(), 'heldout_order_type_count': len({rank_tuple(v) for v in study.cases('matplotlib')}),
        'programs': [{'expression': expr, 'uses': rows, **classify(expr)} for expr, rows in expressions.items()],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=study.DEFAULT)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = evaluate(args.directory)
    path = args.directory / 'order_types.json'
    data = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
    if args.write:
        path.write_bytes(data)
    elif path.read_bytes() != data:
        raise ValueError('Saved order-type results differ')
    print(f"Checked {len(result['programs'])} distinct source strings on 62 possible endpoint order types.")
