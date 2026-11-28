"""Offline reconstruction of two free-edit maintenance comparisons."""
import argparse
import ast
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from analysis import free_patch_report as base

DEFAULT=Path(__file__).resolve().parent/'production_patch_20261128'
ARMS=base.ARMS
NAMES=('matplotlib','tqdm')
SPECS={
    'matplotlib': 'Extend an existing axis view interval to include both supplied endpoints. Keep its direction and every point in the old interval. The first argument of the recursive setter is self. Write the pair of endpoint arguments for its descending-interval branch.',
    'tqdm':'For an ordinary Python iterable, return the same index/value sequence as builtin enumerate(iterable, start), starting at the requested integer. Yield the values through the supplied progress wrapper with its forwarded options. Write the expression returned from the final ordinary-iterable branch.',
}
PROBES={'matplotlib':{'shared':[8,2,0,10],'revealing':[8,2,3,7]},
        'tqdm':{'shared':[['fig','kiwi'],0],'revealing':[['fig','kiwi'],7]}}
ORIGINAL_TEST={'matplotlib':[1,0,0.3,0.7], 'tqdm':[list(range(9)),42]}
MATVARS=('oldmin','oldmax','vmin','vmax')


def slot(name, source):
    tree=ast.parse(source).body[0]
    if name=='tqdm':
        return ast.get_source_segment(source,tree.body[-1].value)
    setter=next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name=='setter')
    calls=[n.value for n in ast.walk(setter) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
           and isinstance(n.value.func,ast.Name) and n.value.func.id=='setter']
    call=next(c for c in calls if c.args[1].func.id=='max')
    return '('+', '.join(ast.get_source_segment(source,x) for x in call.args[1:])+')'


def parse(text):
    if type(text)!=str or not text.isascii() or len(text)>250 or '\n' in text or '#' in text:
        raise base.Rejected('Invalid expression length')
    try:
        tree=ast.parse(text.strip(),mode='eval')
    except (SyntaxError,ValueError,RecursionError) as err:
        raise base.Rejected('Invalid expression') from err
    if sum(1 for _ in ast.walk(tree))>64:
        raise base.Rejected('Too many AST nodes')
    return tree.body


class Wrapper:
    def __init__(self, seq, options):
        self.seq, self.options = seq, options
        self.visited=False

    def __iter__(self):
        self.visited=True
        return iter(self.seq)


def evaluator(name,text):
    root=parse(text)
    if name=='matplotlib':
        if not isinstance(root,(ast.Tuple,ast.List)) or len(root.elts)!=2:
            raise base.Rejected('Supply exactly two endpoint expressions')
        ends=[base.compile_expr(ast.unparse(x),MATVARS) for x in root.elts]
        def endpoints(values):
            oldmin,oldmax,vmin,vmax=values
            if oldmin < oldmax:
                out=[min(vmin,vmax,oldmin),max(vmin,vmax,oldmax)]
            else:
                env=dict(zip(MATVARS,values))
                out=[e(env) for e in ends]
            if any(type(v) not in (int,float) for v in out):
                raise ArithmeticError('Endpoints must be numeric')
            return {'output':out,'wrapped':None}
        return endpoints

    def term(node):
        if isinstance(node,ast.Name) and node.id in ('iterable','start'):
            return lambda e:e[node.id]
        if isinstance(node,ast.Constant) and type(node.value)==int and abs(node.value)<=1000:
            return lambda e:node.value
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('enumerate','tqdm_class') and 1<=len(node.args)<=2:
            args=[term(a) for a in node.args]
            kws={}
            forwarded=False
            for kw in node.keywords:
                if kw.arg is None and isinstance(kw.value,ast.Name) and kw.value.id=='tqdm_kwargs' and not forwarded:
                    forwarded=True
                elif kw.arg=='start' and 'start' not in kws:
                    kws['start']=term(kw.value)
                else:raise base.Rejected('Unrecognized keyword argument')
            def call(e):
                options=dict(e['tqdm_kwargs']) if forwarded else {}
                options.update({k:f(e) for k,f in kws.items()})
                vals=[f(e) for f in args]
                if node.func.id=='enumerate':
                    return enumerate(*vals,**options)
                instance=Wrapper(vals[0],options)
                e['wrappers'].append(instance)
                return instance
            return call
        raise base.Rejected('Expression is outside the iterator grammar')
    fn=term(root)

    def pairs(values):
        seq,start=values
        env={'iterable':seq,'start':start,'tqdm_kwargs':{'disable':True},'wrappers':[]}
        try:
            value=list(fn(env))
            output=[list(pair) if type(pair) in (list,tuple) else pair for pair in value]
            wrappers=env['wrappers']
            wrapped=(len(wrappers)==1 and wrappers[0].visited and wrappers[0].seq is seq
                     and wrappers[0].options==env['tqdm_kwargs'])
            return {'output':output,'wrapped':wrapped}
        except (TypeError,ValueError) as exc:
            raise ArithmeticError('Not a valid iterator result') from exc
    return pairs


