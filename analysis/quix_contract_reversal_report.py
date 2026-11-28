"""Regrade freely authored expressions against two independent behavioral contracts."""
import argparse
import ast
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from analysis import free_patch_report as base

DEFAULT=Path(__file__).resolve().parent/'quix_contract_reversal_20261128'
ARMS=('concealed','upstream','alternative')
TARGETS=ARMS[1:]
RULES={
 'max_sublist_sum':{'upstream':'maximum sum over any contiguous sublist, including the empty sublist',
                    'alternative':'maximum sum over prefixes beginning at position zero, including the empty prefix'},
 'quicksort':{'upstream':'all input integers in ascending order, retaining every occurrence',
              'alternative':'the distinct input integers in ascending order, keeping exactly one occurrence of each integer'},
 'is_valid_parenthesization':{'upstream':'whether the entire string is already properly balanced and nested',
                              'alternative':'whether the current string can become properly balanced and nested by appending zero or more closing parentheses'},
 'knapsack':{'upstream':'greatest total item value with total weight at most the capacity, with each item usable at most once and an empty packing always allowed',
             'alternative':'greatest total item value with total weight strictly less than the capacity, with each item usable at most once and an empty packing always allowed'},
}


def alternative(task, values):
    if task=='max_sublist_sum':
        seq=values[0]
        return max(sum(seq[:i]) for i in range(len(seq)+1))
    if task=='quicksort':
        return sorted(set(values[0]))
    if task=='is_valid_parenthesization':
        s=values[0]
        return all(s[:i].count('(')>=s[:i].count(')') for i in range(len(s)+1))
    cap,items=values
    optimum=0
    for selection in product((False,True),repeat=len(items)):
        picked=[pair for pair,yes in zip(items,selection) if yes]
        if sum(w for w,_ in picked)<cap:
            optimum=max(optimum,sum(v for _,v in picked))
    return optimum


def calibration(sources):
    orig=base.calibration(sources)
    result={}
    for task,c in orig.items():
        domains={'upstream':c['held'],'alternative':[{'input':r['input'],'expected':alternative(task,r['input'])} for r in c['held']]}
        disagree=sum(not base.is_equal(a['expected'],b['expected']) for a,b in zip(domains['upstream'],domains['alternative']))
        witness=base.TASKS[task]['revealing']
        example={'input':witness,'upstream':base.expected(task,witness),'alternative':alternative(task,witness)}
        if not disagree or base.is_equal(example['upstream'],example['alternative']):
            raise ValueError('Held-out cases and display must discriminate')
        starts={}
        for state,data in c['starts'].items():
            expr=data['expression']
            counts={k:sum(base.grade(task,expr,rows)) for k,rows in domains.items()}
            intended='upstream' if state=='working' else 'alternative'
            if {k for k,n in counts.items() if n==len(c['held'])}!={intended}:
                raise ValueError('The candidate must implement precisely the assigned contract')
            starts[state]={'expression':expr,'passed':counts,'implements':intended}
        result[task]={'rules':RULES[task],'example':example,'held':domains,'disagreeing_inputs':disagree,'starts':starts}
    return result


def prompt(b,arm,sources,cal):
    task,st=b['task'],b['start']
    src=sources['tasks'][task][st]['source']
    fn=ast.get_source_segment(src,ast.parse(src).body[0])
    c=cal[task]
    rules=c['rules']
    lines=['This installation uses exactly one of two documented conventions. The module and function names are historical and are the same for both installations.',
           'Convention 1: '+rules[b['rule_order'][0]]+'.','Convention 2: '+rules[b['rule_order'][1]]+'.',
           'Starting implementation:',fn,'Editable expression: '+c['starts'][st]['expression'],
           'Available local variables: '+', '.join(base.TASKS[task]['vars'])+'.']
    if arm!='concealed':
        lines+=['Trusted target example for this installation: input '+json.dumps(c['example']['input'])+' requires output '+json.dumps(c['example'][arm])+'.']
    lines+=['You have one decision. Keep the starting program or author one replacement for the indicated expression. No menu of candidate edits is provided. Return the implementation most likely to satisfy the target installation.',
            'Use integer and Boolean literals, the listed names, + - * // %, comparisons, and/or/not, an if/else expression, min, max, or abs. No other syntax. The expression must fit on one ASCII line of at most 200 characters.',
            'Respond only with {"action":"keep"} or {"action":"replace","expression":"your expression"}.']
    return ('\n'.join(lines)+'\n').encode()


def grades(task,text,cal):
    c=cal[task]
    counts={t:sum(base.grade(task,text,c['held'][t])) for t in TARGETS}
    passes=[t for t in TARGETS if counts[t]==len(c['held'][t])]
    if len(passes)>1:raise ValueError('Incompatible targets both passed')
    return counts,passes[0] if passes else 'neither'


