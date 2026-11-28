"""Regrade two QuixBugs studies on a presealed, disjoint alternative domain."""
import argparse
import ast
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from analysis import quix_contract_reversal_report as reversal

base=reversal.base
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/quix_expanded_domain_20261128'
DESIGN='docs/QUIX_EXPANDED_DOMAIN_20261128.md'
BOUND=(DESIGN,'analysis/quix_expanded_domain.py','analysis/quix_contract_reversal_report.py','analysis/free_patch_report.py',
       'analysis/free_patch_20261128/sources.json','analysis/free_patch_20261128/upstream_check.json',
       'analysis/free_patch_20261128/plan.json','analysis/quix_contract_reversal_20261128/plan.json')
STUDIES={'free_patch':'free_patch_20261128','reversal':'quix_contract_reversal_20261128'}


def pretty(obj):
    return (json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def persist(path,data):
    if path.exists():
        if path.read_bytes()!=data:
            raise ValueError(f'Immutable output changed: {path}')
    else:
        with path.open('xb') as f:f.write(data)


def expanded(task):
    if task=='knapsack':
        return [[cap,[list(x) for x in v]] for cap in range(1,10) for n in range(1,5)
                for v in product(((1,6),(2,1),(3,6),(5,8)),repeat=n)]
    if task=='is_valid_parenthesization':
        displays={base.TASKS[task][a][0] for a in ('shared','revealing')}
        return [[s] for n in range(6,11) for chars in product('()',repeat=n) if (s:=''.join(chars)) not in displays]
    return [[list(v)] for n in range(1,7) for v in product((-7,-1,2,5),repeat=n)]


def information(case_list):
    disagree=sum(not base.is_equal(v['upstream'],v['alternative']) for v in case_list)
    d=Fraction(disagree,len(case_list))
    ceiling={str(k):str(1-(1-d)**k/2) for k in (0,1,3,5)}
    return {'size':len(case_list),'disagreement':disagree,'d':str(d),'ideal_uniform':ceiling}


def material():
    sources=json.loads((base.DEFAULT/'sources.json').read_bytes())
    small=reversal.calibration(sources)
    large={}
    cards={}
    for task in reversal.RULES:
        domain=expanded(task)
        toks={json.dumps(v) for v in base.cases(task)+[base.TASKS[task][a] for a in ('shared','revealing')]}
        if any(json.dumps(v) in toks for v in domain) or len({json.dumps(v) for v in domain})!=len(domain):
            raise ValueError('New inputs overlap old or are repeated')
        large[task]=[{'input':v,'upstream':base.expected(task,v),'alternative':reversal.alternative(task,v)} for v in domain]
        old=[{'upstream':a['expected'],'alternative':b['expected']} for a,b in zip(small[task]['held']['upstream'],small[task]['held']['alternative'])]
        cards[task]={'old':information(old),'expanded':information(large[task]),'oracle_outputs_sha256':base.output_digest(large[task])}
    plan={'design':DESIGN,'exploratory':True,'source_sha256':{n:digest(ROOT/n) for n in BOUND},'domains':cards}
    return plan,small,large


def execute_selected(task,expr,expanded_cases,small):
    fn=base.compile_expr(expr,base.TASKS[task]['vars'])
    counts=Counter()
    witness={}
    for case in expanded_cases:
        try:output=base.execute(task,fn,case['input'])
        except ArithmeticError:output={'arithmetic_error':True}
        for target in reversal.TARGETS:
            if base.is_equal(case[target],output):
                counts[target]+=1
            elif target not in witness:
                witness[target]={'input':case['input'],'expected':case[target],'actual':output}
    orig_counts,_=reversal.grades(task,expr,small)
    result={}
    for target in reversal.TARGETS:
        original_pass=orig_counts[target]==len(small[task]['held'][target])
        expanded_pass=counts[target]==len(expanded_cases)
        result[target]={'original_pass':original_pass,'expanded_pass':expanded_pass,
                        'expanded_passed':counts[target],'expanded_total':len(expanded_cases)}
        if original_pass and not expanded_pass:
            result[target]['lost_witness']=witness[target]
    return result


def compute():
    plan,small,large=material()
    if (OUT/'plan.json').read_bytes()!=pretty(plan):raise ValueError('Expanded domain freeze differs')
    sources={}; entries=[]; programs={}
    for study,folder in STUDIES.items():
        directory=ROOT/'analysis'/folder
        if study=='free_patch':base.verify(directory)
        else:reversal.verify(directory)
        path=directory/'results.json'
        sources[study]=digest(path)
        for r in json.loads(path.read_bytes())['rows']:
            row={k:r[k] for k in ('model','task','start','block','arm','status')}
            row['study']=study
            row['program_id']=None
            if r['status']=='OK':
                tree=ast.dump(ast.parse(r['expression'].strip(),mode='eval'))
                key=sha256((r['task']+'|'+tree).encode()).hexdigest()
                if key not in programs:
                    programs[key]={'task':r['task'],'expression':r['expression'],
                                   'grades':execute_selected(r['task'],r['expression'],large[r['task']],small)}
                row['program_id']=key
            entries.append(row)
    return {'plan_sha256':digest(OUT/'plan.json'),'studies_sha256':sources,'rows':entries,'programs':programs}


def report(result,plan):
    text=['# Expanded-domain transfer of selected QuixBugs expressions','',
          '| Study | Output condition | Valid decisions | Previously passing target assessments | Also pass expanded domain | Lost on expanded domain |',
          '| --- | --- | ---: | ---: | ---: | ---: |']
    for study,arms in [('free_patch',base.ARMS),('reversal',reversal.ARMS)]:
        for arm in arms:
            rows=[r for r in result['rows'] if (r['study'],r['arm'],r['status'])==(study,arm,'OK')]
            assigned=('upstream',) if study=='free_patch' else reversal.TARGETS if arm=='concealed' else (arm,)
            passed=[result['programs'][r['program_id']]['grades'][t] for r in rows for t in assigned
                    if result['programs'][r['program_id']]['grades'][t]['original_pass']]
            retained=sum(s['expanded_pass'] for s in passed)
            text.append(f'| {study} | {arm} | {len(rows)} | {len(passed)} | {retained} | {len(passed)-retained} |')
    text+=['',f"Distinct task-specific parsed expressions across the two ledgers: {len(result['programs'])}. Different choices can return the same program. Any lost-target witness is saved in results.json. No model calls are made.",'',
           '| Task | Original inputs distinguishing the targets | New inputs distinguishing the targets | Ideal correctness after one / three random original examples |',
           '| --- | ---: | ---: | ---: |']
    for t,card in plan['domains'].items():
        old,new=card['old'],card['expanded']
        rates=[float(Fraction(old['ideal_uniform'][str(k)])) for k in (1,3)]
        text.append(f"| {t} | {old['disagreement']}/{old['size']} | {new['disagreement']}/{new['size']} | {rates[0]:.3f} / {rates[1]:.3f} |")
    text+=['','The ideal-observer calculation assumes two equally likely deterministic contracts, independent uniform inputs with replacement, and availability of a program implementing either contract. It is an analytical ceiling under those assumptions. The experiment deliberately chose examples distinguishing the contracts.','',
           'Reproduce with `python3 -B -m analysis.quix_expanded_domain check`.','']
    return '\n'.join(text)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['freeze','export','check'])
    a=p.parse_args().action
    if a=='freeze':
        plan,_,_=material()
        persist(OUT/'plan.json',pretty(plan))
        print('Frozen',digest(OUT/'plan.json'))
    else:
        result=compute()
        text=report(result,json.loads((OUT/'plan.json').read_bytes()))
        if a=='export':
            persist(OUT/'results.json',pretty(result))
            persist(OUT/'comparison.md',text.encode())
        elif pretty(result)!=(OUT/'results.json').read_bytes() or text!=(OUT/'comparison.md').read_text():
            raise ValueError('Expanded replay differs')
        print(text)
