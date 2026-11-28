"""Two candidate sources and independently supplied contract outputs for each task."""
def card(description, first, second, example, tests):
    return dict(description=description, code=[first, second], diagnostic=example, held_out=tests)


TASKS = {
    'range': card('Decide if a number is in an interval. Include the left endpoint; the right endpoint may be included or excluded.',
        'return x[0] <= x[2] <= x[1]', 'return x[0] <= x[2] < x[1]', [[2,5,5],True,False],
        [[[1,3,1],True,True], [[1,3,3],True,False], [[1,3,4],False,False],
         [[-2,-2,-2],True,False], [[0,7,4],True,True], [[-8,1,-9],False,False]]),
    'dedup': card('Remove duplicate integers. Emit them in order of first occurrence or of last occurrence.',
        'return list(dict.fromkeys(x))', 'return list(reversed(dict.fromkeys(reversed(x))))', [[4,2,4],[4,2],[2,4]],
        [[[],[],[]], [[8],[8],[8]], [[1,2,1],[1,2],[2,1]], [[3,3],[3],[3]],
         [[3,0,3,2,0],[3,0,2],[3,2,0]], [[1,2,3],[1,2,3],[1,2,3]]]),
    'quotient': card('Compute the integer quotient on division by four. Nonintegral values round toward zero or minus infinity.',
        'return x // 4', 'return (abs(x) // 4) * (-1 if x < 0 else 1)', [-6,-2,-1],
        [[-1,-1,0],[7,1,1],[-4,-1,-1],[-9,-3,-2],[0,0,0],[12,3,3]]),
    'moving_sum': card('Emit sums of trailing windows of width three. Initial windows may be emitted when partial or only once complete.',
        'return [sum(x[max(0,i-2):i+1]) for i in range(len(x))]', 'return [sum(x[i-2:i+1]) for i in range(2,len(x))]',
        [[2,1,4,2],[2,3,7,7],[7,7]], [[[],[],[]], [[3],[3],[]], [[1,2],[1,3],[]], [[1,2,3],[1,3,6],[6]],
         [[0,0,0,1],[0,0,0,1],[0,1]], [[-1,3,2,0],[-1,2,4,5],[4,5]]]),
    'calendar': card('Convert a zero-based Monday-first weekday to the target format. Numbering is either Monday-first or Sunday-first; both are zero-based.',
        'return x','return (x+1) % 7',[6,6,0], [[0,0,1],[1,1,2],[2,2,3],[3,3,4],[4,4,5],[5,5,6]]),
    'distance': card('Count positional disagreements between two integer sequences. Unmatched trailing elements count as disagreements or are ignored.',
        'return sum(a != b for a,b in zip(*x)) + abs(len(x[0])-len(x[1]))',
        'return sum(a != b for a,b in zip(*x))', [[[1,4],[2,4,3]],2,1],
        [[[[],[]],0,0], [[[1],[]],1,0], [[[3],[2]],1,1], [[[1,2,3],[1]],2,0], [[[8],[8]],0,0], [[[0,2],[4,2,3,7]],3,1]]),
    'flatten': card('Flatten a nonempty rectangular array with at least one column. The installation uses row-major or column-major order.',
        'return [v for row in x for v in row]','return [v for col in zip(*x) for v in col]',
        [[[3,5],[1,8]],[3,5,1,8],[3,1,5,8]], [[[[1]],[1],[1]], [[[1,2]],[1,2],[1,2]], [[[1],[2]],[1,2],[1,2]],
            [[[1,2],[3,4]],[1,2,3,4],[1,3,2,4]], [[[0,3,0],[1,2,4]],[0,3,0,1,2,4],[0,1,3,2,0,4]],
            [[[4,4],[4,4]],[4,4,4,4],[4,4,4,4]]]),
    'fields': card('Split a nonempty string at commas. Retain or drop empty fields according to the installation convention.',
        'return x.split(",")','return [v for v in x.split(",") if v]', ['a,,b',['a','','b'],['a','b']],
        [['x',['x'],['x']], [',a',['','a'],['a']], ['p,',['p',''],['p']], [',,',['','',''],[]],
         ['d,e',['d','e'],['d','e']], [' q,,r,',[' q','','r',''],[' q','r']]])
}


def calibrate():
    result = {}
    for name, task in TASKS.items():
        diagnostic = task['diagnostic']
        if diagnostic[1] == diagnostic[2] or any(q[0] == diagnostic[0] for q in task['held_out']):
            raise ValueError(f'Invalid diagnostic in {name}')
        checks = {}
        for i, impl in enumerate(('A', 'B')):
            ns = {}
            exec('def run(x):\n    ' + task['code'][i], ns)
            for row in [diagnostic] + task['held_out']:
                actual = ns['run'](row[0])
                if type(actual) is not type(row[i+1]) or actual != row[i+1]:
                    raise ValueError(f'Authored expectation disagrees on {name}/{impl}: {row[0]}')
            observed = [ns['run'](row[0]) for row in task['held_out']]
            checks[impl] = {target: [out == row[j+1] for row, out in zip(task['held_out'], observed)]
                            for j, target in enumerate(('A','B'))}
        if any(all(checks[a][b]) != (a == b) for a in checks for b in checks):
            raise ValueError(f'Held-outs cannot identify contracts for {name}')
        result[name] = {**task,'checks':checks}
    return result
