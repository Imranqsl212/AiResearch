"""Rebuild a paired slot list using only catalog metadata and prediction IDs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIN = '40f164d5b8f1d249bf95a6df8b74b577fd8e519d'
PREFIX = 'swe-external-audit-20261122-v1|'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rank(issue):
    return digest((PREFIX + issue).encode()), issue


def construct():
    protocol = digest((ROOT / 'protocol.md').read_bytes())
    receipt = json.loads((ROOT / 'protocol_freeze.json').read_text())
    assert receipt['sha256'] == protocol
    rosters = {}
    series = {}
    evidence = {}
    for arm in ('A', 'B'):
        raw = (ROOT / f'discovery_{arm}.json').read_bytes()
        meta = json.loads(raw)
        ids = meta['roster']
        assert len(ids) == len(set(ids)) and all(isinstance(x, str) and x for x in ids)
        rosters[arm] = set(ids)
        series[arm] = meta['submission']
        evidence[arm] = digest(raw)
    common = rosters['A'] & rosters['B']
    shared = sorted(common, key=rank)[:10]
    slots = []
    for arm in ('A', 'B'):
        chosen = shared + sorted(rosters[arm] - set(shared), key=rank)[:10-len(shared)]
        assert len(chosen) == 10
        slots.extend({'series': arm, 'instance_id': issue, 'selection_hash': rank(issue)[0]} for issue in chosen)
    return {'catalog_commit': PIN, 'protocol_sha256': protocol, 'submission': series,
            'discovery_sha256': evidence, 'roster_sizes': {a: len(r) for a, r in rosters.items()},
            'intersection_size': len(common), 'slots': slots}


if __name__ == '__main__':
    payload = construct()
    out = ROOT / 'selection.json'
    if out.exists():
        recorded = json.loads(out.read_text())
        recorded.pop('frozen_utc')
        if recorded != payload:
            raise ValueError('Selection differs from the frozen sample')
    else:
        payload['frozen_utc'] = datetime.now(timezone.utc).isoformat()
        with out.open('x') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(digest(out.read_bytes()), out.name)
