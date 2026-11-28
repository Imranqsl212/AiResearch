# When Should a Model Put the Bug Back?

Changing one trusted target answer elicited patches satisfying both opposing requirements in 10/16 complete QuixBugs pairs. On a historical Matplotlib fix, the test that exposed the original defect passed a new regression. A test both historical versions passed exposed the new failure. The follow-up ledgers contain 364 usable hosted decisions out of 888 assigned. The 138 earlier one-decision controls and the original pilots retain their separate denominators. All of these are exploratory.

[Manuscript](paper/c5/manuscript.md) · [PDF](paper/c5/checker_feedback.pdf) · [Anonymous PDF](paper/c5/checker_feedback_anonymous.pdf) · [Offline evidence packet](paper/c5/feedback_evidence.zip) · [Blinded reviewer packet](paper/c5/feedback_evidence_anonymous.zip) · [Data and schema](data/c5/README.md) · [New statistical protocol](docs/C5_BUDGET_STATISTICAL_PROTOCOL_20261124.md) · [Study status](docs/C5_STUDY_STATUS.md)

## Main experiments

The [contract reversals on unchanged benchmark code](analysis/quix_contract_reversal_20261128/comparison.md) and [official QuixBugs test replay](analysis/quix_upstream_tests_20261128/comparison.md) support Figure 1. The [identical-value comparison](analysis/output_provenance_20261128/comparison.md) and [actual versus required output](analysis/feedback_factorial_20261128/comparison.md) distinguish the provenance of evidence from its contents. The [maintenance repairs](analysis/production_patch_20261128/comparison.md) and [component-level outcomes](analysis/production_patch_20261128/components.md) reconstruct the Matplotlib regression in Figure 2. [CPython identical-prompt repeats](analysis/replicate_display_20261128/comparison.md) quantify ordinary variation between fresh sessions. The [rule-omission follow-up](analysis/quix_rule_omission_20261128/comparison.md) repeats the target reversal without the two descriptions, and the [Matplotlib replication](analysis/matplotlib_replication_20261128/comparison.md) separates the original observation from fresh identical-prompt decisions. The [headless Matplotlib replay](analysis/matplotlib_axis_integration_20261128/comparison.md) runs the maintainer’s original test and records the actual axis limits across 96 further inputs. Each study records missing calls and starts that already worked.

## Earlier matched comparisons

| Comparison | Observed choices |
| --- | --- |
| [All 16 archived first edits in CPython](analysis/pprint_display_20261128/comparison.md) | With no new output, 2/4 faulty states recovered. With keys 3 and 7 or keys 3 and 20, 4/4 recovered. Both displays added the same two recoveries. Every arm preserved 12/12 working states. |
| [All seven starting implementations across dateutil and CPython](analysis/cross_project_display_20261128/comparison.md) | Each condition repaired 8/8 faulty model–source combinations. Revealing output and no output produced identical final sources in 14/14 blocks. A shared positive-offset display preceded the only regression, in a working dateutil parser. |
| [Trusted examples for three ambiguous specifications](analysis/reference_example_20261128/comparison.md) | Both models chose the correct implementation for both opposing target outputs in all 12 matched blocks. The 48 native choices yield 72 target assessments because a response to a prompt shared across two hidden targets is scored twice. |

## The observed reversal

![Failing candidates after decisions one, two and three: truthful PASS 4, 8, 5; false FAIL 1, 6, 7. Each arm contains 14 continuations.](paper/c5/figures/observed_horizon.png)

In 14 selected pairs, the counts of branches holding a failing candidate were **4/1, 8/6 and 5/7** after successive decisions, shown as truthful PASS / false FAIL. Three truthful branches recovered on the last decision. All six false-failure branches entering that decision with a failing candidate inspected it and retained it. Both conditions had eight entries into failure across the trajectory. From decision two to three the aggregate ranking reversed, yet the sole passing arm switched sides in 0/14 matched pairs. Three pairs gained a second passing branch and one lost a passing branch. [Paired transitions and family sensitivity](analysis/c5_horizon_sensitivity_20261128/comparison.md) · [Source-bound prefix audit](analysis/c5_budget_prefix_audit_20261124/audit.json)

These are descriptive observations from one local model under persistent false feedback. Every branch knew the same three-decision limit. The second point on the graph is not an experiment with an announced two-decision budget. Later one-shot cohorts have separate denominators in the [manuscript](paper/c5/manuscript.md).

## Separate evidence streams

| Evidence | What it establishes | What remains unobserved |
| --- | --- | --- |
| [Historical trajectories](data/c5/README.md) | 78 archived decisions from 14 selected pairs across ten finite task families. | A causal effect of announcing a different remaining budget. |
| [Factorial runner calibration](experiments/c5_budget_README.md) | Four independent continuations from one verified state, actual stopping, truthful later checks and replayable missingness; [12 simulated blocks](experiments/c5_budget_calibration_receipt.json). | Model behavior in the new 2×2 experiment. |
| [Matched correct/defective challenge](docs/C5_EVIDENCE_CHALLENGE.md) | Scripted controls distinguish preserving correct work from repairing defects; a partial independent check can miss defects. | A model policy that succeeds without authored answers. |
| [Four upstream test corrections](external_checker_audit_20261124/README.md) | Pinned sources and local witnesses from CPython, pandas and python-dateutil, with case-specific reproduction limits. | Independent human admission and agent outcomes. |

The finite-oracle [calibration report](analysis/PROSPECTIVE_C5_FINITE_CALIBRATION.md) and [two CWEval observation controls](data/c5/external_controls.json) remain separate engineering evidence. None of these calibrations measures a population false-alarm rate or proves security of unrestricted programs.