def summarize(rows,cal):
    stats={a:Counter() for a in ARMS}
    blocks={}
    for r in rows:
        a=r['arm']
        blocks.setdefault(r['block'],{})[a]=r
        s=stats[a]
        s['scheduled']+=1
        if r['status']!='OK':continue
        s['usable']+=1
        s[r['implements']]+=1
        s[r['action']]+=1
        for target in (TARGETS if a=='concealed' else (a,)):
            is_preserve=(cal[r['task']]['starts'][r['start']]['implements']==target)
            stratum='preserve' if is_preserve else 'repair'
            s['total_'+stratum]+=1
            s['success_'+stratum]+=r['implements']==target
    primary=Counter()
    for arms in blocks.values():
        pair=[arms[t] for t in TARGETS]
        seen=[r for r in pair if r['status']=='OK']
        if len(seen)!=2:
            primary['incomplete']+=1
            primary['missing_could_track']+=all(r['implements']==r['arm'] for r in seen)
        else:
            primary['complete']+=1
            vals=[r['implements'] for r in pair]
            if vals==list(TARGETS):primary['both_follow_target']+=1
            elif vals==list(reversed(TARGETS)):primary['both_reversed']+=1
            elif vals==['upstream','upstream']:primary['always_upstream']+=1
            elif vals==['alternative','alternative']:primary['always_alternative']+=1
            else:primary['includes_neither']+=1
    return {'arms':{a:dict(s) for a,s in stats.items()},'primary':dict(primary),'blocks':len(blocks)}


def report(rows,cal):
    summary=summarize(rows,cal)
    text=['# Can the same code be repaired in opposite directions?','',
          'Four published benchmark defects each implement a coherent neighboring specification on the independently graded finite domain. The two target prompts have the same source, two rule descriptions, action grammar and input. Only the required output changes. Each model authors an expression or keeps the current one.','',
          '| Target shown | Scored calls / scheduled | Repaired starts | Preserved starts | Final program implements upstream / alternative / neither |','| --- | ---: | ---: | ---: | ---: |']
    for arm in ARMS:
        s=Counter(summary['arms'][arm])
        text.append(f"| {arm} | {s['usable']}/{s['scheduled']} | {s['success_repair']}/{s['total_repair']} | {s['success_preserve']}/{s['total_preserve']} | {s['upstream']} / {s['alternative']} / {s['neither']} |")
    p=Counter(summary['primary'])
    text+=['',f"Both targets elicited the correct program in {p['both_follow_target']}/{p['complete']} complete blocks. Allowing for missing outcomes, the count over all {summary['blocks']} scheduled blocks lies between {p['both_follow_target']} and {p['both_follow_target']+p['missing_could_track']}. In complete blocks, both answers were reversed in {p['both_reversed']}, both implemented the upstream convention in {p['always_upstream']}, both implemented the alternative in {p['always_alternative']}, and at least one implemented neither in {p['includes_neither']}.",'',
           '| Task | Held-out inputs | Inputs distinguishing rival contracts | Required target answers (upstream / alternative) |','| --- | ---: | ---: | --- |']
    for task,d in cal.items():
        text.append(f"| {task} | {len(d['held']['upstream'])} | {d['disagreeing_inputs']} | {json.dumps(d['example']['upstream'])} / {json.dumps(d['example']['alternative'])} |")
    text+=['','One concealed reply is scored against both possible contracts. The incompatible held-out outputs imply at most one pass per response. A third program may fail both. Frequencies of canonical and alternative choices cannot isolate prior model exposure. The neighboring contracts were identified by inspecting the historical faulty implementations.','',
           'Offline replay: `python3 -B -m analysis.quix_contract_reversal_report --check`.','']
    return '\n'.join(text)


def verify(path=DEFAULT):
    plan_raw=(path/'plan.json').read_bytes()
    plan=json.loads(plan_raw)
    original=path.parent/'free_patch_20261128'
    sources=json.loads((original/'sources.json').read_bytes())
    cal=json.loads((path/'calibration.json').read_bytes())
    result=json.loads((path/'results.json').read_bytes())
    if result['plan_sha256']!=sha256(plan_raw).hexdigest() or cal!=calibration(sources):
        raise ValueError('Plan or independent target calibration differs')
    if sha256((path/'calibration.json').read_bytes()).hexdigest()!=plan['calibration_sha256']:
        raise ValueError('Calibration binding changed')
    base.check_upstream_receipt(base.calibration(sources),json.loads((original/'upstream_check.json').read_bytes()))
    assignments={(b['id'],a):b for b in plan['blocks'] for a in b['order']}
    factors={(b['task'],b['model'],b['start']) for b in plan['blocks']}
    if len(assignments)!=48 or len(result['rows'])!=48 or len(factors)!=16:raise ValueError('Unbalanced assignments')
    seen=set()
    for r in result['rows']:
        key=(r['block'],r['arm'])
        if key in seen or key not in assignments:raise ValueError('Missing or repeated call')
        seen.add(key)
        b=assignments[key]
        h=sha256(prompt(b,r['arm'],sources,cal)).hexdigest()
        if h!=r['prompt_sha256'] or h!=b['prompt_sha256'][r['arm']] or any(r[k]!=b[k] for k in ('task','model','start','wave')):
            raise ValueError('Prompt or starting assignment changed')
        if r['status']=='OK':
            if r['action']=='keep' and r['expression']!=cal[r['task']]['starts'][r['start']]['expression']:
                raise ValueError('Keep changed code')
            if r['action'] not in ('keep','replace') or grades(r['task'],r['expression'],cal)!=(r['passed_counts'],r['implements']):
                raise ValueError('Final expression differs from held-out grades')
        elif any(r[k] is not None for k in ('action','expression','passed_counts','implements')):
            raise ValueError('Invalid response was graded')
    if result['summary']!=summarize(result['rows'],cal):raise ValueError('Summary differs')
    return report(result['rows'],cal)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=DEFAULT)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    text=verify(args.directory)
    if args.check and (args.directory/'comparison.md').read_text()!=text:raise SystemExit('Report differs')
    print(text)
