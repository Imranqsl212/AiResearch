"""Separate yielded data from progress forwarding in the historical tqdm comparison."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from analysis import production_patch_report as study


def components(name, patch, cases):
    fn=study.evaluator(name,patch)
    totals=Counter()
    failures={}
    axes={}
    for row in cases:
        expected=row['expected']
        try:
            observed=fn(row['input'])
            output=observed['output']
            if name=='tqdm':
                flags={'index_value_pairs':output==expected['output'],'progress_forwarding':observed['wrapped']}
            else:
                a,b,_,_=row['input']
                flags={'direction_preserved':((output[0]<output[1]) if a<b else (output[0]>output[1])),
                       'interval_extent':sorted(output)==sorted(expected['output'])}
        except ArithmeticError:
            observed={'error':'invalid output'}
            flags=dict.fromkeys(('index_value_pairs','progress_forwarding') if name=='tqdm' else ('direction_preserved','interval_extent'),False)
        if name=='matplotlib':
            a,b,x,y=row['input']
            direction='ascending' if a<b else 'descending'
            category='expanding' if min(x,y)<min(a,b) or max(x,y)>max(a,b) else 'contained'
            stratum=axes.setdefault(direction+'_'+category,{'total':0,'exact':0})
            stratum['total']+=1
            stratum['exact']+=all(flags.values())
        for field,passes in flags.items():
            totals[field]+=passes
            if not passes and field not in failures:
                failures[field]={'input':row['input'],'expected':expected,'observed':observed}
    result={'cases':len(cases),'passed':dict(totals),'first_failures':failures}
    if axes:result['interval_strata']=axes
    return result


def fault_comparison(name, candidate, calibration):
    # A display can distinguish the original historical fault and conceal a later one.
    spec=calibration[name]
    parent=study.evaluator(name,spec['starts']['faulty']['expression'])
    patch=study.evaluator(name,candidate)
    overlap=Counter({'neither':0,'historical_only':0,'selected_only':0,'both':0})
    three_way=0
    for row in spec['held']:
        original=parent(row['input'])
        try:selected=patch(row['input'])
        except ArithmeticError:selected={'error':'invalid output'}
        original_bad=original!=row['expected']
        selected_bad=selected!=row['expected']
        three_way+=original_bad and selected_bad and original!=selected
        overlap[{(False,False):'neither',(True,False):'historical_only',
                 (False,True):'selected_only',(True,True):'both'}[original_bad,selected_bad]]+=1
    probes={}
    for arm,args in study.PROBES[name].items():
        expected=study.expected(name,args)['output']
        try:observed=patch(args)['output']
        except ArithmeticError:observed={'error':'invalid output'}
        probes[arm]={'input':args,'expected_output':expected,'historical_output':parent(args)['output'],
                     'selected_output':observed}
    return {'heldout_failed_by':dict(overlap),'three_distinct_heldout_outputs':three_way,'displayed_inputs':probes}


def compute(directory=study.DEFAULT):
    study.verify(directory)
    ledger=(directory/'results.json').read_bytes()
    cal=json.loads((directory/'calibration.json').read_bytes())
    rows=[]
    for r in json.loads(ledger)['rows']:
        row={k:r[k] for k in ('block','arm','model','start','task','status','action','expression')}
        row['components']=None
        if r['status']=='OK':
            row['components']=components(r['task'],r['expression'],cal[r['task']]['held'])
            row['fault_comparison']=fault_comparison(r['task'],r['expression'],cal)
            agrees=all(v==row['components']['cases'] for v in row['components']['passed'].values())
            if agrees!=r['passes']:
                raise ValueError('Component grades did not reconstruct the primary endpoint')
        rows.append(row)
    controls={}
    for name,data in cal.items():
        controls[name]={s:components(name,item['expression'],data['held']) for s,item in data['starts'].items()}
    controls['tqdm']['bypass_wrapper_fixture']=components('tqdm','enumerate(iterable,start)',cal['tqdm']['held'])
    return {'results_sha256':sha256(ledger).hexdigest(),'controls':controls,'rows':rows}


def render(score):
    text=['# What changed in the repaired maintenance functions?','',
          'Each counted implementation must pass the stated component on every held-out case. A single functional pass requires both components. The block ledger in component_scores.json includes the number passing out of 45 inputs (tqdm) or 96 (Matplotlib), plus the first failing input for each component.','',
          '| Project and component | No execution | Shared execution | Revealing execution |','| --- | ---: | ---: | ---: |']
    for task,fields in [('tqdm',('index_value_pairs','progress_forwarding')),('matplotlib',('direction_preserved','interval_extent'))]:
        for field in fields:
            cells=[]
            for arm in study.ARMS:
                valid=[r['components'] for r in score['rows'] if (r['task'],r['arm'],r['status'])==(task,arm,'OK')]
                cells.append(f"{sum(c['passed'][field]==c['cases'] for c in valid)}/{len(valid)}")
            text.append('| '+' | '.join([task+' / '+field,*cells])+' |')
    text+=['','| Matplotlib model and starting state | Display | Ascending, expanding / contained | Descending, expanding / contained |',
           '| --- | --- | ---: | ---: |']
    for r in score['rows']:
        if r['task']!='matplotlib' or r['status']!='OK':continue
        mix=r['components']['interval_strata']
        cells=[]
        for direction in ('ascending','descending'):
            as_text=[]
            for shape in ('expanding','contained'):
                v=mix[direction+'_'+shape]
                as_text.append(f"{v['exact']}/{v['total']}")
            cells.append(' and '.join(as_text))
        text.append('| '+' | '.join([r['model']+' / '+r['start'],r['arm'],*cells])+' |')
    text+=['','Expanding means that at least one requested endpoint lies outside the old interval. Contained requests leave the interval unchanged under the contract. This post-hoc decomposition grades all matched programs.']
    seen=set()
    text+=['','### Do the displayed inputs reveal the selected faults?','',
           'The labels shared and revealing were fixed against the historical parent defect. For every distinct final expression that fails the held-out contract, the table replays both displays. The ledger includes all passing and failing expressions.','',
           '| Project and failing expression | Shared input: historical / selected / expected output | Revealing input: historical / selected / expected output | Held-out failures: historical only / selected only / both / neither | Cases with three distinct outputs |',
           '| --- | --- | --- | --- | ---: |']
    for r in score['rows']:
        if r['status']!='OK' or not r['components']['first_failures']:continue
        key=(r['task'],r['expression'])
        if key in seen:continue
        seen.add(key)
        comparison=r['fault_comparison']
        cells=[]
        for arm in ('shared','revealing'):
            q=comparison['displayed_inputs'][arm]
            cells.append(' / '.join(json.dumps(q[k]) for k in ('historical_output','selected_output','expected_output')))
        overlap=comparison['heldout_failed_by']
        cells.append(' / '.join(str(overlap[k]) for k in ('historical_only','selected_only','both','neither')))
        cells.append(str(comparison['three_distinct_heldout_outputs']))
        text.append('| '+' | '.join([r['task']+' / '+r['expression'],*cells])+' |')
    c=score['controls']['tqdm']
    bypass=c['bypass_wrapper_fixture']
    defect=c['faulty']
    text+=['',f"The original tqdm defect returned all expected pairs on {defect['passed']['index_value_pairs']}/45 inputs and forwarded the wrapper on {defect['passed']['progress_forwarding']}/45. The deliberately bypassing expression, enumerate(iterable, start), returned all pairs on {bypass['passed']['index_value_pairs']}/45 and forwarded the wrapper on {bypass['passed']['progress_forwarding']}/45. This last row is a scripted control, not a model decision.",'',
           'Progress forwarding requires one observed wrapper for the original iterable, actual iteration of that wrapper and preservation of the supplied keyword options in the recording fixture. This does not test progress rendering. Matplotlib separates axis direction from the exact extent of the extended interval.','',
           'Replay with `python3 -B -m analysis.production_patch_components --check`.','']
    return '\n'.join(text)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=study.DEFAULT)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    score=compute(args.directory)
    for file,data in [('component_scores.json',(json.dumps(score,indent=2,sort_keys=True)+'\n').encode()),('components.md',render(score).encode())]:
        p=args.directory/file
        if args.check:
            if p.read_bytes()!=data:raise ValueError('Saved component decomposition differs')
        else:
            from tempfile import NamedTemporaryFile
            with NamedTemporaryFile(dir=p.parent,delete=False) as tmp:
                tmp.write(data)
            Path(tmp.name).replace(p)
    print(render(score))
