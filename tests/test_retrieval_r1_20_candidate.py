"""Fail-closed checks for the excluded twenty-family top-one prototype."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest

from benchmark.retrieval_r1_20_candidate import (
    CORPUS_PATH, FAMILY_ORDER, INHERITED, NEW_DOCUMENTS,
    CandidateRetrievalError, agent_visible_documents, expected_rows,
    freeze_candidate_manifest, retrieve,
)
from benchmark.retrieval_r1_20_candidate import _catalog, _read_rows


def test_exact_twenty_family_source_coverage() -> None:
    rows = _read_rows()
    public = _catalog()
    assert len(rows) == len(FAMILY_ORDER) == len(public) == 20
    assert len(INHERITED) == len(NEW_DOCUMENTS) == 10
    assert rows == expected_rows()
    assert {row["family"] for row in rows} == set(FAMILY_ORDER)
    assert len({row["document_id"] for row in rows}) == 20
    assert all(row["domain"] == public[row["family"]]["environment"]["domain"] for row in rows)
    manifest = freeze_candidate_manifest()
    assert manifest["status"] == "EXCLUDED_PROTOTYPE_UNREVIEWED"
    assert manifest["top_k"] == 1
    assert len(manifest["document_hashes"]) == len(manifest["public_projection_hashes"]) == 20
    saved = json.loads(CORPUS_PATH.with_name("retrieval_manifest_r1_20_candidate.json").read_text(encoding="utf-8"))
    assert saved == manifest


def test_current_retrievers_do_not_cover_twenty_public_domains() -> None:
    from benchmark.retrieval_v1 import make_public_query as v1_query
    from benchmark.retrieval_v2 import make_public_query as v2_query

    def accepted(query_fn):
        rows = []
        for family, public in _catalog().items():
            try:
                query_fn(public)
            except ValueError:
                continue
            rows.append(family)
        return set(rows)

    assert accepted(v1_query) == {"authorization", "path-boundary"}
    assert accepted(v2_query) == {"authorization", "path-boundary", "transaction_replay"}


def test_matched_r0_r1_and_exploratory_r2_for_all_twenty() -> None:
    manifest = freeze_candidate_manifest()
    public = _catalog()
    for family in FAMILY_ORDER:
        task = public[family]
        r0 = retrieve(task, mode="R0", manifest=manifest)
        r1 = retrieve(task, mode="R1", manifest=manifest)
        r2 = retrieve(task, mode="R2", manifest=manifest)
        assert r0["retrieved_document_ids"] == []
        assert r1["retrieved_document_ids"] == ["r1-20-" + family.replace("_", "-")]
        assert r1["documents"][0]["score"] > 0
        assert r2["retrieved_document_ids"][0] == r1["retrieved_document_ids"][0]
        assert len(r2["documents"]) == 2
        assert not r2["documents"][0]["noise_injected"]
        assert r2["documents"][1]["noise_injected"]
        assert r2["documents"][1]["document_id"] != r1["documents"][0]["document_id"]
        assert r0["query"] == r1["query"] == r2["query"]
        visible = agent_visible_documents(r1)
        assert visible == [{key: r1["documents"][0][key] for key in ("document_id", "source", "text")}]
        assert "score" not in visible[0] and "noise_injected" not in visible[0]
        assert retrieve(task, mode="R2", manifest=manifest)["retrieved_document_ids"] == r2["retrieved_document_ids"]


def test_corpus_manifest_and_public_card_drift_fail_closed() -> None:
    manifest = freeze_candidate_manifest()
    task = _catalog()["counter_race"]
    tampered_manifest = deepcopy(manifest)
    tampered_manifest["corpus_sha256"] = "0" * 64
    try:
        retrieve(task, mode="R1", manifest=tampered_manifest)
    except CandidateRetrievalError:
        pass
    else:
        raise AssertionError("tampered manifest accepted")
    changed_task = deepcopy(task)
    changed_task["task_card"]["title"] = "Altered task title"
    try:
        retrieve(changed_task, mode="R1", manifest=manifest)
    except CandidateRetrievalError:
        pass
    else:
        raise AssertionError("unfrozen public task accepted")
    raw = CORPUS_PATH.read_bytes()
    try:
        CORPUS_PATH.write_bytes(raw.replace(b"Concurrent read", b"Concurrent write", 1))
        try:
            _read_rows()
        except CandidateRetrievalError:
            pass
        else:
            raise AssertionError("altered candidate corpus accepted")
    finally:
        CORPUS_PATH.write_bytes(raw)


def test_no_exact_policy_literals_or_hidden_cell_labels_in_candidate_text() -> None:
    from benchmark.finite_family_registry import family_module
    from benchmark import (
        finite_policy_v1, finite_path_v2, finite_replay_v3, finite_race_v4,
        finite_batch_a_v5, finite_batch_b_v5, finite_batch_c_v6,
    )
    modules = (finite_policy_v1, finite_path_v2, finite_replay_v3, finite_race_v4,
               finite_batch_a_v5, finite_batch_b_v5, finite_batch_c_v6)
    c1 = {task["family"]: task for module in modules for task in module.build_reference_tasks()
          if task["condition"] == "C1"}
    for row in _read_rows():
        text = row["text"].lower()
        assert all(label not in text for label in ("c1", "c2", "c3", "c4", "c5", "proof_sha256"))
        task = c1[row["family"]]
        public = family_module(task).public_projection(task)
        options = public.get("candidate_modes", [])
        if not options:
            options = [choice for values in public.get("candidate_options", {}).values() for choice in values]
        for option in options:
            if "_" in option or "-" in option:
                assert option.lower() not in text


class CandidateR1TwentyTests(unittest.TestCase):
    def test_source_coverage(self) -> None:
        test_exact_twenty_family_source_coverage()

    def test_treatment_determinism(self) -> None:
        test_matched_r0_r1_and_exploratory_r2_for_all_twenty()

    def test_legacy_domain_gap(self) -> None:
        test_current_retrievers_do_not_cover_twenty_public_domains()

    def test_fail_closed_drift(self) -> None:
        test_corpus_manifest_and_public_card_drift_fail_closed()

    def test_literal_leakage_markers(self) -> None:
        test_no_exact_policy_literals_or_hidden_cell_labels_in_candidate_text()


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print("excluded twenty-family R1 prototype tests passed")
