"""Join archived endpoint and trajectory evidence on the frozen slots. Offline."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from freeze_selection import construct

ROOT = Path(__file__).resolve().parent
MEASURES = ('edit_attempt', 'confirmed_edit', 'verification_attempt', 'explicit_finish')
CLASSES = ('agent_acknowledged', 'controller_boundary', 'both', 'unknown')


def read(name):
    return json.loads((ROOT/name).read_bytes())


def index(rows, default=None):
    records = {(r.get('series', default), r['instance_id']):r for r in rows}
    assert len(records) == len(rows)
    return records


def render():
    frozen = read('selection.json')
    assert construct() == {k:v for k,v in frozen.items() if k != 'frozen_utc'}
    keys = [(x['series'], x['instance_id']) for x in frozen['slots']]
    endpoint_file = read('endpoints.json')
    assert endpoint_file['selection_sha256'] == hashlib.sha256((ROOT/'selection.json').read_bytes()).hexdigest()
    ends = index(endpoint_file['rows'])
    primary = {}
    for arm in ('A','B'):
        primary.update(index(read(f'primary_{arm}.json')['rows'], arm))
    checks = index(read('independent_checks.json')['rows'])
    receipt = (ROOT/'independent_checks.sha256').read_text().split()[0]
    assert receipt == hashlib.sha256((ROOT/'independent_checks.json').read_bytes()).hexdigest()
    assert endpoint_file['sources']['A']['predictions']['sha256'] == read('discovery_A.json')['sources']['predictions']['raw_sha256']
    assert endpoint_file['sources']['B']['predictions']['sha256'] == read('discovery_B.json')['roster_source']['sha256']
    assert set(keys) == set(ends) == set(primary) == set(checks)
    rows = []
    for key in keys:
        arm, issue = key
        trace, endpoint, other = primary[key], ends[key], checks[key]
        assert trace.get('trace_sha256') == other.get('raw_sha256')
        grades = endpoint['published_resolved'], endpoint['evaluator_resolved']
        stop = trace['stop_class']
        assert stop in CLASSES
        assert all(trace[k] is None or type(trace[k]) is bool for k in MEASURES)
        trace_hash = trace.get('trace_submission_sha256')
        preds = endpoint['predictions']
        rows.append({
            'series':arm, 'instance_id':issue, 'catalog_resolved':grades[0],
            'patch_nonempty':endpoint['nonempty_prediction'],
            **{m:trace[m] for m in MEASURES}, 'stop_class':stop,
            'last_observable_agent_action':(other.get('last_observable_agent_action') or {}).get('type'),
            'last_observable_agent_action_pointer':(other.get('last_observable_agent_action') or {}).get('locator'),
            'instance_report_resolved':grades[1],
            'grade_agreement':None if grades[1] is None else grades[0]==grades[1],
            'trace_patch_matches_prediction':None if not trace_hash else any(trace_hash==p['sha256'] for p in preds),
            'eval_patch_matches_prediction':endpoint['prediction_matches_eval_patch'],
            'prediction_rows':len(preds), 'distinct_prediction_digests':len({p['sha256'] for p in preds}),
            'failed_but_requested_finish':False if grades[0] else trace['explicit_finish'],
            'resolved_with_controller_boundary':False if not grades[0] else
                {'controller_boundary': True, 'agent_acknowledged': False, 'both': None, 'unknown': None}[stop],
            'independent_stop_class':other['stop_class'],
            'independent_explicit_finish':other['explicit_finish'],
            'stop_codings_agree':(stop,trace['explicit_finish'])==(other['stop_class'],other['explicit_finish']),
            'trace_url':trace.get('trace_url'), 'trace_sha256':trace.get('trace_sha256'),
            'eval_log_url':(endpoint['evaluation_log'] or {}).get('url'),
            'eval_patch_url':(endpoint['evaluation_patch'] or {}).get('url'),
        })
    with (ROOT/'episodes.csv').open('w',newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k:'unknown' if v is None else v for k,v in row.items()})
    stats = {}
    for arm in ('A','B','combined'):
        data = [r for r in rows if arm=='combined' or r['series']==arm]
        stats[arm] = {
            'n':len(data), 'trace_files':sum(bool(r['trace_sha256']) for r in data),
            'published_resolved':sum(r['catalog_resolved'] for r in data),
            'stop_class':dict(Counter(r['stop_class'] for r in data)),
            'by_outcome':{label:dict(Counter(r['stop_class'] for r in data if r['catalog_resolved']==test))
                          for label,test in [('resolved',True),('unresolved',False)]},
            'measures':{field:{state:sum(r[field] is value for r in data)
                               for state,value in [('yes',True),('no',False),('unknown',None)]}
                        for field in (*MEASURES,'patch_nonempty','grade_agreement','eval_patch_matches_prediction',
                                      'trace_patch_matches_prediction','stop_codings_agree')},
            'failed_but_requested_finish':sum(r['failed_but_requested_finish'] is True for r in data),
            'failed_with_unknown_finish':sum(r['failed_but_requested_finish'] is None for r in data),
            'resolved_with_controller_boundary':sum(r['resolved_with_controller_boundary'] is True for r in data),
            'resolved_with_unknown_cause':sum(r['resolved_with_controller_boundary'] is None for r in data),
        }
    (ROOT/'summary.json').write_text(json.dumps(stats,indent=2)+'\n')


if __name__ == '__main__':
    render()
