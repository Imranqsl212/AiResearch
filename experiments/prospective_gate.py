"""Collection gate: real review records, explicit approval, verified OSF registration.

An operator's identity/independence attestation is not cryptographically
authenticated here. The existing structural admission validator remains honest
about that limit. The registration is independently fetched from OSF, and must
publish the exact plan and protocol hashes before collection. This gate permits
bounded engineering collection; it never grants scientific/main eligibility.
"""
from __future__ import annotations

from datetime import datetime, timezone
import csv
import re
from pathlib import Path
import tempfile
from urllib.request import Request, build_opener

from analysis.validate_human_admission_register import (
    validate, _read_csv, REVIEW_COLUMNS, ADJUDICATION_COLUMNS,
)
from analysis.admission_review import V7_CANDIDATE_INDEXES
from experiments.main_collector import _sha
from experiments.prospective_finite import ROOT, NoRedirect, ProspectiveError, strict_object


def _timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ProspectiveError("missing or invalid approval/registration timestamp") from exc
    if timestamp.tzinfo is None:
        raise ProspectiveError("timestamps must include a timezone")
    return timestamp


def fetch_registration(registration_id: str, *, token: str | None = None) -> bytes:
    """Read metadata from a fixed official origin; optional token is never logged."""
    if re.fullmatch(r"[a-z0-9]{5,12}", registration_id) is None:
        raise ProspectiveError("invalid public OSF registration ID")
    url = f"https://api.osf.io/v2/registrations/{registration_id}/"
    headers = {"Accept": "application/json"}
    if token is not None:
        if not token or "\n" in token or "\r" in token:
            raise ProspectiveError("explicitly supplied OSF read token is absent or malformed")
        headers["Authorization"] = "Bearer " + token
    with build_opener(NoRedirect).open(Request(url, headers=headers), timeout=30) as reply:
        body = reply.read(2_097_153)
        if reply.status != 200 or len(body) > 2_097_152:
            raise ProspectiveError("OSF metadata response is unavailable or too large")
        return body


def _immutable_answer(attributes: dict, field: str) -> str:
    """Read only one designated frozen answer, never editable descriptions.

    OSF uses direct strings and nested {value: ...} answers across registration
    schemas. The approval identifies the relevant answer key (default summary).
    Only value payloads in that field are considered; unrelated fields/keys and
    descriptive metadata cannot establish the required hash binding.
    """
    if not isinstance(field, str) or not field or len(field) > 200:
        raise ProspectiveError("invalid frozen OSF answer field")
    def value_text(value):
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and "value" in value:
            return value_text(value["value"])
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            return "\n".join(value)
        return ""
    answers = []
    for name in ("registration_responses", "registered_meta"):
        container = attributes.get(name)
        if isinstance(container, dict) and field in container:
            answers.append(value_text(container[field]))
    if not answers or not any(answers):
        raise ProspectiveError("OSF lacks the designated immutable registration answer")
    return "\n".join(answers)


def _admission_audit(review_path: Path, adjudication_path: Path, plan: dict) -> dict:
    """Validate only the planned family rows, retaining original register hashes.

    The shared register may contain other candidate families (e.g. counter_race).
    Their pending rows are not admissions or failures for this selected cohort.
    This projection does not create or complete any human review record.
    """
    selected = set(plan["families"])
    known = {row["family"] for name in V7_CANDIDATE_INDEXES
             for row in strict_object((ROOT / name).read_bytes(), "catalog")["tasks"]}
    reviews = _read_csv(review_path, REVIEW_COLUMNS)
    adjudications = _read_csv(adjudication_path, ADJUDICATION_COLUMNS)
    if any(row["family"] not in known for row in [*reviews, *adjudications]):
        raise ProspectiveError("review registers contain an unknown family")
    with tempfile.TemporaryDirectory(prefix="finite-admission-subset-") as directory:
        projected = []
        for name, rows, columns in (("review.csv", reviews, REVIEW_COLUMNS),
                                    ("adjudication.csv", adjudications, ADJUDICATION_COLUMNS)):
            path = Path(directory) / name
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(row for row in rows if row["family"] in selected)
            projected.append(path)
        audit = validate(*projected, index_paths=tuple(plan["index_paths"]))
        audit["selected_family_projection"] = {
            "families": sorted(selected),
            "omitted_unselected_families": sorted({r["family"] for r in [*reviews, *adjudications]} - selected),
            "review_projection_sha256": _sha(projected[0].read_bytes()),
            "adjudication_projection_sha256": _sha(projected[1].read_bytes()),
            "original_review_sha256": _sha(review_path.read_bytes()),
            "original_adjudication_sha256": _sha(adjudication_path.read_bytes()),
        }
    return audit


