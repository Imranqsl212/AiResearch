"""Read the published benchmark endpoints after the sample is frozen."""
import hashlib
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from public_io import ROOT, fetch, get_key, list_s3


def patches(raw, selected):
    """Retain every matching prediction, including duplicate or empty patches."""
    output = defaultdict(list)
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        issue = obj['instance_id']
        if issue in selected:
            patch = obj['model_patch']
            data = None if patch is None else patch.encode()
            output[issue].append({
                'line': line_number,
                'present': bool(patch and patch.strip()),
                'bytes': len(data) if data is not None else None,
                'sha256': hashlib.sha256(data).hexdigest() if data is not None else None,
            })
    return output


def prediction_meta(series, selection, records, artifacts):
    name = selection['submission'][series]
    base = f'verified/{name}'
    slug = 'https://raw.githubusercontent.com/SWE-bench/experiments'
    url = f"{slug}/{selection['catalog_commit']}/evaluation/{base}/results/results.json"
    results, artifacts['results'] = fetch(url)
    raw, artifacts['predictions'] = get_key(f'{base}/all_preds.jsonl')
    return json.loads(results), patches(raw, records)


def run():
    selection = json.loads((ROOT / 'selection.json').read_bytes())
    output = {'selection_sha256': hashlib.sha256((ROOT/'selection.json').read_bytes()).hexdigest(),
              'sources': {}, 'rows': []}
    for arm in ('A', 'B'):
        ids = [s['instance_id'] for s in selection['slots'] if s['series'] == arm]
        base = 'verified/' + selection['submission'][arm]
        artifacts = output['sources'][arm] = {}
        results, records = prediction_meta(arm, selection, ids, artifacts)
        log_keys = set(list_s3(base+'/logs/'))

        def check(issue):
            preds = records[issue]
            all_presence = {r['present'] for r in preds}
            row = {
                'series': arm, 'instance_id': issue,
                'published_resolved': issue in results['resolved'],
                'published_categories': [k for k, ids_ in results.items() if issue in ids_],
                'nonempty_prediction': all_presence.pop() if len(all_presence) == 1 else None,
                'predictions': preds, 'evaluator_resolved': None,
                'evaluation_log': None, 'evaluation_patch': None, 'prediction_matches_eval_patch': None,
            }
            if arm == 'B':
                key = f'{base}/logs/{issue}/report.json'
                if key in log_keys:
                    raw_report, row['evaluation_log'] = get_key(key)
                    grade = json.loads(raw_report)[issue]
                    assert isinstance(grade['resolved'], bool)
                    row['evaluator_resolved'] = grade['resolved']
                    row['grade_fields'] = {k:v for k,v in grade.items() if k != 'tests_status'}
                    row['grade_test_counts'] = {
                        group: {outcome:len(tests) for outcome,tests in buckets.items()}
                        for group, buckets in grade['tests_status'].items()
                    }
                patch_key = f'{base}/logs/{issue}/patch.diff'
                if patch_key in log_keys:
                    _, row['evaluation_patch'] = get_key(patch_key)
                    row['prediction_matches_eval_patch'] = any(
                        p['sha256'] == row['evaluation_patch']['sha256'] for p in preds)
            else:
                key = f"{base}/logs/{issue}.{selection['submission'][arm]}.eval.log"
                if key in log_keys:
                    raw_log, row['evaluation_log'] = get_key(key)
                    lines = raw_log.decode(errors='replace').splitlines()
                    row['log_markers'] = [{'line':i, 'label':s.strip()} for i,s in enumerate(lines,1)
                                          if re.match(r'^>>>>> [\w ();-]+\s*$',s)]
            return row

        with ThreadPoolExecutor(3) as pool:
            output['rows'].extend(pool.map(check, ids))
    (ROOT/'endpoints.json').write_text(json.dumps(output, indent=2)+'\n')


if __name__ == '__main__':
    run()
