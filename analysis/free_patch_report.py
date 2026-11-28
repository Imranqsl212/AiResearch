"""Bounded scoring of independently authored expressions on four QuixBugs tasks."""
import argparse
import ast
from collections import Counter
from hashlib import sha256
from itertools import product
import json
import operator
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent / 'free_patch_20261128'
ARMS = ('none', 'shared', 'revealing')
TASKS = {
    'max_sublist_sum': {
        'spec': 'Return the maximum sum of a contiguous sublist of integers, allowing the empty sublist (sum zero).',
        'slot': 'max_ending_here = {}', 'vars': ('max_ending_here', 'x'),
        'shared': [[7, -2, 1]], 'revealing': [[-7, 4, 3]],
    },
    'is_valid_parenthesization': {
        'spec': 'Return a Boolean indicating whether the string of opening and closing parentheses is balanced and properly nested.',
        'slot': '    return {}', 'vars': ('depth',),
        'shared': ['(()())()'], 'revealing': ['(()(()'],
    },
    'knapsack': {
        'spec': 'Return the greatest total value achievable using each item at most once within the stated capacity. Weights and values are positive integers.',
        'slot': 'if {}:', 'vars': ('weight', 'j'),
        'shared': [8, [[2, 5], [3, 7]]], 'revealing': [7, [[3, 8], [4, 11]]],
    },
    'quicksort': {
        'spec': 'Return all input integers in ascending order, preserving multiplicities.',
        'slot': 'greater = quicksort([x for x in arr[1:] if {}])', 'vars': ('x', 'pivot'),
        'shared': [[8, -2, 5]], 'revealing': [[8, -2, 8]],
    },
}


class Rejected(ValueError):
    pass


ARITH = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


