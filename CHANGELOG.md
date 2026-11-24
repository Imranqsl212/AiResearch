# Project changes

## 24 November 2026 — reasoning effort across hosted Codex models

- All eleven selectable aliases completed the [176-episode repair comparison](analysis/c5_codex_effort_20261124/comparison.md). Every defect was repaired before a requested check. Low and high effort produced 27 and 7 unchanged submissions.
- On a [six-task panel at all 64 supported model and effort settings](analysis/c5_effort_panel_20261124.md), every model used more reasoning tokens at max than at xhigh. All 66 matched task outcomes stayed the same. The [updated manuscript](paper/c5/manuscript.md) includes the per-task contrasts and their denominators.

## 24 November 2026 — remaining decisions after a false alarm

- Added the [hosted CLI pilot](docs/C5_CLI_PILOT_20261124.md). Sol and Luna completed eight episodes each. All eight defective starts were repaired before any new check; the 24 planned Claude episodes have no observations. The [historical recovery audit](analysis/c5_recovery_identity_20261124.json) also identifies each previously verified candidate restored on the final decision.
- Reframed the C5 manuscript as [What Is One More Step Worth After a False Alarm?](paper/c5/manuscript.md). A [source-bound historical audit](analysis/c5_budget_prefix_audit_20261124/audit.json) reports failing-candidate counts of 4/1, 8/6 and 5/7 after the three observed decisions (truthful PASS / false FAIL, fourteen branches each). The reversal is descriptive; every branch knew the same three-decision cap.
- Added a separate [verdict × announced-budget protocol](docs/C5_BUDGET_STATISTICAL_PROTOCOL_20261124.md), [runner](experiments/c5_budget_README.md) and interaction-specific planning simulation. The design jointly changes the announced and enforced horizon. Family weighting, missingness bounds, incomplete-window reporting and four-model multiplicity are explicit; nineteen families have limited power under plausible clustering assumptions.
- Kept [synthetic factorial calibration](experiments/c5_budget_calibration_receipt.json), the [matched correct/defective challenge](docs/C5_EVIDENCE_CHALLENGE.md), and [four upstream test-correction cases](external_checker_audit_20261124/README.md) separate from model evidence. External-case admission and agent outcomes remain pending.
- Added the [budget registration builder](paper/c5/prepare_budget_registration.py) and [local packet receipt](docs/c5_budget_registration_receipt_20261124.json). No registry timestamp or confirmatory model collection is claimed. The earlier registration builder, statistical plan, historical data and companion stopping-attribution paper remain available.

## 23 November 2026 — checker feedback study

- Added a [focused manuscript](paper/c5/manuscript.md) comparing stopping and damage after matched truthful and false verdicts. Its empirical tables distinguish persistent and one-shot interventions.
- Released a local [data candidate](data/c5/README.md) with a standalone recount of the 14 archived pairs. Added finite-oracle calibration, two CWEval observation controls and a prospective model-free runner.
- Added a [statistical design and power analysis](docs/C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md) and [research status](docs/C5_STUDY_STATUS.md) with the evidence still needed for confirmatory claims.
- Indexed [historical protocols](docs/archive/README.md). The companion [stopping-attribution paper](paper/final.md) and its previous evidence bundle retain their original paths.
