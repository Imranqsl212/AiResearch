"""Verify pinned upstream evidence and prepare a parent-only packet for each case."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
LOCK = HERE / "sources.json"


def digest(data):
    return sha256(data).hexdigest()


def api(repo, path):
    return subprocess.check_output(["gh", "api", "-X", "GET", f"repos/{repo}/{path}"])


def prepare_sources(cache, fetch=False):
    manifest = json.loads(LOCK.read_text())
    if digest((HERE / "selection.md").read_bytes()) != manifest["selection_sha256"]:
        raise ValueError("Screening rule changed")
    for case in manifest["cases"]:
        root = cache / case["cache_key"]
        root.mkdir(parents=True, exist_ok=True)
        repo, fix, parent = (case[k] for k in ("repo", "fix", "parent"))
        metadata_path = root / "commit.json"
        if fetch and not metadata_path.exists():
            metadata_path.write_bytes(api(repo, "commits/" + fix))
        meta = json.loads(metadata_path.read_bytes())
        if (meta["sha"] != fix or meta["parents"][0]["sha"] != parent or
                sorted(f["filename"] for f in meta["files"]) != case["changed_files"]):
            raise ValueError("Upstream commit or complete changed-file list differs")
        for revision, hashes in case["files_by_revision"].items():
            for name, expected in hashes.items():
                path = root / revision / name
                if fetch and not path.exists():
                    blob = json.loads(api(repo, f"contents/{name}?ref={revision}"))
                    data = base64.b64decode(blob["content"])
                    if digest(data) != expected:
                        raise ValueError(f"Unexpected upstream data for {name}")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                if digest(path.read_bytes()) != expected:
                    raise ValueError(f"Source digest differs for {name}")
        for name in case["unchanged_paths"]:
            if case["files_by_revision"][fix][name] != case["files_by_revision"][parent][name]:
                raise ValueError("Product or specification changed")
        if fetch and not (cache / (case["id"] + ".tar.gz")).exists():
            target = cache / (case["id"] + ".tar.gz")
            # Do not leave an interrupted fetch at the verified cache path.
            with target.with_suffix(".part").open("wb") as stream:
                subprocess.run(["gh", "api", "-X", "GET", f"repos/{repo}/tarball/{parent}"],
                               stdout=stream, check=True)
            target.with_suffix(".part").replace(target)
        archive = cache / (case["id"] + ".tar.gz")
        if digest(archive.read_bytes()) != case["parent_archive_sha256"]:
            raise ValueError("Snapshot bytes differ; verify upstream archive before accepting a replacement")
        with tarfile.open(archive) as tar:
            prefix = tar.getmembers()[0].name.split("/")[0]
            if not prefix.endswith("-" + parent[:7]):
                raise ValueError("Parent snapshot label differs")
            for name, expected in case["files_by_revision"][parent].items():
                if digest(tar.extractfile(prefix + "/" + name).read()) != expected:
                    raise ValueError("Parent-only snapshot does not contain the declared source")
    return manifest


def packets(cache, output, manifest):
    output.mkdir(parents=True, exist_ok=False)
    for case in manifest["cases"]:
        target = output / case["id"]
        target.mkdir()
        shutil.copyfile(cache / (case["id"] + ".tar.gz"), target / "source.tar.gz")
        (target / "TASK.md").write_text(case["agent_prompt"] + "\n")
        if set(p.name for p in target.iterdir()) != {"source.tar.gz", "TASK.md"}:
            raise ValueError("Unexpected files in a blinded packet")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true", help="download missing public files using GitHub CLI")
    parser.add_argument("--packets", type=Path, help="new private directory for parent-only agent packets")
    args = parser.parse_args()
    manifest = prepare_sources(args.cache, args.fetch)
    if args.packets:
        packets(args.cache, args.packets, manifest)
    print(f'{len(manifest["cases"])} parent and fix sources verified. Human decisions pending.')
