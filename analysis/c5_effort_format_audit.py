"""Post-hoc structural audit of returned panel responses with formatting errors."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

from experiments import c5_effort_panel as panel

# Fences and element-level keep markers are evaluated separately on the original reply.
FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n(.*?)\r?\n```[ \t]*\Z", re.DOTALL | re.IGNORECASE)
REFUSAL = re.compile(r"^(?:sorry[, .]+|i(?:’m|'m| am) sorry[, .]+)?(?:i cannot|i can(?:’|'|no)t|i must decline|i have to decline)\b", re.I)


def parts(value):
    """Count value types and element-level keep markers without exposing response text."""
    if isinstance(value, list):
        for element in value:
            if isinstance(element, list):
                yield "nested_list"
            yield from parts(element)
    elif isinstance(value,str):
        yield "keep_marker" if value == "keep" else "other_string"
    elif type(value) is int:
        yield "integer"
    else:
        yield "other_type"


def item_keep_sensitivity(decoded, primary_rows):
    """Evaluate only previously unscored, flat same-length arrays in the strict JSON object."""
    cards, truth = panel.material()
    newly_scored = {}
    for card, row in zip(cards, primary_rows):
        key = card["id"]
        value = decoded.get(key)
        candidate = card["candidate_outputs_in_input_order"]
        if (row["valid"] or type(value) is not list or len(value) != len(candidate)
                or "keep" not in value or not all(
                    v == "keep" or (type(v) is int and abs(v) <= 1_000_000) for v in value)):
            continue
        resolved = [old if v == "keep" else v for old,v in zip(candidate,value)]
        newly_scored[key] = resolved == truth[key]
    return newly_scored


def response_format(raw):
    text = raw.decode("utf-8", errors="replace").strip()
    rows, conforms = panel.score(raw)
    if conforms:
        raise ValueError("Response has no format error")
    fence = FENCE.fullmatch(text)
    recovered = panel.score(fence[1].encode())[0] if fence else []
    recognized = [r for r in recovered if r["valid"]]
    result = {"primary_valid":sum(r["valid"] for r in rows),
              "primary_correct":sum(r["final_correct"] for r in rows if r["valid"]),
              "single_surrounding_fence":bool(fence),"fence_only_added_scorable":len(recognized),
              "fence_only_added_correct":sum(r["final_correct"] for r in recognized),
              "task_formats":{}, "nested_item_counts":{}, "literal_keep_new_task_correctness":{},
              "literal_keep_added_scorable":0, "literal_keep_added_correct":0, "literal_keep_added_wrong":0}
    if not text:
        result["class"]="EMPTY_MESSAGE"
        return result
    if fence:
        result["class"]="SINGLE_SURROUNDING_FENCE"
        return result
    try:
        decoded=json.loads(text)
    except ValueError:
        if REFUSAL.search(text):
            category="REFUSAL_LIKE_PREFIX"
        elif "```" in text:
            category="OTHER_FENCED_OR_MIXED_TEXT"
        else:
            category="NON_JSON_TEXT"
            opening=text.find("{")
            if opening > 0:
                try:
                    value,_=json.JSONDecoder().raw_decode(text[opening:])
                    if isinstance(value,dict):
                        category="TEXT_PREFIX_BEFORE_JSON_OBJECT"
                except ValueError:
                    pass
        result["class"]=category
        return result
    if not isinstance(decoded,dict):
        result["class"]="JSON_NON_OBJECT"
        return result
    try:
        panel.strict(raw)
    except (ValueError,UnicodeError,RecursionError):
        result["class"]="INVALID_STRICT_JSON_OBJECT"
        return result
    result["class"]="TASK_VALUE_FORMAT_ERROR" if set(decoded)==set(panel.TASKS) else "WRONG_TASK_KEYS"
    added=item_keep_sensitivity(decoded,rows)
    result.update(literal_keep_new_task_correctness=added,literal_keep_added_scorable=len(added),
                  literal_keep_added_correct=sum(added.values()),literal_keep_added_wrong=len(added)-sum(added.values()))
    structure=Counter()
    for r in rows:
        key=r["task"]
        if r["valid"]:
            result["task_formats"][key]="VALID_KEEP" if r["action"]=="keep" else "VALID_INTEGER_VECTOR"
            continue
        if key not in decoded:
            category="MISSING"
        elif isinstance(decoded[key],list):
            counts=Counter(parts(decoded[key]))
            structure.update(counts)
            if counts["keep_marker"]:
                category="ELEMENT_LEVEL_KEEP"
            elif counts.keys() - {"integer"}:
                category="INVALID_VECTOR_TYPES"
            else:
                category="INVALID_VECTOR_LENGTH_OR_RANGE"
        else:
            category="INVALID_SCALAR_OR_OBJECT"
        result["task_formats"][key]=category
    result["nested_item_counts"]=dict(sorted(structure.items()))
    return result


def audit(root):
    baseline=panel.report(root)
    flagged=[]
    repeated=Counter()
    for row in baseline["rows"]:
        for item in row["tasks"]:
            if item["valid"] and item["starting_correct"] and item["final_correct"]:
                repeated["kept_correct_tables" if item["action"]=="keep" else "resubmitted_unchanged_correct_tables"]+=1
        if row["status"]!="RETURNED_WITH_FORMAT_ERROR":
            continue
        candidate=panel.location(root,row)/"stdout.bin"
        raw,_=panel.pilot.extract("codex",candidate.read_bytes())
        item=response_format(raw)
        if (item["primary_valid"],item["primary_correct"])!=(row["valid_tasks"],row["correct"]):
            raise ValueError("Primary recount mismatch")
        flagged.append({"model":row["model"],"effort":row["effort"],**item})
    return {"kind":"POST_HOC_FORMAT_AUDIT","frozen_plan_sha256":baseline["plan_sha256"],
            "analysis_source_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
            "phase":"Excluded single-invocation numerical panel",
            "status_counts":dict(sorted(Counter(r["status"] for r in baseline["rows"]).items())),
            "format_errors":flagged,"single_fence_added_valid":sum(r["fence_only_added_scorable"] for r in flagged),
            "single_fence_added_correct":sum(r["fence_only_added_correct"] for r in flagged),
            "literal_keep_added_valid":sum(r["literal_keep_added_scorable"] for r in flagged),
            "literal_keep_added_correct":sum(r["literal_keep_added_correct"] for r in flagged),
            "literal_keep_added_wrong":sum(r["literal_keep_added_wrong"] for r in flagged),
            "correct_preservation_actions":{k:repeated[k] for k in ("kept_correct_tables","resubmitted_unchanged_correct_tables")},
            "limitations":"Post-hoc syntax classification. A refusal-like text prefix is only a heuristic label. "
                "Two independent sensitivity checks. One strips exactly one enclosing code fence. "
                "The second was specified after inspecting two responses that used keep inside arrays. "
                "In an unfenced strict JSON object, for a previously unscored task with a flat same-length array "
                "of bounded integers or literal keep, retain the initial candidate value at each marked index. "
                "No flattening, guessing, or combining the two rules. Primary outcomes unchanged."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root",required=True,type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=audit(panel.pilot.private_path(args.private_root))
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        if args.output.exists():
            if args.output.read_text()!=text:
                raise FileExistsError("Choose a fresh output for a changed capture")
        else:
            with args.output.open("x") as handle:
                handle.write(text)
    else:
        print(text,end="")


if __name__=="__main__":
    main()