def compile_expr(source, names):
    """Translate a restricted AST to closures. User-provided expressions are never executed by Python."""
    if type(source) is not str or not source.isascii() or len(source) > 200 or '\n' in source or '#' in source:
        raise Rejected('Expression exceeds the grammar')
    try:
        tree = ast.parse(source.strip(), mode='eval')
    except (ValueError, SyntaxError, RecursionError, OverflowError) as exc:
        raise Rejected('Expression does not parse') from exc
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise Rejected('Expression exceeds node limit')

    def bounded(value):
        if abs(value) > 1_000_000:
            raise ArithmeticError('Intermediate exceeds numeric bound')
        return value

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool) and abs(node.value) <= 1_000:
            return lambda env: node.value
        if isinstance(node, ast.Name) and node.id in names:
            return lambda env: env[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in ARITH:
            left, right, op = visit(node.left), visit(node.right), ARITH[type(node.op)]
            return lambda env: bounded(op(left(env), right(env)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.Not, ast.UAdd, ast.USub):
            fn = visit(node.operand)
            op = {ast.Not: operator.not_, ast.UAdd: operator.pos, ast.USub: operator.neg}[type(node.op)]
            return lambda env: op(fn(env))
        if isinstance(node, ast.Compare) and all(type(op) in COMPARE for op in node.ops):
            first, rest = visit(node.left), [(COMPARE[type(op)], visit(n)) for op,n in zip(node.ops, node.comparators)]
            def compare(env):
                old = first(env)
                for op, get in rest:
                    new = get(env)
                    if not op(old, new):
                        return False
                    old = new
                return True
            return compare
        if isinstance(node, ast.BoolOp) and type(node.op) in (ast.And, ast.Or):
            terms = [visit(v) for v in node.values]
            def logical(env):
                for term in terms:
                    value = term(env)
                    if bool(value) == isinstance(node.op, ast.Or):
                        return value
                return value
            return logical
        if isinstance(node, ast.IfExp):
            test, yes, no = visit(node.test), visit(node.body), visit(node.orelse)
            return lambda env: yes(env) if test(env) else no(env)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('min','max','abs')
                and not node.keywords and (len(node.args) == 1 if node.func.id=='abs' else 2 <= len(node.args) <= 4)):
            fn = {'min':min,'max':max,'abs':abs}[node.func.id]
            args = [visit(a) for a in node.args]
            return lambda env: fn(*(a(env) for a in args))
        raise Rejected('Unsupported expression')
    return visit(tree.body)


def execute(task, expr, values):
    """Harnesses implement the fixed context around the upstream expression slot."""
    if task == 'is_valid_parenthesization':
        depth = 0
        for char in values[0]:
            depth += 1 if char == '(' else -1
            if depth < 0:
                return False
        return expr({'depth': depth})
    if task == 'max_sublist_sum':
        ending = best = 0
        for item in values[0]:
            ending = expr({'x':item, 'max_ending_here':ending})
            best = max(best, ending)
        return best
    if task == 'quicksort':
        def sort(seq):
            if not seq:
                return []
            pivot, rest = seq[0], seq[1:]
            return sort([v for v in rest if v < pivot]) + [pivot] + sort([v for v in rest if expr({'x':v,'pivot':pivot})])
        return sort(values[0])
    capacity, items = values
    prev = [0]*(capacity+1)
    for weight, value in items:
        curr = list(prev)
        for j in range(1, capacity+1):
            if expr({'weight':weight,'j':j}):
                curr[j] = max(curr[j], value + (prev[j-weight] if j >= weight else 0))
        prev = curr
    return prev[-1]


def expected(task, values):
    if task=='is_valid_parenthesization':
        s = values[0]
        while '()' in s:
            s=s.replace('()','')
        return not s
    if task=='quicksort':
        return sorted(values[0])
    if task=='max_sublist_sum':
        a=values[0]
        return max([0]+[sum(a[i:j]) for i in range(len(a)) for j in range(i+1,len(a)+1)])
    cap, items=values
    return max(sum(v*pick for (_,v),pick in zip(items,mask)) for mask in product((0,1),repeat=len(items))
               if sum(w*pick for (w,_),pick in zip(items,mask))<=cap)


def cases(task):
    if task=='is_valid_parenthesization':
        return [[''.join(chars)] for n in range(6) for chars in product('()',repeat=n)]
    if task=='knapsack':
        return [[cap,[list(pair) for pair in items]] for cap in range(6) for n in range(4)
                for items in product(((1,1),(2,4),(3,3)),repeat=n)]
    return [[list(a)] for n in range(5) for a in product((-2,0,3),repeat=n)]


def slot_expression(task, code):
    function = ast.parse(code).body[0]
    if task=='is_valid_parenthesization':
        node = function.body[-1].value
    elif task=='max_sublist_sum':
        node = next(n for n in function.body if isinstance(n,ast.For)).body[0].value
    elif task=='knapsack':
        node = next(n for n in ast.walk(function) if isinstance(n,ast.If)).test
    else:
        node = next(n for n in function.body if isinstance(n,ast.Assign) and n.targets[0].id=='greater').value.args[0].generators[0].ifs[0]
    return ast.get_source_segment(code,node)


def is_equal(answer, target):
    return type(answer) is type(target) and answer == target


def grade(task, text, held):
    fn = compile_expr(text,TASKS[task]['vars'])
    passed=[]
    for case in held:
        try:
            ok=is_equal(execute(task,fn,case['input']),case['expected'])
        except ArithmeticError:
            ok=False
        passed.append(ok)
    return passed


def calibration(sources):
    output={}
    for task, spec in TASKS.items():
        graded=[{'input':v,'expected':expected(task,v)} for v in cases(task)]
        if any(case['input'] in (spec['shared'],spec['revealing']) for case in graded):
            raise ValueError('A displayed input overlaps the scored domain')
        starts={}
        for state, record in sources['tasks'][task].items():
            code=record['source']
            if sha256(code.encode()).hexdigest()!=record['sha256']:
                raise ValueError('Source digest changed')
            text=slot_expression(task,code)
            fn=compile_expr(text,spec['vars'])
            shown={arm:execute(task,fn,spec[arm]) for arm in ('shared','revealing')}
            if not is_equal(shown['shared'],expected(task,spec['shared'])) or is_equal(shown['revealing'],expected(task,spec['revealing']))!=(state=='working'):
                raise ValueError('Display calibration mismatch')
            outcomes=grade(task,text,graded)
            if all(outcomes)!=(state=='working'):
                raise ValueError('Starting state calibration mismatch')
            starts[state]={'expression':text,'displays':shown,'passed':sum(outcomes)}
        output[task]={'held':graded,'starts':starts}
    return output



def output_digest(outputs):
    return sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def check_upstream_receipt(cal, receipt):
    """Compare the fixed harness with native outputs of the pinned, original benchmark files."""
    for task, data in cal.items():
        args=[case['input'] for case in data['held']]+[TASKS[task]['shared'],TASKS[task]['revealing']]
        for start, row in data['starts'].items():
            run=compile_expr(row['expression'],TASKS[task]['vars'])
            outputs=[execute(task,run,arg) for arg in args]
            if receipt[task][start]!={'inputs':len(args),'outputs_sha256':output_digest(outputs)}:
                raise ValueError('Scoring context differs from upstream benchmark outputs')


def prompt(block, arm, sources, cal):
    name, state=block['task'], block['start']
    spec=TASKS[name]
    original=sources['tasks'][name][state]['source']
    fn=ast.parse(original).body[0]
    code=ast.get_source_segment(original,fn)
    target=cal[name]['starts'][state]['expression']
    line=spec['slot'].format(target)
    if line not in code:
        raise ValueError('Cannot locate selected expression in source')
    message = [spec['spec'], 'Current implementation:', code, 'Editable line: '+line.strip(),
               'Editable expression: '+target, 'Allowed local variables: '+', '.join(spec['vars'])+'.']
    if arm != 'none':
        message.append('Execution of this CURRENT implementation: arguments '+json.dumps(spec[arm])+
                       ' returned '+json.dumps(cal[name]['starts'][state]['displays'][arm])+'.')
    message.extend(['You have one decision. Keep the current implementation or write one replacement Python expression for the indicated slot. No menu of alternative edits is provided.',
                    'Use integer and Boolean literals, the listed names, + - * // %, comparisons, and/or/not, an if/else expression, or min, max, abs. No other syntax. The expression must fit on one ASCII line of at most 200 characters.',
                    'Respond only with {"action":"keep"} or {"action":"replace","expression":"your expression"}.'])
    return ('\n'.join(message)+'\n').encode()


def summarize(rows, cal):
    summary={}
    for arm in ARMS:
        items=[r for r in rows if r['arm']==arm]
        stats=Counter(scheduled=len(items), attempted=sum(r['status'] not in ('UNSTARTED','INTERRUPTED') or r.get('native_response_sha256') is not None for r in items))
        for r in items:
            label='preserve' if r['start']=='working' else 'repair'
            stats['scheduled_'+label]+=1
            if r['status']!='OK':
                continue
            stats['scored_'+label]+=1
            stats['passed_'+label]+=r['passes']
            stats['replacement']+=r['action']=='replace'
            if r['action']=='replace':
                reference=cal[r['task']]['starts']['working']['expression']
                stats['passing_noncanonical']+=r['passes'] and ast.dump(ast.parse(r['expression'].strip(),mode='eval'))!=ast.dump(ast.parse(reference,mode='eval'))
        summary[arm]=dict(stats)
    return summary


def report(rows, cal):
    summary=summarize(rows,cal)
    text=['# Writing a replacement expression on QuixBugs', '',
          'Each of four algorithms contributes an upstream defective and corrected starting program. Two hosted model configurations received each start under three displays. Only a valid returned implementation is scored. A submitted expression has to pass every held-out input for that task.', '',
          '| Current-program output | Scored / scheduled | Defective starts repaired | Working starts preserved | Replacements | Passing replacements differing from upstream patch AST |',
          '| --- | ---: | ---: | ---: | ---: | ---: |']
    for arm in ARMS:
        s=Counter(summary[arm])
        text.append(f"| {arm} | {s['scored_repair']+s['scored_preserve']}/{s['scheduled']} | {s['passed_repair']}/{s['scored_repair']} | {s['passed_preserve']}/{s['scored_preserve']} | {s['replacement']} | {s['passing_noncanonical']} |")
    states=Counter(r['status'] for r in rows)
    text+=['','Status of every scheduled decision: '+', '.join(f'{k} {v}' for k,v in sorted(states.items()))+'.','',
           '| Revealing vs no output, matched starts | Both pass | Revealing only | No output only | Neither | Missing / scheduled pairs |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for group in ('faulty','working'):
        byblock={}
        for r in rows:
            if r['start']==group:
                byblock.setdefault(r['block'],{})[r['arm']]=r
        counts=Counter()
        for arms in byblock.values():
            a,b=arms['revealing'], arms['none']
            if a['status']==b['status']=='OK':
                counts[a['passes'],b['passes']]+=1
            else:
                counts['missing']+=1
        text.append('| '+ ' | '.join([group]+[str(counts[k]) for k in ((True,True),(True,False),(False,True),(False,False))]+[f"{counts['missing']}/{len(byblock)}"])+ ' |')
    text+=['','| Task | Finite held-out inputs | Passed by original defect | Passed by upstream correction |',
           '| --- | ---: | ---: | ---: |']
    for name,data in cal.items():
        text.append(f"| {name} | {len(data['held'])} | {data['starts']['faulty']['passed']} | {data['starts']['working']['passed']} |")
    text+=['','This measures free expression generation in an identified slot of four published benchmark tasks. It does not measure fault localization, repository editing, frequency of production defects, or functional correctness outside the finite domains. Public benchmark familiarity is possible. The 16 model-by-start blocks contain four distinct defects. Each model made at most one decision for each condition.','',
           'Run the offline recount with `python3 -B -m analysis.free_patch_report --check`.','']
    return '\n'.join(text)


def verify(path=DEFAULT):
    plan_raw=(path/'plan.json').read_bytes()
    plan=json.loads(plan_raw)
    sources=json.loads((path/'sources.json').read_bytes())
    cal=json.loads((path/'calibration.json').read_bytes())
    result=json.loads((path/'results.json').read_bytes())
    check_upstream_receipt(cal,json.loads((path/'upstream_check.json').read_bytes()))
    if result['plan_sha256']!=sha256(plan_raw).hexdigest() or cal!=calibration(sources):
        raise ValueError('Plan binding or independently rescored starting calibrations differ')
    for filename,key in [('sources.json','sources_sha256'),('calibration.json','calibration_sha256'),('upstream_check.json','upstream_check_sha256')]:
        if sha256((path/filename).read_bytes()).hexdigest()!=plan[key]:
            raise ValueError('Bound material changed')
    assignments={(b['id'],arm):b for b in plan['blocks'] for arm in b['order']}
    if len(assignments)!=48 or len(result['rows'])!=48:
        raise ValueError('Expected exactly 48 scheduled decisions')
    seen=set()
    for row in result['rows']:
        key=(row['block'],row['arm'])
        if key in seen or key not in assignments:
            raise ValueError('Unexpected or duplicate call')
        seen.add(key)
        b=assignments[key]
        digest=sha256(prompt(b,row['arm'],sources,cal)).hexdigest()
        if any(row[k]!=b[k] for k in ('task','start','model','wave')) or b['prompt_sha256'][row['arm']]!=digest or row['prompt_sha256']!=digest:
            raise ValueError('Prompt or assignment differs')
        if row['status']=='OK':
            if row['action'] not in ('keep','replace'):
                raise ValueError('Unknown native action')
            if row['action']=='keep' and row['expression']!=cal[b['task']]['starts'][b['start']]['expression']:
                raise ValueError('Keep action changed the program')
            checks=grade(b['task'],row['expression'],cal[b['task']]['held'])
            if type(row['passes'])!=bool or row['passes']!=all(checks) or row['passed_count']!=sum(checks):
                raise ValueError('Source does not match released grade')
        elif any(row[k] is not None for k in ('passes','passed_count','expression','action')):
            raise ValueError('Unavailable or malformed choice was scored')
    if result['summary']!=summarize(result['rows'],cal):
        raise ValueError('Counts differ')
    return report(result['rows'],cal)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=DEFAULT)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    out=verify(args.directory)
    if args.check and out!=(args.directory/'comparison.md').read_text():
        raise SystemExit('Saved report differs')
    print(out)
