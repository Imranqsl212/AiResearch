# Who stopped the coding agent?

The [manuscript](../paper/final.md) asks what a reader can establish about a coding agent after only its public records survive. This supplement contains two archive censuses and a controlled experiment on a public exporter. The earlier [20-episode discovery audit](../external_audit_20261122/REPORT_RU.md) and the original 40 local runs retain their own denominators.

## What the archives establish

| Population | Observed result | Evidentiary limit |
| --- | --- | --- |
| OpenHands CodeAct 2.1, all 500 Verified issues | 265 listed as resolved. All 500 released files were message lists, 278 ending on a user-role message and 222 on a tool message. | Zero files contained a separate last response or controller stop field. Zero lists contained a structured assistant tool call named finish or submit. |
| Same release, 490 issues held out from discovery | 261 listed as resolved, 274 ending on a user role and 216 on a tool role. | The missing final response occurred throughout this release, including among successful runs. |
| Ten original OpenHands inputs, two simulated responses per input | A finish request and an instruction to run pwd produced exactly the same exported bytes in all ten pairs. Each pair reproduced its original archive file. Providing the original patch and grade preserved every collision. | The last request can differ while the visible record stays fixed. These are constructed alternatives. The actual last request and controller decision for each historical episode remain unknown. |
| SWE-agent with Claude 3 Opus, 78 published successes on the 490 held-out issues | 53 explicit final submissions, 13 automatic submissions at the cost limit, 12 missing traces. | The automatic share lies between 13/78 and 25/78 (16.7–32.1%). Requiring explicit submission would credit 53–65/490 (10.82–13.27%), compared with the native 78/490 (15.92%). |
| SWE-agent with GPT-4, 112 published successes on those 490 issues | Zero trace patches matched their predictions byte for byte. A separate diagnostic linked 103 after allowing one leading LF byte (0x0A). Of those, 98 were explicit and five automatic. | All 112 remain unknown under the frozen exact rule. The nine remaining discrepancies have a different byte pattern. The source of the extra byte has not been established. |

For the ten controlled pairs, any deterministic binary classifier forced to label every case must predict the same request for both copies of each exported input. It gets exactly ten of twenty right under the deliberately equal weighting. Recording the requested tool distinguished all ten pairs. A separate controller receipt is needed to establish whether the runtime acted on a finish request. The [controlled experiment](projection/REPORT.md) provides the schemas, pinned source lines and per-pair digests.

A digest links the SWE-agent trace to the published prediction. The issue ID links that prediction to the published grade. The censuses did not independently attest the exact patch bytes consumed by the grader on all successes. The Claude bounds allocate each absent trajectory to one of the possible classes. They describe a fixed archive. They carry no sampling confidence level and estimate no behavior under a changed policy. The full Claude series has 79 successes (53 explicit, 14 automatic, 12 unknown). The full GPT-4 series has 112. Among the 58 held-out issues resolved by both models, the strict rule never identified both mechanisms, and zero pairs had byte-identical published predictions. This last check supplies no natural example of opposite endings on the same identical patch. [Strict results](summary.json) · [Per-issue evidence](rows.csv) · [Matched analysis](matches.json) · [Post hoc LF comparison](boundary_lf.json)

