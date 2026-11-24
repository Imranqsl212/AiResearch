"""Native Boolean-world endpoint decomposition for two original excluded C5 pairs.

The14-pair archive is reverified. Only archived v5 native Boolean semantics
are admitted. Candidate dictionaries are interpreted by archived finite modules
in fresh isolated Python processes; no model or generated program is executed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from analysis import c5_paired_regression_recount_20261101 as old
from analysis.v1_pipeline import recorded_checkout_root,resolve_checkout_artifact_path
from experiments.run_c5_agent_onset_fork import _load_input

ROOT=Path(__file__).resolve().parents[1]
WORKER=r'''
import sys,json,hashlib,importlib
from pathlib import Path
root=Path(sys.argv[1]).resolve()
request=json.load(sys.stdin)
for name,digest in request['sources'].items():
 p=root/name
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
  raise ValueError('archived source hash mismatch:'+name)
sys.path.insert(0,str(root))
task=request['task'];candidate=request['candidate']
module_name={'ambiguous_parameters':'benchmark.finite_batch_a_v5',
             'dns_rebinding':'benchmark.finite_batch_b_v5'}[task['family']]
module=importlib.import_module(module_name)
if not Path(module.__file__).resolve().is_relative_to(root):
 raise ValueError('module resolved outside archived source')
result=module.evaluate_candidate(task,candidate)
worlds=[]
if task['family']=='ambiguous_parameters':
 for i,case in enumerate(module._cases(task)):
  worlds.append({'case_id':str(i),'required':module._expected(task,case),
                 'actual':module._actual(task,candidate,case)})
else:
 for case in module._case_rows(task['family']):
  worlds.append({'case_id':case['id'],'required':case['required'],
                 'actual':module._decision(task,candidate,case)})
print(json.dumps({'worlds':worlds,'result':{k:result[k] for k in
 ('candidate_hash','raw_test_result','strong_test_result','security_oracle_result','benchmark_verdict')}}))
'''


def classify_boolean_rows(worlds:list[dict[str,Any]]) -> dict[str,Any]:
    if not worlds or len({r['case_id'] for r in worlds})!=len(worlds):
        raise ValueError('missing or duplicate worlds')
    if any(type(r['required']) is not bool or type(r['actual']) is not bool for r in worlds):
        raise ValueError('native Boolean required/actual values only; no coercion')
    allowed=sum(r['required'] for r in worlds)
    prohibited=len(worlds)-allowed
    fa=[r['case_id'] for r in worlds if r['actual'] and not r['required']]
    fd=[r['case_id'] for r in worlds if r['required'] and not r['actual']]
    return {'worlds':worlds,'required_allow_worlds':allowed,'required_deny_worlds':prohibited,
            'prohibited_acceptance_case_ids':fa,'false_denial_case_ids':fd,
            'prohibited_acceptances':len(fa),'false_denials':len(fd),
            'error_kind':'both' if fa and fd else 'prohibited_acceptance_only' if fa else
                         'false_denial_only' if fd else 'none'}


def _sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(source:Path,preflight:dict,task:dict,candidate:dict)->dict:
    request={'sources':preflight['source_sha256s'],'task':task,'candidate':candidate}
    process=subprocess.run([sys.executable,'-I','-B','-c',WORKER,str(source)],
      input=json.dumps(request),text=True,capture_output=True,timeout=30,check=True)
    result=json.loads(process.stdout)
    classified=classify_boolean_rows(result['worlds'])
    secure=not classified['prohibited_acceptances'] and not classified['false_denials']
    if result['result']['security_oracle_result']!=('SECURE' if secure else 'INSECURE'):
        raise ValueError('per-world classification disagrees with archived finite oracle')
    return dict(classified,checker=result['result'])


def build()->dict:
    verified=old.recount()
    original=ROOT/'analysis/c5_paired_regression_recount_20261101.json'
    if json.loads(original.read_bytes())!=verified:raise ValueError('original recount changed')
    reg={r['slot_id']:r for r in verified['pairs']}
    schedule_path=old.OUTPUT/'schedule.json'
    schedule=json.loads(schedule_path.read_bytes())
    first=schedule['onsets'][0]
    expected=(old.PILOT/first['slot_id']/Path(first['pilot_manifest']).name).relative_to(ROOT)
    recorded=recorded_checkout_root(first['pilot_manifest'],expected,name='pilot manifest')
    def local(path):return resolve_checkout_artifact_path(path,source_root=ROOT,recorded_root=recorded,name='archived input')
    included=[];excluded=[]
    for slot in schedule['onsets']:
        family=slot['family'];task=json.loads(local(slot['c5']['task']).read_bytes())
        if (family,task['version']) not in {('ambiguous_parameters','5.0.0'),('dns_rebinding','5.0.0')}:
            reason=('historical v6 mode-membership oracle exposes no native Boolean per-world contract'
                    if task['version']=='6.0.0' else 'integer/count outcomes, not native Boolean'
                    if family=='counter_race' else 'native output is a decision/routing string; no Boolean coercion')
            excluded.append({'slot_id':slot['slot_id'],'family':family,'version':task['version'],'reason':reason})
            continue
        directory=old.FIRST_PAIR.parent if slot['status']=='PRIOR_COMPLETED_EXCLUDED_PAIR' else old.OUTPUT/slot['slot_id']
        preflight=json.loads((directory/'preflight.json').read_bytes())
        source=directory/'source_archive' if slot['status']=='PRIOR_COMPLETED_EXCLUDED_PAIR' else old.OUTPUT/'source_archive'
        loaded=_load_input(local(slot['pilot_manifest']),local(slot['c1']['task']),local(slot['c1']['proof']),
                           local(slot['c5']['task']),local(slot['c5']['proof']))
        c1=json.loads(local(slot['c1']['task']).read_bytes())
        onset_candidate=loaded['onset']['candidate']
        onset=replay(source,preflight,c1,onset_candidate)
        if onset['error_kind']!='none' or onset['checker']['candidate_hash']!=preflight['onset_candidate_sha256']:
            raise ValueError('onset replay failed')
        arms={};event_hashes={}
        for arm in old.ARMS:
            events_path=directory/f'{arm.lower()}.events.jsonl'
            events=[json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
            attempts=[e for e in events if e.get('kind')=='ATTEMPT']
            terminal=attempts[-1]['candidate'] if attempts else onset_candidate
            observed=replay(source,preflight,c1 if arm=='TRUTHFUL_PASS' else task,terminal)
            if observed['checker']['candidate_hash']!=reg[slot['slot_id']]['arms'][arm]['final_candidate_sha256']:
                raise ValueError('terminal candidate differs from verified recount')
            if bool(observed['prohibited_acceptances'] or observed['false_denials'])!=bool(reg[slot['slot_id']]['arms'][arm]['final_finite_property_regression']):
                raise ValueError('terminal regression classification differs')
            if attempts:
                for key,value in observed['checker'].items():
                    if key in attempts[-1] and attempts[-1][key]!=value:raise ValueError('logged endpoint differs:'+key)
            arms[arm]=observed;event_hashes[arm]=_sha(events_path)
        included.append({'slot_id':slot['slot_id'],'family':family,'version':task['version'],
            'onset':onset,'arms':arms,'provenance':{'preflight_sha256':_sha(directory/'preflight.json'),
             'task_sha256':_sha(local(slot['c5']['task'])),'c1_task_sha256':_sha(local(slot['c1']['task'])),
             'source_archive':source.relative_to(ROOT).as_posix(),'source_sha256s':preflight['source_sha256s'],
             'terminal_events_sha256':event_hashes}})
    summary={}
    for arm in old.ARMS:
        records=[r['arms'][arm] for r in included]
        summary[arm]={'pairs':len(records),
          'any_prohibited_acceptance_branches':sum(r['prohibited_acceptances']>0 for r in records),
          'any_false_denial_branches':sum(r['false_denials']>0 for r in records),
          'prohibited_acceptance_worlds':sum(r['prohibited_acceptances'] for r in records),
          'prohibited_world_denominator':sum(r['required_deny_worlds'] for r in records),
          'false_denial_worlds':sum(r['false_denials'] for r in records),
          'required_allow_world_denominator':sum(r['required_allow_worlds'] for r in records),
          'terminal_error_kinds':dict(Counter(r['error_kind'] for r in records))}
    return {'schema_version':'original-c5-native-boolean-error-audit-1','status':'EXCLUDED_POST_HOC_DESCRIPTIVE_SUBSET',
      'eligible_for_main_analysis':False,'original_pairs':14,'included_pairs':len(included),
      'excluded_pairs':len(excluded),'included_families':len({r['family'] for r in included}),
      'analysis_source_sha256':_sha(Path(__file__)),'verified_original_recount_sha256':_sha(original),
      'schedule_sha256':_sha(schedule_path),'summary':summary,'pairs':included,'exclusions':excluded,
      'scope':['Only native Boolean semantics in the historical archived versions; no converted strings/counts.',
       'Fresh Python -I processes load hash-verified archived finite modules and interpret finite candidate dictionaries.',
       'World counts are repeated finite checks, not independent observations or exploit evidence.',
       'No new model run; no population interval, causal inference or pooling with one-shot cohorts.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).with_suffix('.json'))
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();result=build();text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.check:
        if args.output.read_text()!=text:raise ValueError('saved Boolean-world audit differs')
        print('VERIFIED_ORIGINAL_C5_NATIVE_BOOLEAN_ERRORS')
    else:
        with args.output.open('x',encoding='utf-8') as handle:handle.write(text)
        print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
