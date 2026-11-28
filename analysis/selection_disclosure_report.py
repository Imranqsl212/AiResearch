"""Compare matched interpretations of the same non-authoritative output, with and without its selection rule."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from analysis import output_provenance_report as parent

DEFAULT = Path(__file__).resolve().parent / "selection_disclosure_20261128"
LABELS = ("anonymous", "disclosed")


def validate(plan, parent_plan, calibration, rows):
    parent.verify_calibration(calibration)
    originals = {b["id"]: b for b in parent_plan["blocks"] if b["wave"] == 1}
    blocks = {b["id"]: b for b in plan["blocks"]}
    if len(originals) != 8 or set(blocks) != set(originals) or len(plan["blocks"]) != 8:
        raise ValueError("The study requires every block from the original first wave")
    expected = {}
    for bid, b in blocks.items():
        orig = originals[bid]
        if any(b[k] != orig[k] for k in ("task", "model", "start")):
            raise ValueError("Original block changed")
        if len(b["calls"]) != 4 or {(c["label"], c["value_contract"]) for c in b["calls"]} != {
                (label,t) for label in LABELS for t in parent.TARGETS}:
            raise ValueError("Incomplete or duplicated disclosure cell")
        hashes = {c["value_contract"]: c["prompt_sha256"] for c in orig["calls"] if c["label"] == "anonymous"}
        if len({c["prompt_sha256"] for c in b["calls"]}) != 4:
            raise ValueError("Distinct native cells cannot share a prompt")
        for c in b["calls"]:
            key = bid, c["id"]
            if (key in expected or c["targets"] != list(parent.TARGETS)
                    or (c["label"] == "anonymous" and c["prompt_sha256"] != hashes[c["value_contract"]])):
                raise ValueError("Incorrect dual-target scoring or anonymous baseline prompt")
            expected[key] = b,c
    if len(rows) != 32 or {(r["block"],r["call_id"]) for r in rows} != set(expected):
        raise ValueError("Every scheduled native call requires an explicit status")
    for r in rows:
        b,c = expected[r["block"],r["call_id"]]
        if any(r[k] != b[k] for k in ("task", "model", "start")) or any(
                r[k] != c[k] for k in ("label", "value_contract", "targets", "prompt_sha256")):
            raise ValueError("Received assignment differs from plan")
        if r["status"] != "OK":
            if not r["status"] or r["choice"] is not None or r["after"] is not None or r["assessments"] != []:
                raise ValueError("Missing response is graded")
            continue
        if r["choice"] not in ("keep", "switch"):
            raise ValueError("Unknown action")
        start = r["start"]
        chosen = start if r["choice"] == "keep" else {"A":"B","B":"A"}[start]
        checks = calibration[r["task"]]["checks"]
        assessments = [{"target":t, "before_correct":all(checks[start][t]), "after_correct":all(checks[chosen][t])}
                       for t in parent.TARGETS]
        if (r["after"] != chosen or r["assessments"] != assessments or any(type(v[field]) is not bool
                for v in r["assessments"] for field in ("before_correct", "after_correct"))):
            raise ValueError("Choice or target assessment changed")


def summarize(rows):
    cells = {label:Counter() for label in LABELS}
    block_info, choices = {}, {}
    missing = Counter()
    for r in rows:
        bid, label = r["block"], r["label"]
        block_info[bid] = r["model"],r["task"],r["start"]
        choices[bid, label, r["value_contract"]] = r["after"]
        g = cells[label]
        ok = r["status"] == "OK"
        g["scheduled_calls"] += 1
        g["valid_calls"] += ok
        g["retained"] += ok and r["choice"] == "keep"
        for t in parent.TARGETS:
            key = "preserve" if t == r["start"] else "repair"
            g[key + "_scored"] += ok
            g[key + "_passed"] += ok and r["after"] == t
        if not ok:
            missing[r["status"]] += 1
    matched = Counter()
    detail = []
    for bid, (model,task,start) in sorted(block_info.items()):
        values = {}
        patterns, signed_bounds = [], []
        for label in LABELS:
            a,b = [choices[bid,label,t] for t in parent.TARGETS]
            values[label] = [a,b]
            p,lower,upper = parent.pair_pattern(a,b,start)
            sign_min = int(a == "A") - int(b in ("A",None))
            sign_max = int(a in ("A",None)) - int(b == "A")
            signed_bounds.append((sign_min,sign_max))
            patterns.append((p,lower,upper))
            g = cells[label]
            g[p] += 1
            g["complete"] += p != "incomplete"
            g["min"] += lower
            g["max"] += upper
            g["signed_min"] += sign_min
            g["signed_max"] += sign_max
            if p != "incomplete":
                g["signed"] += sign_min
        f,s = patterns
        matched["scheduled"] += 1
        matched["min_gain"] += s[1] - f[2]
        matched["max_gain"] += s[2] - f[1]
        matched["signed_diff_min"] += signed_bounds[1][0] - signed_bounds[0][1]
        matched["signed_diff_max"] += signed_bounds[1][1] - signed_bounds[0][0]
        if "incomplete" not in (f[0],s[0]):
            matched["complete"] += 1
            matched["only_disclosed"] += s[1] > f[1]
            matched["only_anonymous"] += f[1] > s[1]
            matched["both"] += s[1] == f[1] == 1
            matched["neither"] += s[1] == f[1] == 0
            matched["signed_diff"] += signed_bounds[1][0] - signed_bounds[0][0]
        detail.append({"model":model,"task":task,"start":start,**values})
    return {"cells":cells, "paired":matched, "rows":detail, "missing":dict(missing)}


def report(s):
    lines = ["# Does explaining output selection change which program an agent chooses?", "",
             "Both arms show the identical input and value as an observation from one unnamed candidate. The "
             "disclosure arm also describes how the value was selected. Neither displayed value identifies the installation's "
             "required convention. Tracking both means choosing the producing implementation on both native calls.", "",
             "| Caption | Valid / assigned calls | Both values followed / complete blocks | Both opposed | Always kept | Always switched | Bounds on both-follow count |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for label,g in s["cells"].items():
        lines.append(f"| {label} | {g['valid_calls']} / {g['scheduled_calls']} | {g['both_aligned']} / {g['complete']} | "
                     f"{g['both_opposite']} | {g['always_keep']} | {g['always_switch']} | [{g['min']}, {g['max']}] |")
    v = s["paired"]
    lines += ["", f"Across {v['complete']}/{v['scheduled']} complete matched blocks, both captions tracked both values in "
              f"{v['both']}. Only anonymous tracked both in {v['only_anonymous']}, only disclosed in {v['only_disclosed']}, "
              f"and neither in {v['neither']}. The possible change in the number tracking both under disclosed minus "
              f"anonymous is [{v['min_gain']:+}, {v['max_gain']:+}] over all eight assignments.", "",
              "Signed tracking gives +1 to both-follow, −1 to both-opposed, and 0 to a constant selection. The "
              f"change in this signed total was {v['signed_diff']:+} across {v['complete']} complete comparisons, "
              f"with bounds [{v['signed_diff_min']:+}, {v['signed_diff_max']:+}] across the eight assigned blocks.", "",
              "| Caption | Repair / scored | Preservation / scored | Signed total / complete blocks |",
              "| --- | ---: | ---: | ---: |"]
    for label,g in s["cells"].items():
        lines.append(f"| {label} | {g['repair_passed']} / {g['repair_scored']} | "
                     f"{g['preserve_passed']} / {g['preserve_scored']} | {g['signed']:+} / {g['complete']} |")
    lines += ["", "Each native choice is assessed once per possible hidden target. Exactly one of the two assessments "
              "must pass for each valid response. These paired target grades are not two independent decisions. Each task "
              "appears once in the eight blocks, so model and task are not fully crossed. Each native call supplies "
              "one sampled response.", "",
              "Missing calls: " + (", ".join(f"{k}={v}" for k,v in sorted(s["missing"].items())) or "none") + ".", "",
              "| Model | Task | Initial implementation | Anonymous selections for A / B | Disclosed selections for A / B |",
              "| --- | --- | --- | --- | --- |"]
    for r in s["rows"]:
        pairs=[" / ".join(v or "—" for v in r[k]) for k in LABELS]
        lines.append("| " + " | ".join([r["model"],r["task"],r["start"],*pairs]) + " |")
    lines += ["", "Offline recount: `python3 -B -m analysis.selection_disclosure_report --check`.", ""]
    return "\n".join(lines)


def verify(directory=DEFAULT):
    directory=Path(directory)
    original=directory.parent/"output_provenance_20261128"
    raw=(directory/"plan.json").read_bytes()
    cal=(directory/"calibration.json").read_bytes()
    parent_plan=(original/"plan.json").read_bytes()
    plan=json.loads(raw)
    results=json.loads((directory/"results.json").read_bytes())
    if (results["plan_sha256"]!=sha256(raw).hexdigest() or plan["calibration_sha256"]!=sha256(cal).hexdigest()
            or results["eligible_for_main_analysis"] is not False or plan["eligible_for_main_analysis"] is not False
            or plan["parent_wave"] != 1 or plan["parent_plan_sha256"]!=sha256(parent_plan).hexdigest()):
        raise ValueError("Frozen assignment, parent or calibration changed")
    validate(plan,json.loads(parent_plan),json.loads(cal),results["rows"])
    return summarize(results["rows"])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,default=DEFAULT)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    text=report(verify(args.directory))
    if args.check and (args.directory/"comparison.md").read_text()!=text:
        raise SystemExit("Stored selection-disclosure report differs")
    print(text,end="")
