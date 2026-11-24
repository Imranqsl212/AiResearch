"""Read-only historical prefix audit, distinct from announced-budget intervention."""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path
from statistics import fmean
from analysis import c5_paired_regression_recount_20261101 as prior
from analysis.c5_budget_statistics import _csv

ARMS=prior.ARMS


def trajectory(events):
    """Retained state after each actual decision; completed endpoints absorb later prefixes."""
    state=1;states=[];actions=Counter();entries=recoveries=0;transitions=[]
    for number,event in enumerate(events,1):
        kind=event['kind'];actions[kind]+=1;before=state
        if kind=='ATTEMPT':
            label=event['security_oracle_result']
            if label not in ('SECURE','INSECURE'):raise ValueError('indeterminate historical state')
            state=int(label=='SECURE')
        if before==1 and state==0:entries+=1
        if before==0 and state==1:recoveries+=1
        transitions.append({'decision':number,'action':kind,'correct_before':before,'correct_after':state})
        states.append(state)
    if not 1<=len(states)<=3:raise ValueError('historical decision range changed')
    return {'decisions':len(states),'actions':dict(actions),'correct_prefixes':states+[state]*(3-len(states)),
            'entry_events':entries,'recovery_events':recoveries,'ever_error':0 in states,
            'terminal_correct':state,'transitions':transitions}


def audit():
    verified=prior.recount()
    if json.loads(prior.OUT.read_text())!=verified:raise ValueError('prior verified recount differs')
    schedule=json.loads((prior.OUTPUT/'schedule.json').read_text())
    expected={row['slot_id']:row for row in verified['pairs']}
    rows=[];sources={};families=defaultdict(list)
    for slot in schedule['onsets']:
        directory=prior.FIRST_PAIR.parent if slot['status']=='PRIOR_COMPLETED_EXCLUDED_PAIR' else prior.OUTPUT/slot['slot_id']
        arms={}
        for arm in ARMS:
            path=directory/f'{arm.lower()}.events.jsonl'
            raw=path.read_bytes();sources[str(path.relative_to(prior.ROOT))]=hashlib.sha256(raw).hexdigest()
            arms[arm]=trajectory([json.loads(line) for line in raw.decode().splitlines() if line.strip()])
            if 1-arms[arm]['terminal_correct']!=expected[slot['slot_id']]['arms'][arm]['final_finite_property_regression']:
                raise ValueError('prefix endpoint differs from source-identical recount')
        t=arms['TRUTHFUL_PASS']['correct_prefixes'];f=arms['FALSE_FAIL']['correct_prefixes']
        row={'slot_id':slot['slot_id'],'family':slot['family'],'arms':arms,
             'observed_prefix_change_contrast':(f[2]-f[1])-(t[2]-t[1])}
        rows.append(row);families[slot['family']].append(row)
    horizon=[]
    for step in range(3):
        paired=Counter((r['arms'][ARMS[0]]['correct_prefixes'][step],r['arms'][ARMS[1]]['correct_prefixes'][step]) for r in rows)
        horizon.append({'observed_prefix_decisions':step+1,'pairs':len(rows),
            'truthful_correct':sum(r['arms'][ARMS[0]]['correct_prefixes'][step] for r in rows),
            'false_fail_correct':sum(r['arms'][ARMS[1]]['correct_prefixes'][step] for r in rows),
            'equal_family_false_minus_truth_correct':fmean(fmean(r['arms'][ARMS[1]]['correct_prefixes'][step]-r['arms'][ARMS[0]]['correct_prefixes'][step] for r in members) for members in families.values()),
            'both_correct':paired[(1,1)],'truthful_only_correct':paired[(1,0)],
            'false_only_correct':paired[(0,1)],'neither_correct':paired[(0,0)]})
    transitions={}
    for arm in ARMS:
        members=[r['arms'][arm] for r in rows];actions=Counter()
        for member in members:actions.update(member['actions'])
        transitions[arm]={'branches':len(members),'decisions':sum(r['decisions'] for r in members),
            'actions':dict(actions),'entry_events':sum(r['entry_events'] for r in members),
            'branches_ever_error':sum(r['ever_error'] for r in members),
            'recovery_events':sum(r['recovery_events'] for r in members),
            'ever_error_then_terminal_correct':sum(r['ever_error'] and r['terminal_correct'] for r in members)}
    return {'schema_version':'historical-c5-prefix-audit-v1','eligible_for_main_analysis':False,
        'data_kind':'EXCLUDED_POST_HOC_DESCRIPTIVE_RECOUNT','simulated':False,
        'cohort':verified['cohort'],'historical_protocol':verified['protocol'],
        'selected_pairs':len(rows),'families':len(families),'decisions':sum(t['decisions'] for t in transitions.values()),
        'observed_prefixes':horizon,'transitions':transitions,
        'prefix2_to3_contrast':{'pair_weighted':fmean(r['observed_prefix_change_contrast'] for r in rows),
             'equal_family':fmean(fmean(r['observed_prefix_change_contrast'] for r in members) for members in families.values()),
             'definition':'(correct_FALSE_at3-correct_FALSE_at2)-(correct_TRUE_at3-correct_TRUE_at2)'},
        'pairs':rows,'events_sha256':sources,
        'verified_prior_recount_sha256':hashlib.sha256(prior.OUT.read_bytes()).hexdigest(),
        'analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limitations':['All historical branches received the same three-decision budget notice; prefix2 is not an announced budget2 arm.',
            'Historical false FAIL persisted on later secure submissions; proposed factorial study changes only the initial verdict.',
            'An early completed branch retains its observed terminal state at later prefixes; no continuation is imputed.',
            'Recovery counts are post-treatment descriptive transitions, not causal recovery probabilities.',
            'Selected engineering cohort, ten heterogeneous finite families, no new model calls, p-values, intervals or general code-security claim.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory',type=Path,required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.output_directory.exists() and not args.check:parser.error('preserve existing output')
    data=audit()
    outputs={'audit.json':json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n',
             'observed_prefixes.csv':_csv(data['observed_prefixes'])}
    if args.check:
        for name,text in outputs.items():
            if (args.output_directory/name).read_text()!=text:raise ValueError('historical prefix audit differs:'+name)
        print('VERIFIED_HISTORICAL_PREFIX_AUDIT')
    else:
        args.output_directory.mkdir(parents=True,exist_ok=False)
        for name,text in outputs.items():
            with (args.output_directory/name).open('x',encoding='utf-8',newline='') as handle:handle.write(text)
        print(args.output_directory)


if __name__=='__main__':main()