def cases(name):
    if name=='matplotlib':
        return [[o,p,x,y] for o,p,x,y in product((-2,0,2),(-2,0,2),(-3,-1,1,3),(-3,-1,1,3)) if o!=p]
    return [[list(a),start] for length in range(4) for a in product(('a','b'),repeat=length) for start in (-2,0,3)]


def expected(name,args):
    if name=='tqdm':
        return {'output':[[args[1]+i,v] for i,v in enumerate(args[0])],'wrapped':True}
    ordered=sorted(args)
    endpoints=[ordered[0],ordered[-1]]
    return {'output':endpoints if args[0]<args[1] else endpoints[::-1],'wrapped':None}


def grade(name,expr,held):
    fn=evaluator(name,expr)
    passed=[]
    for row in held:
        try:passed.append(fn(row['input'])==row['expected'])
        except ArithmeticError:passed.append(False)
    return passed


def calibration(sources):
    cal={}
    for name, source in sources.items():
        held=[{'input':a,'expected':expected(name,a)} for a in cases(name)]
        starts={}
        for state,version in source['versions'].items():
            expr=slot(name,version['function_source'])
            fn=evaluator(name,expr)
            shows={arm:fn(args)['output'] for arm,args in PROBES[name].items()}
            correct=state=='working'
            if shows['shared']!=expected(name,PROBES[name]['shared'])['output'] or (shows['revealing']==expected(name,PROBES[name]['revealing'])['output'])!=correct:
                raise ValueError('Display validity changed')
            checks=grade(name,expr,held)
            if all(checks)!=correct or any(r['input'] in list(PROBES[name].values())+[ORIGINAL_TEST[name]] for r in held):
                raise ValueError('Starting state or disjoint domain changed')
            test=fn(ORIGINAL_TEST[name])
            if (test==expected(name,ORIGINAL_TEST[name]))!=correct:
                raise ValueError('Upstream regression example failed to discriminate')
            starts[state]={'expression':expr,'passed':sum(checks),'displays':shows,'upstream_example':test}
        cal[name]={'starts':starts,'held':held}
    return cal


def all_inputs(name):
    return cases(name)+list(PROBES[name].values())+[ORIGINAL_TEST[name]]


def check_native(cal,receipt):
    for name,c in cal.items():
        for start,r in c['starts'].items():
            fn=evaluator(name,r['expression'])
            values=all_inputs(name)
            if receipt[name][start]!={'inputs':len(values),'outputs_sha256':base.output_digest([fn(v) for v in values])}:
                raise ValueError('The harness differs from native execution of the pinned upstream function')


def prompt(block, arm, sources, cal):
    name,st=block['task'],block['start']
    s=sources[name]['versions'][st]['function_source']
    expression=cal[name]['starts'][st]['expression']
    parts=[SPECS[name], 'Current upstream function:',s,'Editable expression: '+expression]
    if name=='matplotlib':
        parts.append('Available names: oldmin, oldmax, vmin, vmax. Return a pair (expr1, expr2). For each scalar use integer/Boolean literals, names, + - * // %, comparisons, and/or/not, if/else, min, max or abs.')
    else:
        parts.append('Available names: iterable, start, tqdm_kwargs. Return an iterator expression using the supplied tqdm_class and/or enumerate, with positional arguments, integer literals, start= or **tqdm_kwargs. Do not use the NumPy branch.')
    if arm!='none':
        ins=PROBES[name][arm]
        args=dict(zip(MATVARS,ins)) if name=='matplotlib' else dict(zip(('iterable','start'),ins))
        output=cal[name]['starts'][st]['displays'][arm]
        parts.append('Execution of this CURRENT implementation: input '+json.dumps(args)+' returned '+json.dumps(output)+'.')
    parts+=['You have one decision. Keep the current implementation or write its replacement expression, one ASCII line of at most 250 characters. No alternative implementation is provided.',
            'Reply only with {"action":"keep"} or {"action":"replace","expression":"your expression"}.']
    return ('\n'.join(parts)+'\n').encode()


