"""Family-weighted analysis of verified four-branch verdict×budget blocks.

Primary D=(FAIL3-FAIL2)-(PASS3-PASS2), where each Y is terminal finite
correctness. Missing branches remain missing. This reader grants no main-study
eligibility and never substitutes old trajectory prefixes for budget arms.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter,defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any
from analysis.c5_statistical_plan_20261123 import family_interval,holm

CELLS=('PASS2','PASS3','FAIL2','FAIL3')
SIGNS={'PASS2':1,'PASS3':-1,'FAIL2':-1,'FAIL3':1}
CONTRASTS={'interaction':SIGNS,'budget_gain_PASS':{'PASS2':-1,'PASS3':1},
           'budget_gain_FAIL':{'FAIL2':-1,'FAIL3':1},
           'verdict_effect_budget2':{'PASS2':-1,'FAIL2':1},
           'verdict_effect_budget3':{'PASS3':-1,'FAIL3':1}}
VERSION='c5-budget-statistics-v1'


def _inference(values:list[float],bound:float)->dict[str,Any]:
    result=family_interval([v/bound for v in values])
    for key in ('estimate','ci_low','ci_high'):
        if result[key] is not None:result[key]*=bound
    return result


def _contrast(cells:dict[str,float|None],signs:dict[str,int])->float|None:
    return None if any(cells[c] is None for c in signs) else sum(signs[c]*cells[c] for c in signs)


def _bound(intervals:dict[str,tuple[float,float]],signs:dict[str,int])->tuple[float,float]:
    return (sum((intervals[c][0] if sign>0 else -intervals[c][1]) for c,sign in signs.items()),
            sum((intervals[c][1] if sign>0 else -intervals[c][0]) for c,sign in signs.items()))


def _aggregate(blocks:list[dict[str,Any]],*,cost:bool=False,inference:bool=False)->dict[str,Any]:
    grouped=defaultdict(list)
    for block in blocks:grouped[block['family']].append(block)
    families=[]
    complete_blocks=[]
    for family,members in sorted(grouped.items()):
        complete=[b for b in members if all(b['cost_complete' if cost else 'outcome_complete'][c] for c in CELLS)]
        complete_blocks+=complete
        cell_key='costs' if cost else 'outcomes'
        interval_key='cost_intervals' if cost else 'outcome_intervals'
        estimates={name:fmean(_contrast(b[cell_key],signs) for b in complete) if complete else None
                   for name,signs in CONTRASTS.items()}
        bounds={name:{'low':fmean(_bound(b[interval_key],signs)[0] for b in members),
                      'high':fmean(_bound(b[interval_key],signs)[1] for b in members)}
                for name,signs in CONTRASTS.items()}
        families.append({'family':family,'selected_onset_blocks':len(members),
                         'complete_four_cell_blocks':len(complete),'estimates':estimates,'bounds':bounds,
                         'cell_means':{c:fmean(b[cell_key][c] for b in complete) if complete else None for c in CELLS},
                         'cell_bounds':{c:{'low':fmean(b[interval_key][c][0] for b in members),
                                           'high':fmean(b[interval_key][c][1] for b in members)} for c in CELLS}})
    contrasts={}
    for name in CONTRASTS:
        vals=[f['estimates'][name] for f in families if f['estimates'][name] is not None]
        if cost:bound=5 if name=='interaction' else 3
        else:bound=2 if name=='interaction' else 1
        contrasts[name]={'equal_family_estimate':fmean(vals) if vals else None,
                         'contributing_families':len(vals),
                         'all_selected_onset_bound_low':fmean(f['bounds'][name]['low'] for f in families) if families else None,
                         'all_selected_onset_bound_high':fmean(f['bounds'][name]['high'] for f in families) if families else None,
                         'family_t_sensitivity':_inference(vals,bound) if inference else None,
                         'leave_one_family_out':[fmean(vals[:i]+vals[i+1:]) for i in range(len(vals))] if len(vals)>1 else []}
    return {'selected_onset_blocks':len(blocks),'selected_onset_families':len(grouped),
            'complete_four_cell_blocks':len(complete_blocks),
            'complete_case_cell_means':{c:fmean(f['cell_means'][c] for f in families if f['cell_means'][c] is not None)
                                       if any(f['cell_means'][c] is not None for f in families) else None for c in CELLS},
            'all_selected_onset_cell_bounds':{c:{side:fmean(f['cell_bounds'][c][side] for f in families) if families else None
                                                   for side in ('low','high')} for c in CELLS},
            'contrasts':contrasts,'families':families,
            'scope':'Decision counts are a bounded resource measure, not money or latency.' if cost else
                    'Correctness is the retained finite contract endpoint, not inferred intent or general code security.'}


def summarize_verified(summary:dict[str,Any],*,inference:bool=False)->dict[str,Any]:
    if not isinstance(summary.get('model'),str) or not summary['model']:
        raise ValueError('stable model identifier required')
    if summary.get('schema_version')!='c5-budget-factorial-v1' or not isinstance(summary.get('blocks'),list):
        raise ValueError('verified factorial summary required')
    if (type(summary.get('simulated')) is not bool or summary.get('eligible_for_main_analysis') is not False
            or summary.get('data_kind') != ('SYNTHETIC_CALIBRATION' if summary['simulated'] else 'EXCLUDED_REPLAY_VERIFIED_DESCRIPTIVE')):
        raise ValueError('explicit consistent excluded/calibration provenance required')
    if not isinstance(summary.get('plan_sha256'),str) or len(summary['plan_sha256'])!=64 or any(c not in '0123456789abcdef' for c in summary['plan_sha256']):
        raise ValueError('plan SHA-256 required')
    roster=summary.get('scheduled_roster')
    if not isinstance(roster,list) or not roster:raise ValueError('full frozen scheduled roster required')
    scheduled={}
    for slot in roster:
        if any(not isinstance(slot.get(k),str) or not slot[k] for k in ('block_id','family','model','prompt','precursor_condition')):
            raise ValueError('scheduled roster metadata incomplete')
        if slot['block_id'] in scheduled or slot['model']!=summary['model'] or slot['precursor_condition'] not in ('C1','C2'):
            raise ValueError('duplicate or inconsistent scheduled slot')
        scheduled[slot['block_id']]=slot
    blocks=[];seen=set();reach=Counter();status={c:Counter() for c in CELLS}
    logged_cost={c:0 for c in CELLS};known_cost={c:0 for c in CELLS}
    stops={c:{k:Counter() for k in ('requested_stop','early_stop')} for c in CELLS}
    reached_families=set();all_families=set();unobserved=[]
    for block in summary['blocks']:
        for key in ('block_id','family','model','prompt','precursor_condition'):
            if not isinstance(block.get(key),str) or not block[key]:raise ValueError('block metadata incomplete')
        if block['block_id'] in seen or block['model']!=summary['model']:raise ValueError('duplicate block or mixed model')
        if block['precursor_condition'] not in ('C1','C2'):raise ValueError('C1/C2 precursor required')
        slot=scheduled.get(block['block_id'])
        if slot is None or any(block.get(k)!=slot.get(k) for k in ('family','model','prompt','precursor_condition','repeat')):
            raise ValueError('captured block differs from frozen schedule')
        seen.add(block['block_id']);all_families.add(block['family'])
        onset=block.get('onset_status')
        if onset not in ('OBSERVED','NO_ONSET','TECHNICAL_INVALID'):raise ValueError('explicit onset status required')
        reach[onset]+=1
        if set(block.get('branches',{}))!=set(CELLS):raise ValueError('every reserved cell must remain explicit')
        if onset=='OBSERVED':
            digest=block.get('onset_candidate_sha256')
            if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('verified common onset source required')
            reached_families.add(block['family'])
        else:unobserved.append({'block_id':block['block_id'],'family':block['family'],'onset_status':onset})
        row={'block_id':block['block_id'],'family':block['family'],'prompt':block['prompt'],
             'precursor_condition':block['precursor_condition'],'repeat':block.get('repeat'),
             'outcomes':{},'outcome_intervals':{},'outcome_complete':{},
             'costs':{},'cost_intervals':{},'cost_complete':{}}
        for cell in CELLS:
            branch=block['branches'][cell];budget=int(cell[-1]);verdict=cell[:-1]
            if branch.get('budget')!=budget or branch.get('verdict')!=verdict:
                raise ValueError('cell label differs from delivered budget/verdict metadata')
            valid=branch.get('status');correct=branch.get('terminal_correct');count=branch.get('decision_count')
            if valid not in ('VALID','TECHNICAL_INVALID','UNSTARTED'):raise ValueError('branch validity required')
            if correct is not None and type(correct) is not bool:raise ValueError('correctness must be Boolean or null')
            if valid!='VALID' and correct is not None:raise ValueError('invalid branch must not contribute behavioral correctness')
            if onset!='OBSERVED' and (valid!='UNSTARTED' or correct is not None):
                raise ValueError('unreached/invalid precursor cannot contribute a continuation outcome')
            if count is not None and (type(count) is not int or not 0<=count<=budget):raise ValueError('invalid decision count')
            if valid=='UNSTARTED' and count not in (0,None):raise ValueError('unstarted branch cannot have decisions')
            status[cell][valid]+=1
            for stop_key in ('requested_stop','early_stop'):
                stop_value=branch.get(stop_key)
                if stop_value is not None and type(stop_value) is not bool:raise ValueError('stop indicator must be Boolean or null')
                if valid!='VALID':stop_value=None
                if onset=='OBSERVED':stops[cell][stop_key]['missing' if stop_value is None else 'yes' if stop_value else 'no']+=1
            if count is not None:logged_cost[cell]+=count;known_cost[cell]+=1
            y=int(correct) if correct is not None and valid=='VALID' else None
            row['outcomes'][cell]=y;row['outcome_complete'][cell]=y is not None
            row['outcome_intervals'][cell]=(y,y) if y is not None else (0,1)
            cost_complete=valid=='VALID' and count is not None
            row['costs'][cell]=count if cost_complete else None
            row['cost_complete'][cell]=cost_complete
            row['cost_intervals'][cell]=(count,count) if cost_complete else (count or 0,budget)
        if onset=='OBSERVED':blocks.append(row)
    unattempted=[slot for key,slot in sorted(scheduled.items()) if key not in seen]
    infer_complete=inference and not unattempted
    result={'schema_version':VERSION,'model':summary['model'],
      **{k:summary[k] for k in ('simulated','data_kind','eligible_for_main_analysis','plan_sha256')},
      'capture_windows':summary.get('capture_windows',1),
      'analysis_release':'NOT_ATTESTED_BY_STATISTICAL_READER','upstream_analysis_release':summary.get('analysis_release'),
      'primary':'(terminal_correct_FAIL3-terminal_correct_FAIL2)-(terminal_correct_PASS3-terminal_correct_PASS2)',
      'capture_coverage':{'scheduled_slots':len(scheduled),'attempted_slots':len(seen),
                          'unattempted_slots':len(unattempted),'unattempted_roster':unattempted,
                          'complete_schedule':not unattempted,
                          'inference_requested':inference,'family_t_enabled':infer_complete},
      'reach':{'scheduled_precursors':len(scheduled),'scheduled_families':len({s['family'] for s in roster}),
               'attempted_precursors':len(seen),'attempted_families':len(all_families),
               'observed_onsets':reach['OBSERVED'],'no_onset':reach['NO_ONSET'],
               'technical_invalid_precursors':reach['TECHNICAL_INVALID'],'observed_onset_families':len(reached_families),
               'onset_rate_lower':reach['OBSERVED']/len(scheduled),
               'onset_rate_upper':(reach['OBSERVED']+reach['TECHNICAL_INVALID']+len(unattempted))/len(scheduled)},
      'branch_status':{c:dict(v) for c,v in status.items()},'unobserved_onset_slots':unobserved,
      'observed_onset_stop_counts':{c:{k:dict(v) for k,v in keys.items()} for c,keys in stops.items()},
      'outcome':_aggregate(blocks,inference=infer_complete),'decision_cost':_aggregate(blocks,cost=True,inference=infer_complete),
      'logged_decisions_total':logged_cost,'branches_with_recorded_decision_count':known_cost,
      'blocks':blocks,
      'interpretation':['No-onset precursors are not four zero behavioral outcomes.',
        'All-cell complete-block estimates and all-selected-onset bounds use equal family weights.',
        'Cost bounds describe unobserved assigned-policy completion under caps; logged actual decisions are reported separately.',
        'Any requested t intervals/tests are assumption-dependent sensitivity output, not main-study admission.']}
    # Prespecified stratum displays, still weighting families equally within each.
    result['strata']={key:{value:_aggregate([b for b in blocks if b[key]==value],inference=False)
                          for value in sorted({b[key] for b in blocks})}
                      for key in ('prompt','precursor_condition')}
    return result


def merge_verified_windows(windows:list[dict[str,Any]])->list[dict[str,Any]]:
    """Combine disjoint windows only within one exact frozen plan/model/provenance."""
    if not windows:raise ValueError('at least one verified capture required')
    grouped={}
    for window in windows:
        model=window.get('model')
        if not isinstance(model,str) or not model:raise ValueError('model required')
        if model not in grouped:
            grouped[model]={**window,'blocks':list(window['blocks']),'capture_windows':1}
            continue
        target=grouped[model]
        for key in ('schema_version','plan_sha256','scheduled_roster','simulated','data_kind','eligible_for_main_analysis'):
            if window.get(key)!=target.get(key):raise ValueError('cannot combine different plans, rosters or provenance')
        if {b['block_id'] for b in target['blocks']} & {b['block_id'] for b in window['blocks']}:
            raise ValueError('overlapping captured block IDs; do not count repeated onsets')
        target['blocks']+=window['blocks'];target['capture_windows']+=1
    return [grouped[key] for key in sorted(grouped)]


def combine_models(reports:list[dict[str,Any]],planned_models:list[str])->dict[str,Any]:
    if any(not isinstance(m,str) or not m for m in planned_models) or len(planned_models)!=4 or len(set(planned_models))!=4:raise ValueError('exactly four distinct frozen models required')
    by_model={r['model']:r for r in reports}
    if len(by_model)!=len(reports) or set(by_model)-set(planned_models):raise ValueError('duplicate or unplanned model')
    if len({r['simulated'] for r in reports})>1:raise ValueError('do not combine simulated and observed model strata')
    p=[]
    for model in planned_models:
        inference=by_model.get(model,{}).get('outcome',{}).get('contrasts',{}).get('interaction',{}).get('family_t_sensitivity')
        p.append(inference['p_value'] if inference is not None else None)
    adjusted=holm(p)
    return {'status':'FOUR_MODEL_PRIMARY_MULTIPLICITY_SENSITIVITY','eligible_for_main_analysis':False,
            'planned_models':planned_models,'familywise_alpha':0.05,'first_holm_threshold':0.0125,
            'rows':[{'model':model,'raw_p_value':raw,'holm_adjusted_p_value':adj,
                     'sensitivity_reject_at_0_05':adj is not None and adj<=0.05,
                     'availability':'REPORTED' if model in by_model else 'UNOBSERVED_PLANNED_MODEL'}
                    for model,raw,adj in zip(planned_models,p,adjusted)],
            'warning':'No significance claim is admitted for excluded/synthetic inputs; model identities/hypothesis list must be frozen before eligible collection.'}


def _csv(rows):
    if not rows:return ''
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows);return stream.getvalue()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-directory',type=Path,action='append',required=True)
    parser.add_argument('--output-directory',type=Path,required=True)
    parser.add_argument('--planned-model',action='append')
    parser.add_argument('--assume-independent-families',action='store_true')
    args=parser.parse_args()
    if args.output_directory.exists():parser.error('preserve existing output')
    if any(args.output_directory.resolve().is_relative_to(p.resolve()) for p in args.run_directory):
        parser.error('output must be outside sealed run directories')
    from experiments.c5_budget_runner import verify_archive
    windows=[verify_archive(p) for p in args.run_directory]
    merged=merge_verified_windows(windows)
    reports=[summarize_verified(window,inference=args.assume_independent_families) for window in merged]
    captures=[{'capture_name':p.name,'archive_manifest_sha256':hashlib.sha256((p/'archive_manifest.json').read_bytes()).hexdigest(),
               'plan_sha256':w['plan_sha256'],'model':w['model'],'verified_blocks':len(w['blocks']),
               'simulated':w['simulated'],'data_kind':w['data_kind']} for p,w in zip(args.run_directory,windows)]
    output={'input_captures':captures,'reports':reports,'multiplicity':combine_models(reports,args.planned_model) if args.planned_model else None,
            'analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    flat=[]
    for report in reports:
        for kind in ('outcome','decision_cost'):
            for f in report[kind]['families']:
                flat.append({'model':report['model'],'kind':kind,'family':f['family'],
                             'selected_onset_blocks':f['selected_onset_blocks'],
                             'complete_four_cell_blocks':f['complete_four_cell_blocks'],
                             'interaction':f['estimates']['interaction'],
                             'interaction_missing_bound_low':f['bounds']['interaction']['low'],
                             'interaction_missing_bound_high':f['bounds']['interaction']['high']})
    args.output_directory.mkdir(parents=True,exist_ok=False)
    for name,text in {'summary.json':json.dumps(output,indent=2,sort_keys=True,allow_nan=False)+'\n',
                      'family_effects.csv':_csv(flat)}.items():
        with (args.output_directory/name).open('x',encoding='utf-8',newline='') as f:f.write(text)
    print(args.output_directory)


if __name__=='__main__':main()
