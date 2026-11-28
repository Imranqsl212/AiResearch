"""Plot the actual answers and paired tracking counts on QuixBugs."""
from collections import defaultdict
import json
from pathlib import Path
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors

STUDY=Path(__file__).resolve().parents[2]/"analysis/quix_contract_reversal_20261128"
NAMES={"quicksort":"Sort with duplicates", "max_sublist_sum":"Maximum sum",
       "is_valid_parenthesization":"Parentheses", "knapsack":"Knapsack"}


def example_input(task, values):
    if task=="knapsack":
        capacity,items=values
        return f"Limit {capacity}, items {items[0][0]}/{items[0][1]}, {items[1][0]}/{items[1][1]}"
    return json.dumps(values[0]).replace(" ", "")


def paired_counts(rows):
    blocks=defaultdict(dict)
    for row in rows:
        if row["arm"] in ("upstream","alternative"):
            blocks[row["task"],row["block"]][row["arm"]]=row
    counts=defaultdict(lambda:[0,0])
    for (task,_),pair in blocks.items():
        complete=set(pair)=={"upstream","alternative"} and all(r["status"]=="OK" for r in pair.values())
        if complete:
            counts[task][1]+=1
            counts[task][0]+=all(r["implements"]==arm for arm,r in pair.items())
    return counts


def contract_figure(calibration=None, rows=None):
    if calibration is None:
        calibration=json.loads((STUDY/"calibration.json").read_bytes())
    if rows is None:
        rows=json.loads((STUDY/"results.json").read_bytes())["rows"]
    counts=paired_counts(rows)
    fig=Drawing(460,174)
    ink=colors.HexColor("#19333b")
    muted=colors.HexColor("#3c5961")
    teal=colors.HexColor("#246577")
    def label(x,y,value,size=9.2,bold=False,shade=ink):
        fig.add(String(x,y,str(value),fontName="Helvetica-Bold" if bold else "Helvetica",fontSize=size,fillColor=shade))
    label(4,157,"Same starting code, same input, opposite target answers",12,True)
    for x,h in [(7,"Task and shown input"),(173,"Benchmark answer"),(281,"Alternative answer"),(398,"Both followed")]:
        label(x,138,h,8.5,True,teal)
    for i,(task,name) in enumerate(NAMES.items()):
        top=131-i*31
        fig.add(Rect(3,top-28,452,29,fillColor=colors.HexColor("#f2f6f5" if i%2==0 else "#ffffff"),strokeColor=None))
        item=calibration[task]["example"]
        label(7,top-9,name,9.4,True)
        label(7,top-22,example_input(task,item["input"]),8.4,False,muted)
        for x,target in ((174,"upstream"),(282,"alternative")):
            label(x,top-17,json.dumps(item[target]).replace(" ",""),10.3)
        n,d=counts[task]
        label(402,top-17,f"{n}/{d}" if d else "—",10.3,True,teal)
    fig.add(Line(4,7,454,7,strokeWidth=.6,strokeColor=colors.HexColor("#c9d8d8")))
    return fig
