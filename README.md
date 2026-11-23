# When a Checker Rejects a Correct Repair

After an agent produces a policy that passes the bounded reference, does false failure feedback change when it stops or what it breaks? The main C5 manuscript analyzes selected historical continuations and specifies a prospective comparison. The model-free calibration and historical results are available now. The confirmatory model study has **zero collected episodes**.

[Manuscript](paper/c5/manuscript.md) · [PDF](paper/c5/checker_feedback.pdf) · [Anonymous PDF](paper/c5/checker_feedback_anonymous.pdf) · [Data and schema](data/c5/README.md) · [Prospective statistical plan](docs/C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md) · [Study status and remaining decisions](docs/C5_STUDY_STATUS.md)

## What the archived pairs show

In 14 selected pairs, three truthful-pass branches stopped early and none of the false-failure branches did. False-failure branches nevertheless proposed fewer additional candidates (17 versus 28). In 12 of 14 pairs their first action was inspection, compared with zero in truthful-pass branches. Terminal finite-property failures went from five to seven; temporary failures went from eight to seven. These are observations from a persistent-verdict pilot with one local model. Adjacent one-shot cohorts have their own denominators. [Paired reanalysis](analysis/c5_statistical_plan_20261123/historical_summary.csv)

## Reproduce without models

```sh
python3 -B -m analysis.c5_public_trajectories
python3 -B data/c5/check_release.py
python3 -B -m analysis.c5_cweval_transfer
```

The [calibration report](analysis/PROSPECTIVE_C5_FINITE_CALIBRATION.md) distinguishes raw examples, finite reference outcomes and displayed feedback for every family and version. The [C5 paper and release instructions](paper/c5/README.md) include the PDF build, instructions for preparing a data deposit and a clean review package. Use [CITATION.cff](CITATION.cff) and the exact revision to cite the work.

## Companion paper and earlier studies

The separate paper [How Do We Know a Coding Agent Chose to Stop?](paper/final.md) covers 40 local episodes, the SWE-bench archive and the controlled export experiment. Its [PDF](paper/submission/full_paper.pdf), [reproduction instructions](paper/README.md) and [public archive audit](submission_audit_20261123/README.md) remain available. The [historical index](docs/archive/README.md) and [previous project overview](https://github.com/Imranqsl212/AiResearch/blob/3b5679d5b2df0d231a981fdd1419eb37fb0df721/README.md) document earlier pilots and protocols.
