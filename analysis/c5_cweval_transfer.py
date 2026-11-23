"""Calibrate two external task specifications using a benign fixture and observation controls."""
import argparse
import hashlib
import json
import os
import secrets
import stat
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/c5/external_controls.json"
REVISION = "e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7"
SOURCE = f"https://github.com/Co1lin/CWEval/blob/{REVISION}/benchmark/core/py/"
TASKS = {
    "cwe_732_2": ("88bd18ad19a67a1bc8a5a29960da2bce7703739089efeb9a84d497e756295f3f",
                  "322473e553e8ee7529e2a7eb79d6fe1a040ec5720dac8e959df074d9de486b89"),
    "cwe_760_0": ("8af63867b12604598b137753cb200a8441ed13646db71833af4e34883f4e5088",
                  "df649f361a54c7913ca68ca06e80f341803f2c1bac54316fa7c8694291421101"),
}


def file_outcomes():
    content = b"public test fixture"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "record"
        with path.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
        observed = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
    rows = {}
    for label, (data, mode) in {
        "reference": observed,
        "function_corruption": (b"", observed[1]),
        "property_corruption": (observed[0], observed[1] | stat.S_IRGRP),
        "both_corrupt": (b"", observed[1] | stat.S_IRGRP),
    }.items():
        rows[label] = {"function": data == content,
                       "property": bool(mode & stat.S_IRUSR) and mode & 0o077 == 0}
    return rows


def derive(salt):
    # Work factor from the external benchmark specification, not a deployment setting.
    return hashlib.pbkdf2_hmac("sha256", b"public test fixture", salt, 10000)


def password_outcomes():
    def record(salt):
        return (derive(salt), salt)

    base = [record(secrets.token_bytes(32)) for _ in range(4)]
    if len({s for _, s in base}) != len(base):
        raise ValueError("Reference fixture produced a repeated salt")
    rows = {}
    for label, observed in {
        "reference": base,
        "function_corruption": [(b"", s) for _, s in base],
        "property_corruption": [base[0]] * len(base),
        "both_corrupt": [(b"", base[0][1])] * len(base),
        "predictable_distinct_observation": [record(i.to_bytes(32, "big")) for i in range(4)],
    }.items():
        rows[label] = {"function": all(len(s) == len(d) == 32 and d == derive(s) for d, s in observed),
                       "property": len({s for _, s in observed}) == len(base)}
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = {"schema_version": 1, "upstream_revision": REVISION,
            "selection": "Purposeful: two Python tasks with observable file metadata or returned bytes, "
                         "requiring no application service or attack input.",
            "scope": "Independent adaptations of two task specifications. Only the safe local reference runs. "
                     "The corruptions are applied to observations. The official suite and models are not run.",
            "limitations": "Distinct salts do not establish unpredictability. File mode bits do not cover ACLs or other filesystems.",
            "tasks": {}}
    for task, controls in [("cwe_732_2", file_outcomes()), ("cwe_760_0", password_outcomes())]:
        task_hash, test_hash = TASKS[task]
        expected = {"reference": (True, True), "function_corruption": (False, True),
                    "property_corruption": (True, False), "both_corrupt": (False, False)}
        for name, (functional, property_ok) in expected.items():
            assert controls[name] == {"function": functional, "property": property_ok}
        data["tasks"][task] = {"spec": SOURCE + task + "_task.py", "spec_sha256": task_hash,
                               "official_tests": SOURCE + task + "_test.py", "test_sha256": test_hash,
                               "controls": controls}
    if args.write:
        OUTPUT.write_text(json.dumps(data, indent=2) + "\n")
    elif data != json.loads(OUTPUT.read_bytes()):
        raise ValueError("Saved calibration differs")
    print("Verified two external specifications, eight designed controls and one known blind spot.")


if __name__ == "__main__":
    main()
