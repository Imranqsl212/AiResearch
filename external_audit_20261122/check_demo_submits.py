"""Post hoc check of exact assistant submit actions in SWE-agent history."""
import hashlib
import json
from pathlib import Path

from public_io import ROOT, fetch


def check():
    rows = []
    for record in json.loads((ROOT/'primary_A.json').read_bytes())['rows']:
        row = {'instance_id':record['instance_id'], 'trace_sha256':record['trace_sha256'], 'matches':None}
        if record['trace_available']:
            path = Path(record['raw_trace_path'])
            raw = path.read_bytes() if path.exists() else fetch(record['trace_url'])[0]
            assert hashlib.sha256(raw).hexdigest() == record['trace_sha256']
            history = json.loads(raw)['history']
            row['matches'] = [
                {'locator':f'/history/{i}/action', 'is_demo':event.get('is_demo',False)}
                for i,event in enumerate(history) if event.get('role') == 'assistant'
                and (event.get('action') or '').strip() == 'submit'
            ]
        rows.append(row)
    (ROOT/'demo_submits.json').write_text(json.dumps({
        'design':'post hoc diagnostic on the frozen sample; exact assistant history.action only',
        'rows':rows,
    },indent=2)+'\n')


if __name__ == '__main__':
    check()