In the [candidate-identity audit](analysis/c5_recovery_identity_20261124.json), all three truthful final-step recoveries matched a previously verified candidate. Two matched decision one and a third matched the starting policy.

## Codex models and reasoning effort

We compared eleven selectable CLI aliases. On the six-task panel, moving from `xhigh` to `max` left correctness unchanged on all 66 matched model–task outcomes while increasing output tokens for every model. Each setting received the same six tasks in a single invocation. [All 64 configurations, timings and token counts](analysis/c5_effort_panel_20261124.md) · [Figure by model](paper/c5/figures/effort_panel.png) · [Task definitions](experiments/c5_effort_panel.md) · [Design fixed before collection](docs/C5_CODEX_EFFORT_DESIGN_20261124.md)

On the separate eight-episode arithmetic task, low and high each preserved 44/44 correct tables and repaired 44/44 defective ones on the first decision. All 41 diagnostic requests followed a correct table. Unchanged resubmissions fell from 27 to 7. [Paired outcomes and actions across 176 episodes](analysis/c5_codex_effort_20261124/comparison.md)

## Diagnostic timing on dateutil and CPython

An exploratory pilot paired a historically correct implementation with a constructed defect in each project. GPT-6.2 Astra and GPT-6 Luna chose among concrete edits to the pinned source. Early and late arms received the same diagnostic of the initial version on opposite sides of the first decision. Both arms repaired 8/8 defective starts immediately and damaged 2/8 correct starts. All 16 matched pairs selected the same first implementation. Both timings ended with 15/16 correct implementations.

All four first-decision regressions came from Luna on CPython. It chose a textual key ordering that satisfied the old assertion but placed integer key 12 before 2. Astra also rewrote the four correct CPython starts and its alternatives passed all six held-out probes. Every second decision used a fresh session. The second prompts matched byte for byte in all 16 pairs and yielded different final implementations in two. These observations describe two selected tasks before human admission. [Counts, paired decisions and raw-response hashes](analysis/checker_timing_20261126/comparison.md) · [Frozen protocol](docs/CHECKER_TIMING_PILOT_20261126.md) · [Code variants and held-out outcomes](analysis/checker_timing_20261126/calibration.json)

### One more decision after the CPython edit

We forked all 16 CPython histories immediately after the first edit. Each originating model received the current formatter's actual output for keys 1 and 2 in one branch and 2 and 10 in the other. Each branch got one decision. The second probe exposed the lexical sorting regression. The first produced the same output as a correct formatter. Both conditions repaired all 4 failing checkpoints and preserved all 12 working checkpoints on ten held-out cases. The four failures were repeated instances of the same Luna edit. Four paired histories ended in different implementations that all passed. This pilot covered one task with one sampled continuation per branch. [Paired outcomes and source choices](analysis/pprint_postedit_20261127/comparison.md) · [Executed probes and scoring controls](analysis/pprint_postedit_20261127/calibration.json) · [Protocol frozen before collection](docs/PPRINT_POSTEDIT_20261127.md)

## The prospective comparison

The [new protocol](docs/C5_BUDGET_STATISTICAL_PROTOCOL_20261124.md) crosses a single initial PASS/FAIL with an explicitly announced and enforced allowance of two/three new decisions. It compares the gain from the third decision under FAIL with that gain under PASS. Four candidate models and nineteen families are proposed; family weighting, missing-outcome bounds and four-model Holm correction are specified. Announcing a horizon and supplying another opportunity are jointly manipulated. Under the protocol's stated moderate-clustering simulation, the nineteen-family design has limited power for small interactions.

Independent review, actual preregistration and a compute budget remain outstanding. In a separate [hosted CLI pilot](docs/C5_CLI_PILOT_20261124.md), Sol and Luna each preserved four correct starts and repaired four defective starts on a single arithmetic task. All eight repairs occurred on the first action, before any requested check returned. The [public action table](analysis/c5_cli_pilot_20261124.json) retains 24 unattempted Claude episodes. The [earlier stopping-focused plan](docs/C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md), including its C4/C3 comparison, remains available as a distinct design.

## Reproduce without models

```sh
python3 -B -m paper.c5.verify_feedback
python3 -B -m analysis.c5_public_trajectories
python3 -B data/c5/check_release.py
python3 -B -m analysis.c5_budget_prefix_audit_20261124 --output-directory analysis/c5_budget_prefix_audit_20261124 --check
python3 -B -m analysis.c5_budget_power_20261124 --output-directory analysis/c5_budget_design_20261124 --check
```

Prepare the new local registration packet without model calls:

```sh
python3 -B -m paper.c5.prepare_budget_registration --output .local_private/c5-release-20261124/budget-registration-draft.zip
```

The [draft receipt](docs/c5_budget_registration_receipt_20261124.json) records the packet's bindings; a local packet is not a registry timestamp. The [paper and release instructions](paper/c5/README.md) include PDF builds, data packaging and the older registration builder. Use [CITATION.cff](CITATION.cff) and the exact revision to cite the work.

## Companion paper and earlier studies

The separate paper [How Do We Know a Coding Agent Chose to Stop?](paper/final.md) covers 40 local episodes, the SWE-bench archive and the controlled export experiment. Its [PDF](paper/submission/full_paper.pdf), [reproduction instructions](paper/README.md) and [public archive audit](submission_audit_20261123/README.md) remain available. The [historical index](docs/archive/README.md) and [previous project overview](https://github.com/Imranqsl212/AiResearch/blob/3b5679d5b2df0d231a981fdd1419eb37fb0df721/README.md) document earlier pilots and protocols.
