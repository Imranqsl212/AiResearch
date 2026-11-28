"""Reserve fresh native subscription decisions for the six original Matplotlib prompts."""
from argparse import ArgumentParser
import fcntl
from pathlib import Path
import shutil
import subprocess

from analysis import matplotlib_replication_report as study
from experiments import production_patch as discovery

core = discovery.core
prior, cli = core.prior, core.cli
PUBLIC = study.DEFAULT
PRIVATE = core.ROOT / '.local_private/matplotlib_replication_20261128'
DESIGN = 'docs/MATPLOTLIB_REPLICATION_20261128.md'
BOUND = (DESIGN, 'docs/MATPLOTLIB_ORDER_TYPES_20261128.md', 'experiments/matplotlib_replication.py',
         'analysis/matplotlib_replication_report.py', 'analysis/matplotlib_order_types.py', *discovery.BOUND)


def materials():
    data, hashes = study.source_materials(discovery.PUBLIC)
    assignments = study.assignments(data)
    source = data['sources.json']['matplotlib']
    manifest = {
        'design': DESIGN, 'seed': study.SEED, 'effort': 'low', 'included_window_end': core.RESET,
        'eligible_for_main_analysis': False, 'discovery_files_sha256': hashes,
        'workflow_sha256': {p: cli.file_sha(core.ROOT / p) for p in BOUND},
        'source': {'repository': source['repository'], 'fixed_commit': source['fixed'], 'parent_commit': source['parent'],
                   'path': source['source_path'], 'file_sha256': {s: source['versions'][s]['file_sha256'] for s in study.STATES}},
        'mixed_unshown_probe': study.MIXED, 'assignments': assignments,
    }
    return manifest, data


def freeze():
    manifest, _ = materials()
    launcher = Path(shutil.which('codex')).resolve()
    login = subprocess.run([str(launcher), 'login', 'status'], capture_output=True, text=True,
                           check=True, env=cli.child_environment('codex'))
    if 'logged in using chatgpt' not in (login.stdout + login.stderr).lower():
        raise ValueError('Included subscription authentication required')
    prior.persist(PUBLIC / 'plan.json', prior.pretty(manifest))
    info = {'launcher': str(launcher), 'launcher_sha256': cli.file_sha(launcher),
            'version': subprocess.check_output([str(launcher), '--version'], text=True).strip(),
            'plan_sha256': cli.file_sha(PUBLIC / 'plan.json'), 'auth': 'CHATGPT_LOGIN'}
    path = PRIVATE / 'frozen.json'
    if path.exists():
        if any(prior.read(path)[k] != v for k, v in info.items()):
            raise ValueError('Different frozen launcher or design')
    else:
        cli.record(path, {**info, 'utc': cli.now()})
    print('Frozen 24 matched calls', info['plan_sha256'])


def load():
    plan, data = materials()
    info = prior.read(PRIVATE / 'frozen.json')
    if (PUBLIC / 'plan.json').read_bytes() != prior.pretty(plan) or info['plan_sha256'] != cli.file_sha(PUBLIC / 'plan.json'):
        raise ValueError('Frozen inputs changed')
    return plan['assignments'], data, info


def prompt_for(cell, data):
    prompt = study.original.prompt(cell, cell['arm'], data['sources.json'], data['calibration.json'])
    if study.digest(prompt) != cell['prompt_sha256']:
        raise ValueError('Prompt differs from original matched cell')
    return prompt


def outcome(cell, prompt, info, data):
    folder = PRIVATE / 'calls' / cell['id']
    row = {**cell, 'status': 'INTERRUPTED' if folder.exists() else 'UNSTARTED', 'grade': None}
    if not (folder / 'process.json').exists():
        return row
    start = prior.read(folder / 'start.json')
    proc = prior.read(folder / 'process.json')
    if (start['cell'] != cell['id'] or start['argv'] != prior.command_for(info['launcher'], study.MODEL)
            or start['prompt_sha256'] != cell['prompt_sha256'] or (folder / 'prompt.txt').read_bytes() != prompt):
        raise ValueError('Prompt reservation or launcher arguments changed')
    raw = (folder / 'stdout.bin').read_bytes()
    err = (folder / 'stderr.bin').read_bytes()
    if study.digest(raw) != proc['stdout_sha256'] or study.digest(err) != proc['stderr_sha256']:
        raise ValueError('Native response changed')
    row.update(native_response_sha256=proc['stdout_sha256'], elapsed_seconds=proc['elapsed_seconds'])
    if proc['error'] or proc['returncode']:
        row['status'] = prior.codex.failure_kind([(raw + err).decode(errors='replace')], proc['error'] or 'CLI_ERROR')
        return row
    try:
        response, _ = cli.extract('codex', raw)
        choice = cli.base.strict(response)
        if choice == {'action': 'keep'}:
            expr = data['calibration.json']['matplotlib']['starts'][cell['start']]['expression']
        elif isinstance(choice, dict) and set(choice) == {'action', 'expression'} and choice['action'] == 'replace':
            expr = choice['expression']
        else:
            raise ValueError('Invalid action record')
        grade = study.grade(choice['action'], expr, cell, data['calibration.json'])
    except study.original.base.Rejected:
        row['status'] = 'INVALID_EXPRESSION'
    except (TypeError, KeyError, ValueError):
        row['status'] = 'INVALID_RESPONSE'
    else:
        row.update(status='OK', grade=grade)
    return row


def collect():
    cells, data, info = load()
    if cli.file_sha(Path(info['launcher'])) != info['launcher_sha256']:
        raise ValueError('Frozen launcher changed')
    with (core.QUOTA / 'native.lock').open('a+b') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for cell in cells:
            folder = PRIVATE / 'calls' / cell['id']
            prompt = prompt_for(cell, data)
            if not folder.exists():
                prior.check_memory()
                core.require_remaining()
                argv = prior.command_for(info['launcher'], study.MODEL)
                folder.mkdir(mode=0o700, parents=True)
                cli.write(folder / 'prompt.txt', prompt)
                cli.record(folder / 'start.json', {'cell': cell['id'], 'utc': cli.now(), 'argv': argv,
                                                    'prompt_sha256': cell['prompt_sha256']})
                cli.record(folder / 'process.json', cli._launch(argv, prompt, folder, 'codex', prior.TIMEOUT))
            row = outcome(cell, prompt, info, data)
            if row['status'] != 'INTERRUPTED':
                prior.persist(folder / 'event.json', prior.pretty(row))
            print(cell['id'], row['status'], flush=True)
            if row['status'] in prior.codex.ACCOUNT_ERRORS or row['status'] == 'MODEL_UNAVAILABLE':
                raise RuntimeError(row['status'])


def export():
    cells, data, info = load()
    rows = []
    for cell in cells:
        row = outcome(cell, prompt_for(cell, data), info, data)
        if row['status'] not in ('INTERRUPTED', 'UNSTARTED'):
            if row != prior.read(PRIVATE / 'calls' / cell['id'] / 'event.json'):
                raise ValueError('Captured observation differs')
        rows.append(row)
    artifact = {'plan_sha256': info['plan_sha256'], 'frozen_at_utc': info['utc'], 'cli_version': info['version'],
                'eligible_for_main_analysis': False, 'rows': rows, 'summary': study.summarize(rows)}
    prior.persist(PUBLIC / 'results.json', prior.pretty(artifact))
    text = study.verify()
    prior.persist(PUBLIC / 'comparison.md', text.encode())
    print(text)


if __name__ == '__main__':
    actions = {'freeze': freeze, 'collect': collect, 'export': export}
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=actions)
    actions[parser.parse_args().action]()
