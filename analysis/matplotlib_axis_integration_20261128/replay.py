"""Replay an inverted-axis regression on headless historical Matplotlib or recount saved bounds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent
PRODUCTION = ANALYSIS / 'production_patch_20261128'
REPEATS = ANALYSIS / 'matplotlib_replication_20261128'
PROGRAMS = ('historical_fix', 'historical_fault', 'generated_regression')
FROZEN = (PRODUCTION / 'sources.json', PRODUCTION / 'results.json',
          PRODUCTION / 'calibration.json', REPEATS / 'results.json')
PROBES = ('maintainer', 'shared', 'revealing', 'mixed')


def read(path):
    return json.loads(path.read_bytes())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def inputs_and_sources():
    source = read(FROZEN[0])['matplotlib']
    row, = (r for r in read(FROZEN[1])['rows'] if r['block'] == 'gpt-6-luna_matplotlib_working'
            and r['arm'] == 'revealing' and r['status'] == 'OK' and r['action'] == 'replace')
    repeat, = (r for r in read(FROZEN[3])['rows'] if r['id'] == 'repeat1_working_revealing')
    require(row['expression'] == repeat['grade']['expression'], 'Repeated source differs')
    inputs = {k: repeat['grade']['probes'][k]['input'] for k in PROBES}
    held = read(FROZEN[2])['matplotlib']['held']
    require(len(held) == len({tuple(r['input']) for r in held}) == 96, 'Held-out input count differs')
    for i, r in enumerate(held, 1):
        inputs['held_%02d' % i] = r['input']
        require(expected(r['input']) == r['expected']['output'], 'Frozen expected interval differs')
    return source, row, repeat, inputs


def expected(values):
    start, end, _, _ = values
    require(start != end, 'Old interval must have a direction')
    endpoints = [min(values), max(values)]
    return endpoints if start < end else endpoints[::-1]


def recount(observations, inputs):
    require(list(inputs) == [r['case'] for r in observations], 'Input order or membership differs')
    scores = {p: {'heldout_passed': 0, 'heldout_total': 0, 'heldout_direction_preserved': 0,
                  'probes_passed': {}} for p in PROGRAMS}
    for r in observations:
        values = inputs[r['case']]
        require(r['input'] == values and r['expected'] == expected(values), 'Oracle or input differs')
        for program, stats in scores.items():
            limits = r[program]
            require(isinstance(limits, list) and len(limits) == 2 and
                    all(isinstance(v, (int, float)) and v in values for v in limits), 'Invalid limits')
            correct = limits == expected(values)
            if r['case'] in PROBES:
                stats['probes_passed'][r['case']] = correct
            else:
                stats['heldout_total'] += 1
                stats['heldout_passed'] += correct
                a, b = limits
                stats['heldout_direction_preserved'] += (a < b if values[0] < values[1] else a > b)
    return scores


def worker(staged, inputs):
    import matplotlib
    import matplotlib.axis
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    require(matplotlib.get_backend().lower() == 'agg' and
            Path(matplotlib.axis.__file__).resolve() == staged / 'matplotlib/axis.py',
            'Unexpected Matplotlib backend or imported axis module')
    test_path = staged / 'matplotlib/tests/test_axes.py'
    import contextlib
    import io
    import pytest

    class CaptureLimits:
        def pytest_runtest_logreport(self, report):
            if report.when == 'call':
                self.limits = list(plt.gca().get_xlim())
                self.is_agg = isinstance(plt.gcf().canvas, FigureCanvasAgg)
                self.passed = report.passed
                if report.failed:
                    location = report.longrepr.reprcrash
                    self.failed_line = test_path.read_text().splitlines()[location.lineno - 1].strip()

    capture = CaptureLimits()
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        code = pytest.main([str(test_path) + '::test_set_ticks_inverted', '--assert=plain',
                            '-q', '-p', 'no:cacheprovider'], plugins=[capture])
    require(code in (0, 1) and hasattr(capture, 'limits'), 'Maintainer test did not execute: ' + log.getvalue())
    require(capture.is_agg and (code == 0) == capture.passed, 'Unexpected canvas or pytest status')
    if not capture.passed:
        require(capture.failed_line == 'assert ax.get_xlim() == (1, 0)', 'Unexpected upstream failure')
    upstream_passed = capture.passed
    outputs = {'maintainer': capture.limits}
    require(upstream_passed == (capture.limits == expected(inputs['maintainer'])),
            'Maintainer assertion disagrees with observed public limits')
    for label, (start, end, first, last) in inputs.items():
        if label == 'maintainer':
            continue
        fig, ax = plt.subplots()
        ax.set_xlim(start, end)
        require(list(ax.get_xlim()) == [start, end], 'Starting limits differ')
        ax.set_xticks([first, last])
        outputs[label] = list(ax.get_xlim())
        plt.close(fig)
    imported = {name: Path(mod.__file__).resolve() for name, mod in list(sys.modules.items())
                if (name == 'matplotlib' or name.startswith('matplotlib.'))
                and getattr(mod, '__file__', '').endswith('.py')}
    require(all(staged in path.parents for path in imported.values()), 'Matplotlib Python import escaped historical tree')
    return {'outputs': outputs, 'upstream_assertion_passed': upstream_passed,
            'axis_sha256': digest(Path(matplotlib.axis.__file__).read_bytes()),
            'backend': matplotlib.get_backend(), 'matplotlib_reported_version': matplotlib.__version__,
            'python_modules_from_staged_tree': len(imported)}


def run(checkout):
    from importlib import metadata, util
    source, row, repeat, inputs = inputs_and_sources()
    require(metadata.version('matplotlib') == '3.1.2', 'The binary donor must be Matplotlib 3.1.2')
    lib = checkout.resolve() / 'lib'
    historical = (lib / 'matplotlib/axis.py').read_bytes()
    source_paths = ('matplotlib/axis.py', 'matplotlib/axes/_base.py', 'matplotlib/axes/_axes.py',
                    'matplotlib/pyplot.py', 'matplotlib/backends/backend_agg.py', 'matplotlib/figure.py')
    historical_files = {str(p): digest((lib / p).read_bytes()) for p in source_paths}
    versions = source['versions']
    require(digest(historical) == versions['working']['file_sha256'] and
            digest((lib / 'matplotlib/tests/test_axes.py').read_bytes()) == versions['working']['test_file_sha256'],
            'Historical axis or maintainer test file differs from pinned commit')
    fixed_func = versions['working']['function_source']
    old_call = 'setter(self, max(vmin, vmax, oldmin), min(vmin, vmax, oldmax),'
    require(fixed_func.count(old_call) == historical.count(fixed_func.encode()) == 1, 'Source anchor differs')
    programs = [fixed_func, versions['faulty']['function_source'],
                fixed_func.replace(old_call, 'setter(self, ' + row['expression'][1:-1] + ',')]
    wheel = Path(util.find_spec('matplotlib').origin).parent
    records = {}
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp).resolve() / 'lib'
        shutil.copytree(str(lib), str(stage), ignore=shutil.ignore_patterns('__pycache__'))
        pkg = stage / 'matplotlib'
        for binary in wheel.rglob('*.so'):
            (pkg / binary.relative_to(wheel)).symlink_to(binary)
        if (wheel / '.dylibs').is_dir():
            (pkg / '.dylibs').symlink_to(wheel / '.dylibs')
        shutil.copyfile(str(wheel / 'mpl-data/matplotlibrc'), str(pkg / 'mpl-data/matplotlibrc'))
        env = dict(os.environ, PYTHONPATH=str(stage), MPLBACKEND='Agg', MPLCONFIGDIR=temp,
                   PYTHONNOUSERSITE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        for program, replacement in zip(PROGRAMS, programs):
            axis = historical.replace(fixed_func.encode(), replacement.encode())
            if program == 'historical_fault':
                require(digest(axis) == versions['faulty']['file_sha256'], 'Parent module differs')
            (pkg / 'axis.py').write_bytes(axis)
            raw = subprocess.check_output([sys.executable, '-B', str(Path(__file__).resolve()),
                                           '--worker', str(stage)], env=env, cwd=temp)
            records[program] = json.loads(raw)
            require(records[program]['axis_sha256'] == digest(axis), 'Worker used different source')
    observations = [{'case': k, 'input': v, 'expected': expected(v),
                     **{p: records[p]['outputs'][k] for p in PROGRAMS}} for k, v in inputs.items()]
    return {
        'scope': 'Post-hoc real-axis replay of three existing programs on one historical bug.',
        'source': {'repository': source['repository'], 'bugsinpy_bug': 24, 'bugsinpy_revision': source['bugsinpy_revision'],
                   'fixed': source['fixed'], 'parent': source['parent'], 'path': source['source_path'],
                   'test': source['test_path'] + '::test_set_ticks_inverted',
                   'historical_python_files_sha256': historical_files,
                   'test_sha256': versions['working']['test_file_sha256'], 'generated_expression': row['expression'],
                   'discovery_native_response_sha256': row['native_response_sha256'],
                   'repeat_id_with_identical_expression': repeat['id'],
                   'repeat_native_response_sha256': repeat['native_response_sha256']},
        'frozen_inputs_sha256': {str(f.relative_to(ANALYSIS)): digest(f.read_bytes()) for f in FROZEN},
        'runtime': {'python': platform.python_version(), 'implementation': platform.python_implementation(),
                    'system': platform.system(), 'os_version': platform.mac_ver()[0], 'architecture': platform.machine(),
                    'packages': {k: metadata.version(k) for k in ('matplotlib', 'numpy', 'cycler', 'kiwisolver',
                                       'python-dateutil', 'pyparsing', 'six', 'pytest', 'Pillow')},
                    'source_binding': {p: {k: v for k, v in r.items() if k != 'outputs'} for p, r in records.items()}},
        'summary': recount(observations, inputs), 'observations': observations,
    }


def verify(directory=HERE):
    result = read(Path(directory) / 'results.json')
    source, row, repeat, inputs = inputs_and_sources()
    require(result['frozen_inputs_sha256'] == {str(p.relative_to(ANALYSIS)): digest(p.read_bytes()) for p in FROZEN},
            'Frozen inputs changed')
    require(result['source']['generated_expression'] == row['expression'] and
            result['source']['repeat_native_response_sha256'] == repeat['native_response_sha256'] and
            result['source']['discovery_native_response_sha256'] == row['native_response_sha256'], 'Generated source differs')
    stats = recount(result['observations'], inputs)
    require(stats == result['summary'], 'Recount differs from archived summary')
    require(result['source']['fixed'] == source['fixed'] and result['source']['parent'] == source['parent'],
            'Upstream commit binding differs')
    controls = read(FROZEN[2])['matplotlib']['starts']
    saved_totals = [controls['working']['passed'], controls['faulty']['passed'], row['passed_count']]
    require([stats[p]['heldout_passed'] for p in PROGRAMS] == saved_totals, 'Real-axis and fixture totals differ')
    for observation in result['observations'][:len(PROBES)]:
        probe = repeat['grade']['probes'][observation['case']]
        require(observation['generated_regression'] == probe['output'], 'Public probe differs from frozen repeat')
    binding = result['runtime']['source_binding']
    for p, key in [('historical_fix', 'working'), ('historical_fault', 'faulty')]:
        require(binding[p]['axis_sha256'] == source['versions'][key]['file_sha256'], 'Historical module hash differs')
    for p in PROGRAMS:
        require(binding[p]['upstream_assertion_passed'] == stats[p]['probes_passed']['maintainer'],
                'Saved maintainer assertion disagrees with public bounds')
    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--check', action='store_true', help='recount recorded observations using the standard library')
    actions.add_argument('--replay', type=Path, metavar='CHECKOUT', help='repeat all public operations, compare bounds')
    actions.add_argument('--record', type=Path, metavar='CHECKOUT', help='create the observations JSON')
    actions.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, inputs_and_sources()[-1])))
    else:
        if args.record or args.replay:
            data = run(args.record or args.replay)
            if args.record:
                (HERE / 'results.json').write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
            else:
                require(read(HERE / 'results.json')['observations'] == data['observations'], 'Real-axis replay differs')
        print(json.dumps(verify(), indent=2))
