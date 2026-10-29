#!/bin/sh
# Validate controlled engineering fixtures without promoting pilot data.
set -eu

research_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$research_root"
PYTHONPATH="$research_root${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH

python3 -B tests/test_finite_policy_v1.py
python3 -B -m benchmark.validate_finite_policy_v1
python3 -B tests/test_finite_path_v2.py
python3 -B -m benchmark.validate_finite_path_v2
python3 -B tests/test_finite_replay_v3.py
python3 -B -m benchmark.validate_finite_replay_v3
python3 -B tests/test_finite_race_v4.py
python3 -B -m benchmark.validate_finite_race_v4
python3 -B tests/test_finite_batch_a_v5.py
python3 -B -m benchmark.validate_finite_batch_a_v5
python3 -B tests/test_finite_batch_b_v5.py
python3 -B -m benchmark.validate_finite_batch_b_v5
python3 -B tests/test_finite_batch_c_v6.py
python3 -B -m benchmark.validate_finite_batch_c_v6
# The separately versioned v7 candidate remains outside the admission set.
python3 -B -m benchmark.validate_finite_batch_c_v7
python3 -B -m analysis.admission_review --json-out /tmp/admission_review_reproduced.json
python3 -B -m analysis.validate_human_admission_register --catalog v6-current
python3 -B -m analysis.validate_human_admission_register --catalog v7-candidate
# Requires the tracked v0.2 page snapshot archive; one page is redacted.
python3 -B -m analysis.validate_r1_v2_source_review
python3 -B -m analysis.validate_statistical_plan_candidate

# Recompute the finite confusion matrices and mutation checks from the saved
# fixtures. The comparison fails if the checked-in calibration becomes stale.
calibration_tmp=$(mktemp)
trap 'rm -f "$calibration_tmp"' EXIT HUP INT TERM
python3 -B -m analysis.finite_fixture_calibration --output "$calibration_tmp"
cmp "$calibration_tmp" analysis/finite_fixture_calibration_20261004.json
python3 -B -m analysis.family_sign_sensitivity --check
python3 -B -m analysis.render_v1_methods --output-dir tables/v1_methods
python3 -B -m unittest \
  tests.test_v1_baselines \
  tests.test_ollama_adapter \
  tests.test_v1_ollama_adapter \
  tests.test_v1_analysis \
  tests.test_retrieval_v1 \
  tests.test_retrieval_v2 \
  tests.test_v1_retrieval_manifest \
  tests.test_v1_collector \
  tests.test_finite_family_collector \
  tests.test_race_v4_collector \
  tests.test_v1_preflight \
  tests.test_v1_task_index \
  tests.test_validate_finite_path_v2 \
  tests.test_validate_finite_replay_v3 \
  tests.test_v1_rag_block \
  tests.test_excluded_pilot_audit \
  tests.test_excluded_rag_report \
  tests.test_cross_model_rag_excluded \
  tests.test_c5_false_failure_probe_v1 \
  tests.test_c5_onset_probe_v1 \
  tests.test_real_code_sqli \
  tests.test_real_code_command_injection \
  tests.test_finite_batch_b_v5 \
  tests.test_finite_batch_c_v6 \
  tests.test_admission_review \
  tests.test_main_orchestrator \
  tests.test_family_sign_sensitivity \
  tests.test_full_catalog_live_feasibility \
  tests.test_c5_agent_onset_fork \
  tests.test_retrieval_r1_20_candidate \
  tests.test_r1_20_live_feasibility \
  tests.test_private_excluded_pilot_bundle \
  tests.test_human_admission_register \
  tests.test_v1_power_sensitivity \
  tests.test_v1_companion_power_sensitivity \
  tests.test_finite_batch_c_v7 \
  tests.test_retrieval_r1_20_candidate_v2 \
  tests.test_r1_source_snapshots_v2 \
  tests.test_validate_r1_v2_source_review \
  tests.test_statistical_plan_candidate \
  tests.test_main_collector \
  tests.test_main_c5_fork_scaffold \
  tests.test_main_c5_precursor_bridge \
  tests.test_c5_raw_archive_reader \
  tests.test_main_live_dispatch_excluded \
  tests.test_main_ollama_transport_excluded \
  tests.test_excluded_live_dispatch_crash_audit \
  tests.test_v7_excluded_integration \
  tests.test_c5_family_ledger \
  paper.test_author_review_bundle

# SQLite connection lifecycle regression: ResourceWarning is a hard failure.
python3 -B -W error::ResourceWarning -m unittest tests.test_real_code_sqli
python3 -B -W error::ResourceWarning -m unittest tests.test_real_code_command_injection

# This produces NO_ELIGIBLE_DATA until a locked, validated main cohort exists.
python3 -B -m analysis.v1_pipeline --manifest-dir experiments/v1/manifests

# Keep the preflight's explicit NOT_READY result visible. Status 2 is expected
# for the checked-in design-stage manifest and is not a successful main gate.
preflight_status=0
python3 -B -m reproduction.preflight --manifest experiment_manifest.json || preflight_status=$?
if [ "$preflight_status" -ne 0 ] && [ "$preflight_status" -ne 2 ]; then
  exit "$preflight_status"
fi
if [ "$preflight_status" -eq 2 ]; then
  echo 'Prospective v1 main experiment: NOT_READY'
fi