One Claude log appeared to contradict its published resolution. For django__django-13658, the terminal marker reads “Some Tests Failed.” Each of the 182 tests required for this issue was logged as passing, and the recorded failures and error concerned three other tests. A generic terminal log marker alone gives an incorrect account of the benchmark criterion here. [Required-test comparison](grading/required_tests_13658.json) · [Official grading log](https://swe-bench-submissions.s3.amazonaws.com/verified/20240402_sweagent_claude3opus/logs/django__django-13658.20240402_sweagent_claude3opus.eval.log) · [Official test split](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified/tree/78f471bf655a3137b2e8a75af1501690ec009ec3)

## Sampling and attribution

The [SWE-agent plan](protocol.md), [matched-issue plan](matched_plan.md), [OpenHands coverage plan](openhands/plan.md), and [projection protocol](projection/protocol.json) have local timestamp and digest receipts. These were local freezes. The ten discovery issues and the earlier successful automatic submission were known when designing the follow-up. Both archive censuses exclude the same ten issues in their primary summaries. The controlled projection instead deliberately reuses the ten known inputs. Never add these counts together as independent runs.

The canonical test split contains 500 unique issues. The OpenHands object listing covers exactly those 500. Its predictions cover 499, the Claude predictions cover 496, and the GPT-4 predictions cover 495. Official outcome membership, prediction availability and trajectory availability are separate fields. The Claude and GPT-4 censuses use every published successful issue regardless of trace availability. The [roster check](openhands/verified_roster.json) records the full sets, pinned revisions and file hashes. [OpenHands rows](openhands/rows.csv) · [OpenHands coverage and outcome cross-tabulation](openhands/summary.json)

For the strict classification, the script links the trajectory's submitted patch to the sole distinct prediction and compares the final trajectory action with non-demonstration assistant history. Explicit means a standalone submit with submitted status. Automatic requires a system exit action, a matching submitted-at-exit status and an autosubmission receipt. Twelve Claude trajectories were absent from the complete collection and returned HTTP 404. An independent script reread the resolved rosters, the predictions and all available successful trajectories, corroborating the classifications. The later within-run one-byte diagnostic leaves the strict cross-model patch comparison intact. [Primary source manifest](manifest.json)

## Relation to prior work

Yang et al. already separated explicit submissions and successful autosubmissions on SWE-bench Full and Lite. The two Verified releases also supply aggregate exit counts. SWE-smith reports accuracy conditional on natural termination. SWE-Master discounts successful forced submission during training. Liu et al. analyze process phases and resolution. The contribution here is to test which final requests are distinguishable after export and to show exactly which credited patches can be linked to controller events, with the unknown cases visible. [SWE-agent, Table 13](https://papers.nips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf#page=38) · [Claude exit counts](https://github.com/SWE-bench/experiments/blob/40f164d5b8f1d249bf95a6df8b74b577fd8e519d/evaluation/verified/20240402_sweagent_claude3opus/results/end_condition.json) · [GPT-4 exit counts](https://github.com/SWE-bench/experiments/blob/40f164d5b8f1d249bf95a6df8b74b577fd8e519d/evaluation/verified/20240402_sweagent_gpt4/results/end_condition.json) · [SWE-smith](https://arxiv.org/html/2504.21798v2#S4.SS2) · [SWE-Master](https://arxiv.org/html/2602.03411v1#S3.SS4.SSS2) · [Process-Centric Analysis](https://doi.org/10.1145/3798271)

## Reproduce

From the repository root, check the distributed rows, cohort accounting, classification bounds, cross-model comparison and controlled-pair digests offline with standard Python.

```sh
python3 -B submission_audit_20261123/verify_saved.py
```

To re-read the archived sources, run the following commands from the repository root. Downloads use public HTTPS. The census, coverage and required-test commands regenerate their derived reports. The other commands below verify saved results. The independent roster and grading-log checks require PyArrow (tested with 22.0.0), and the controlled projection requires jq (tested with 1.8.2). The projection report also documents offline cache use. The scripts do not run a model or execute the downloaded programs, patches, tests or commands.

```sh
python3 -B submission_audit_20261123/openhands/verify_verified_roster.py
python3 -B submission_audit_20261123/openhands/coverage.py
python3 -B submission_audit_20261123/census.py --workers 4
python3 -B submission_audit_20261123/check_matches.py --raw
python3 -B submission_audit_20261123/check_boundary_lf.py
python3 -B submission_audit_20261123/grading/check_required_tests.py
python3 -B submission_audit_20261123/projection/run_projection.py --check
python3 -B submission_audit_20261123/verify_saved.py
```

Use [the local study reproduction instructions](../paper/README.md) for the historical cohorts and the manuscript build. Raw trajectories remain in the official public collections. This directory redistributes hashes, field locators, derived labels and explicitly synthetic control records.