def report(rows,cal):
    text=['# Writing patches on two historical maintenance fixes','',
          'Each block holds the same model and upstream start, then offers a single free expression edit under each display. The fixed domains score the Matplotlib axis-extension branch and ordinary-iterable tqdm enumeration. Every candidate must satisfy its complete task domain, including progress-wrapper forwarding in tqdm.','',
          '| Current-program display | Scored decisions / scheduled | Defects repaired | Working starts preserved | Submitted replacements |','| --- | ---: | ---: | ---: | ---: |']
    for arm in ARMS:
        rr=[r for r in rows if r['arm']==arm]
        valid=[r for r in rr if r['status']=='OK']
        cells=[]
        for st in ('faulty','working'):
            part=[r for r in valid if r['start']==st]
            cells.append(f"{sum(r['passes'] for r in part)}/{len(part)}")
        text.append('| '+' | '.join([arm,f'{len(valid)}/{len(rr)}',*cells,str(sum(r['action']=='replace' for r in valid))])+' |')
    text+=['','| Project | Model | Upstream start | None | Shared | Revealing |','| --- | --- | --- | --- | --- | --- |']
    for ident in sorted({r['block'] for r in rows}):
        arms={r['arm']:r for r in rows if r['block']==ident}
        ex=arms['none']
        def cell(r):
            if r['status']!='OK':return r['status']
            return r['action']+(' / pass' if r['passes'] else ' / fail')
        text.append('| '+' | '.join([ex['task'],ex['model'],ex['start'],*(cell(arms[a]) for a in ARMS)])+' |')
    states=Counter(r['status'] for r in rows)
    text+=['','Scheduled decisions by status: '+', '.join(f'{s} {v}' for s,v in sorted(states.items()))+'.','',
           'The two original parent commits contain the faulty implementations. The maintainer commits supply the corresponding working controls. Both fixes add a targeted test. The saved upstream-example and exhaustive judgments validate the affected function using an axis-object fixture or progress-wrapper fixture. The full projects and their dependency stacks were not executed. Each condition provides one sampled decision per model and start.','',
           'Run `python3 -B -m analysis.production_patch_report --check` to recalculate the table and every accepted patch grade.','']
    return '\n'.join(text)


def verify(path=DEFAULT):
    plan_raw=(path/'plan.json').read_bytes()
    plan=json.loads(plan_raw)
    sources=json.loads((path/'sources.json').read_bytes())
    cal=json.loads((path/'calibration.json').read_bytes())
    result=json.loads((path/'results.json').read_bytes())
    if result['plan_sha256']!=sha256(plan_raw).hexdigest() or cal!=calibration(sources):
        raise ValueError('Plan binding or independently rescored starting calibrations differ')
    for filename,key in [('sources.json','sources_sha256'),('calibration.json','calibration_sha256'),('upstream_check.json','upstream_check_sha256')]:
        if sha256((path/filename).read_bytes()).hexdigest()!=plan[key]:
            raise ValueError('Bound material changed')
    check_native(cal,json.loads((path/'upstream_check.json').read_bytes()))
    assignments={(b['id'],arm):b for b in plan['blocks'] for arm in b['order']}
    if len(assignments)!=24 or len(result['rows'])!=24:
        raise ValueError('Expected 24 scheduled decisions')
    seen=set()
    for r in result['rows']:
        key=(r['block'],r['arm'])
        if key in seen or key not in assignments:raise ValueError('Duplicate or missing assignment')
        seen.add(key)
        b=assignments[key]
        h=sha256(prompt(b,r['arm'],sources,cal)).hexdigest()
        if r['prompt_sha256']!=h or b['prompt_sha256'][r['arm']]!=h or any(r[k]!=b[k] for k in ('wave','task','model','start')):
            raise ValueError('Assignment or prompt digest differs')
        if r['status']=='OK':
            if r['action']=='keep' and r['expression']!=cal[r['task']]['starts'][r['start']]['expression']:
                raise ValueError('Kept source changed')
            if r['action'] not in ('keep','replace'):raise ValueError('Invalid action')
            passed=grade(r['task'],r['expression'],cal[r['task']]['held'])
            if r['passes'] is not all(passed) or r['passed_count']!=sum(passed):
                raise ValueError('Patch grade changed')
        elif any(r[k] is not None for k in ('action','expression','passes','passed_count')):
            raise ValueError('Missing response scored')
    if result['summary']!=base.summarize(result['rows'],cal):
        raise ValueError('Public summary differs')
    return report(result['rows'],cal)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=DEFAULT)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    text=verify(args.directory)
    if args.check and (args.directory/'comparison.md').read_text()!=text:
        raise SystemExit('Saved report differs')
    print(text)