def check_collection_gate(*, plan_raw: bytes, approval_path: Path,
                          review_path: Path, adjudication_path: Path,
                          preregistration_path: Path,
                          registration_fetcher=None, osf_token: str | None = None) -> dict:
    """Fail locally before any network access when reviews/approval are pending."""
    plan = strict_object(plan_raw, "plan")
    approval_raw = approval_path.read_bytes()
    approval = strict_object(approval_raw, "operator approval")
    prereg_raw = preregistration_path.read_bytes()
    hashes = {"plan_sha256": _sha(plan_raw), "review_register_sha256": _sha(review_path.read_bytes()),
              "adjudication_register_sha256": _sha(adjudication_path.read_bytes()),
              "preregistration_sha256": _sha(prereg_raw)}
    if (approval.get("status") != "APPROVED_FOR_BOUNDED_COLLECTION"
            or any(approval.get(k) != v for k, v in hashes.items())
            or approval.get("independent_human_reviews_confirmed") is not True
            or approval.get("collection_has_not_started") is not True
            or set(approval.get("admitted_families", [])) != set(plan["families"])):
        raise ProspectiveError("approval is absent/pending or not bound to this exact plan and reviews")
    for field in ("approver_name", "approver_role", "independence_verification_basis"):
        if (not isinstance(approval.get(field), str) or not approval[field].strip()
                or approval[field].strip().upper() in {"PENDING", "TODO", "PLACEHOLDER"}):
            raise ProspectiveError("approval lacks a real identified human attestation")
    now = datetime.now(timezone.utc)
    if _timestamp(approval.get("approved_at")) >= now:
        raise ProspectiveError("approval must precede collection")
    audit = _admission_audit(review_path, adjudication_path, plan)
    if (audit["status"] != "RECORDS_COMPLETE_UNVERIFIED" or audit["errors"]
            or set(audit["recorded_admit_families"]) != set(plan["families"])):
        raise ProspectiveError("independent family admission records are incomplete or inconsistent")
    registration_id = approval.get("osf_registration_id", "")
    if re.fullmatch(r"[a-z0-9]{5,12}", registration_id) is None:
        raise ProspectiveError("approval lacks a public OSF registration ID")
    registration_raw = (registration_fetcher(registration_id) if registration_fetcher is not None
                        else fetch_registration(registration_id, token=osf_token))
    registration = strict_object(registration_raw, "OSF registration")
    data = registration.get("data", {})
    attrs = data.get("attributes", {})
    visibility_verified = (attrs.get("public") is True or
                           (attrs.get("public") is False and attrs.get("embargoed") is True
                            and isinstance(osf_token, str) and bool(osf_token)))
    if (data.get("type") != "registrations" or data.get("id") != registration_id
            or attrs.get("withdrawn") is not False or not visibility_verified
            or attrs.get("pending_registration_approval") is not False
            or attrs.get("archiving") is not False
            or _timestamp(attrs.get("date_registered")) >= now):
        raise ProspectiveError("OSF record is not an accessible, approved prior registration")
    # These literal hash lines must be in the frozen registration responses;
    # editable descriptive metadata alone is deliberately insufficient.
    answer_field = approval.get("osf_answer_field", "summary")
    values = _immutable_answer(attrs, answer_field)
    for name in ("plan_sha256", "preregistration_sha256"):
        if f"{name}: {hashes[name]}" not in values:
            raise ProspectiveError("frozen OSF responses do not bind the exact plan/protocol hashes")
    return {"status": "COLLECTION_GATE_PASSED", "eligible_for_main_analysis": False,
            "checked_at": now.isoformat(), **hashes,
            "approval_sha256": _sha(approval_raw), "admission_structural_audit": audit,
            "identity_evidence": "identified_operator_attestation_not_authenticated_identity",
            "registration_visibility": "public" if attrs.get("public") else "approved_embargo",
            "authenticated_registration_read": osf_token is not None,
            "immutable_answer_field": answer_field,
            "osf_metadata_sha256": _sha(registration_raw), "osf_metadata": registration,
            "registration_url": f"https://osf.io/{registration_id}/",
            "registration_api_url": f"https://api.osf.io/v2/registrations/{registration_id}/",
            "main_analysis_release": "NOT_GRANTED_BY_COLLECTION_GATE"}
