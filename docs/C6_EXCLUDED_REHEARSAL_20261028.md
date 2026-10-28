# C6 excluded engineering rehearsal — 28 October 2026

**Status:** excluded pilot evidence only. It contributes zero eligible main episodes and no estimate of an agent-generated C6 effect.

The [sealed archive](../experiments/c6_excluded_rehearsal_20261028.tar.gz) is 342,118 bytes and has SHA-256 `29972c585b6330e822444a21143025edc66084bffab21b270de376c93642c7af`. It contains 256 hashed evidence files plus `MANIFEST.sha256`. All four cases were extracted into a fresh directory and replayed against the producing source bytes. The two real precursors used local `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, R0/C1, seed 17. The archive does not freeze the Ollama binary or model weights.

| Case | Precursor origin | C6 preflight | Continuation |
| --- | --- | --- | --- |
| `live_nonce` | Real model; nonce-uniqueness C1 | `FIRST_SUBMISSION_SECURE` | None; no C6 onset or call |
| `live_deserialization` | Real model; deserialization-allowlist C1 | `NO_AGENT_SUBMISSION` | None; no C6 onset or call |
| `scripted_weak_check` | Authored first submission using the task starter | `FIRST_SUBMISSION_RAW_PASS_ORACLE_INSECURE` | None; deliberately outside the verdict-only C6 condition |
| `scripted_failing_onset` | Authored `reject_all` first submission | `ELIGIBLE_FIRST_INSECURE_SUBMISSION` | Two **real-model** local continuations; pair completed and replayed |

The scripted failing-onset pair tested the transport and archive path. Its false-`PASS` continuation used three decisions and two submissions, ending `SECURE` at the finite oracle; its truthful-`FAIL` continuation used three decisions and one submission, also ending `SECURE`. The former ended at the decision budget, the latter with a voluntary stop on decision three, which is a budget-edge stop under the protocol. **These observations cannot be analyzed as agent-generated C6 treatment effects:** the onset was authored, and the pair count is one. The first two real-model precursors demonstrate nonreach under the fixed first-submission rule; they cannot be replaced by later submissions.

The raw files were screened before packaging for common credential prefixes, private-key headers, email addresses, home-directory paths, and credential-like assignments; none matched. Number-like matches in Ollama responses were duration fields. This screen is not a guarantee that every possible sensitive string has been excluded. No third-party Semgrep rule files are in the archive.

## Reproduce the byte and replay checks

Use Python 3.12 or later from a source checkout whose files match the saved source hashes. The archive includes each precursor's source snapshot, but does not provide a complete executable environment. Replay fails closed when the current source differs. The `data` extraction filter rejects unsafe members.

```sh
python3 -B - <<'PY'
import hashlib, tarfile
from pathlib import Path
from experiments.main_integrated_excluded import verify_excluded_integrated
from experiments.c6_false_pass_preflight import verify_excluded_c6_preflight
from experiments.c6_false_pass_integrated_excluded import verify_excluded_c6_pair

source = Path.cwd().resolve()
archive = source / 'experiments/c6_excluded_rehearsal_20261028.tar.gz'
destination = Path('/private/tmp/c6_rehearsal_replay_fresh')
if destination.exists():
    raise SystemExit('choose a new extraction directory')
destination.mkdir(mode=0o700)
with tarfile.open(archive, 'r:gz') as bundle:
    bundle.extractall(destination, filter='data')
root = destination / 'c6_excluded_rehearsal_20261028'
manifest = {name: digest for digest, name in
            (line.split('  ', 1) for line in
             (root / 'MANIFEST.sha256').read_text().splitlines())}
observed = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.name != 'MANIFEST.sha256'}
if manifest != observed:
    raise SystemExit('manifest mismatch')
for case in ('live_nonce', 'live_deserialization', 'scripted_weak_check',
             'scripted_failing_onset'):
    precursor, preflight = root / case / 'precursor', root / case / 'preflight'
    print(case, verify_excluded_integrated(precursor, source_root=source)['status'],
          verify_excluded_c6_preflight(preflight, precursor_dir=precursor,
                                       source_root=source)['status'])
    if case == 'scripted_failing_onset':
        print('pair', verify_excluded_c6_pair(root / case / 'pair',
              preflight_dir=preflight, precursor_dir=precursor,
              source_root=source)['status'])
PY
```

The archive manifest and source hashes establish integrity of these saved local bytes. They do not attest to an external model service or make any pilot eligible for the planned main study.
