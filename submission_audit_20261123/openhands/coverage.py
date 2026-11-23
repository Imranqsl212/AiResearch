"""Read the released message histories as data. Never run their tool calls."""
import argparse
import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parents[1] / 'external_audit_20261122'
sys.path.insert(0, str(PRIOR))
from public_io import fetch


def read_json(path):
    return json.loads(path.read_bytes())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def summarize(rows):
    groups = {}
    for label, subset in [('full', rows), ('held_out', [r for r in rows if not r['discovery_issue']])]:
        groups[label] = {
            'indexed': len(subset),
            'unique_trace_digests': len({r['trace_sha256'] for r in subset}),
            'with_prediction': sum(r['in_prediction_roster'] for r in subset),
            'listed_as_resolved': sum(r['resolved'] for r in subset),
            'root_types': dict(Counter(r['format'] for r in subset)),
            'last_roles': dict(Counter(r['final_role'] for r in subset)),
            'with_assistant_finish_or_submit': sum(bool(r['finish_locations']) for r in subset),
            'with_separate_response_or_stop_field': sum(bool(r['separate_fields']) for r in subset),
            'last_role_by_resolution': {
                str(value).lower(): dict(Counter(r['final_role'] for r in subset if r['resolved'] == value))
                for value in [True, False]
            },
            'official_categories': {k:sum(k in r['grading_categories'].split('|') for r in subset)
                                    for k in ['resolved','no_generation','no_logs']},
        }
    return groups


def extract(issue, archive, roster, outcomes, discovery):
    url = archive['per_instance_url_template'].format(instance_id=issue)
    raw, src = fetch(url)
    obj = json.loads(raw)
    fields, positions = [], []
    messages = obj if isinstance(obj, list) else []
    if isinstance(obj, dict):
        fields = sorted(set(obj) & {'response','stop','exit_status','termination_reason','agent_state'})
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            raise ValueError(f'Invalid message type in {issue}/{i}')
        if m.get('role') == 'assistant':
            for j, call in enumerate(m.get('tool_calls') or []):
                if call.get('function', {}).get('name') in {'finish', 'submit'}:
                    positions.append(f'/{i}/tool_calls/{j}')
    return {'instance_id':issue, 'discovery_issue':issue in discovery,
            'in_prediction_roster':issue in roster, 'resolved':issue in outcomes['resolved'],
            'grading_categories':'|'.join(k for k,v in outcomes.items() if issue in v),
            'format':type(obj).__name__, 'message_count':len(messages),
            'final_role':messages[-1].get('role','unknown') if messages else 'unknown',
            'assistant_content_messages':sum(m.get('role')=='assistant' and bool(m.get('content')) for m in messages),
            'finish_locations':'|'.join(positions), 'separate_fields':'|'.join(fields),
            'trace_url':url,'trace_sha256':src['sha256'],'trace_bytes':len(raw)}


def build():
    receipt = read_json(HERE/'plan.receipt.json')
    assert digest((HERE/'plan.md').read_bytes()) == receipt['sha256']
    discovery = read_json(PRIOR/'discovery_B.json')
    selection = read_json(PRIOR/'selection.json')
    assert digest((PRIOR/'discovery_B.json').read_bytes()) == selection['discovery_sha256']['B']
    archive = discovery['trajectory_collection']
    xml, index = fetch(archive['listing_url'])
    root = ET.fromstring(xml)
    assert root.findtext('{*}IsTruncated') == 'false'
    prefix = archive['s3_uri'].split('swe-bench-submissions/',1)[1]+'/'
    keys = [node.text for node in root.findall('{*}Contents/{*}Key')]
    assert all(k.startswith(prefix) and k.endswith('.json') and '/' not in k[len(prefix):] for k in keys)
    ids = sorted(k[len(prefix):-5] for k in keys)
    assert len(ids) == len(set(ids)) == archive['listed_object_count']
    raw, grade_source = fetch(discovery['outcomes']['url'])
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==discovery['outcomes']['git_blob_sha1_from_index']
    outcomes = {k:set(v) for k,v in json.loads(raw).items()}
    roster = set(discovery['roster'])
    old = {r['instance_id'] for r in selection['slots']}
    assert old <= set(ids) and roster <= set(ids) and outcomes['resolved'] <= set(ids)
    def one(issue):
        return extract(issue, archive, roster, outcomes, old)
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = []
        for i, row in enumerate(pool.map(one, ids),1):
            rows.append(row)
            if i % 75 == 0:
                print(f'{i}/{len(ids)} archives checked',flush=True)
    with (HERE/'rows.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    report={'plan_sha256':receipt['sha256'],'selection_sha256':digest((PRIOR/'selection.json').read_bytes()),
            'listing':index,'original_listing_sha256':archive['listing_sha256'],'published_results':grade_source,
            'row_sha256':digest((HERE/'rows.csv').read_bytes()),'groups':summarize(rows)}
    (HERE/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['groups']))


def verify():
    report=read_json(HERE/'summary.json')
    assert digest((HERE/'plan.md').read_bytes()) == report['plan_sha256'] == read_json(HERE/'plan.receipt.json')['sha256']
    assert digest((PRIOR/'selection.json').read_bytes()) == report['selection_sha256']
    assert digest((HERE/'rows.csv').read_bytes()) == report['row_sha256']
    with (HERE/'rows.csv').open(newline='',encoding='utf-8') as stream:
        rows=list(csv.DictReader(stream))
    for row in rows:
        for key in ['resolved','in_prediction_roster','discovery_issue']:
            assert row[key] in {'True','False'}
            row[key] = row[key]=='True'
    assert len({r['instance_id'] for r in rows})==len(rows)
    assert summarize(rows)==report['groups']
    print('Verified archive rows and coverage summaries.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true',help='check saved outputs offline')
    if parser.parse_args().verify:
        verify()
    else:
        build()
