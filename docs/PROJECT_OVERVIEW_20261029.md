# Research project overview — 29 October 2026

**Research title:** *The Tests Passed. The Benchmark Said No: A Hidden Veto in AI Security Repair*

**Author:** Imran Zakirov, independent student researcher, Bishkek, Kyrgyzstan
**Status:** completed exploratory audit; prospective causal study not yet admitted. This overview is for GitHub project review, not a claim of journal acceptance.

## Summary (150 words)

AI coding agents are evaluated by whether a security checker accepts their patches. We audited an experiment with one `qwen3:4b` agent, 40 episodes, and five cryptographic and web task families. The study crossed nominal task repairability, feedback detail, and fixed contextual guidance. In 9 of 20 episodes labeled “unavailable,” the final submitted program passed the evaluator's implemented family tests, but a hidden condition still produced `FAIL`. An independent recount of terminal receipts confirmed the count. This matters because a benchmark can make an agent appear unable to repair or stop even when its verdict is disconnected from its own tests. It does not show that the programs were secure beyond those finite tests, nor that the agent revised code after a known raw pass: the 81 per-action records lack raw test outcomes. A corrected-oracle pilot remains exploratory. The next planned study will compare matched continuations after truthful versus false verdicts.

## What was done and found

| Question | Evidence-based answer |
| --- | --- |
| What was tested? | One local coding agent on five selected security-repair task families, with 40 historical main episodes and a separate eight-episode AEAD pilot. |
| What is the main finding? | In 9/20 final submissions from the nominally unavailable arm, the implemented family tests passed but a hidden acceptance rule rejected the candidate. Across all 40 main episodes, 25 final candidates passed raw tests and 16 were accepted. |
| Why does it happen? | The evaluator computes final acceptance as `raw_test_pass AND condition_reachable`; the flag is false for the `UD`/`UW` conditions ([source](../sandbox/docker_candidate.py#L52-L57)). The agent did not see this flag. |
| What does it mean? | This local benchmark's final verdict cannot by itself establish that the agent failed to solve, recognize, or stop on a genuinely impossible repair. It is an evaluator-validity finding. |

## Two ways a checker can mislead

| Direction | Recorded evidence | Scope |
| --- | --- | --- |
| **Rejected despite passing the implemented tests** | 9/20 final agent submissions in the nominally unavailable arm passed the family tests, then failed a hidden acceptance rule. | Historical agent cohort; a test–gate disagreement, not proof of general security. |
| **Passed weak tests despite an insecure mutation** | 4/4 deliberately insecure authored mutations passed a weak suite; all four failed a stronger suite and triggered Bandit warnings. | [Separate authored calibration](../analysis/SAST_MUTATION_JOIN_20261028.md); zero agent submissions and no prevalence estimate. |

The rows have different sources and denominators. They are not pooled, and a Bandit warning is not itself a security verdict.

![Raw finite tests versus final benchmark acceptance in the historical runs](../paper/milestone/hidden_veto_results.png)

**Independent check:** [archived-receipt recount](../paper/INDEPENDENT_DISCORDANCE_CHECK_20261008.md) and [original-archive provenance check](../paper/ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md). The [research article](../paper/final.md) explains the methods, full results, and limitations. Read the [identified PDF](../paper/submission/full_paper.pdf) or [anonymous review PDF](../paper/submission/full_paper_anonymous.pdf).

## Reproduce the headline result

From a complete repository checkout with Python 3.12 or later, run:

```sh
python3 -B -m reproduction.verify_project
```

The [read-only verifier](../reproduction/README.md) rebuilds the historical summary in a temporary directory and checks it against independent terminal receipts and source-fidelity records. Success prints `VERIFIED_EXPLORATORY_EVIDENCE` with 40 episodes and 9/20 hidden-gate disagreements. It does not call the model, Docker, or the prospective main collector.

The broader offline `sh reproduction/reproduce.sh` check passed on 29 October 2026, including 298 unit/integration tests and six focused real-code regression tests. It also passed from a relocated full-history clone after the archived-path audit fix. Its final prospective preflight correctly reports `NOT_READY` because the main study has not been admitted.

## Limits and next research question

Passing these finite checks does not prove that a program is generally secure. The historical action records lack raw test results for all 81 checks, so the exact moment of test–verdict disagreement during an episode is unknown. The completed cohort has five selected families and one run per arm; it does not estimate an effect for all AI coding agents. Later pilots, including one selected false-`FAIL` pair, are excluded and descriptive.

The next question is **“Can a wrong verdict undo a security fix?”** The [proposed matched study](INTEGRATED_STUDY_EXTENSION_20261018.md) would start two continuations from the same independently verified candidate and change only the feedback. A separate proposed second-opinion stage would ask whether access to an independent check prevents finite-property regression. Both require human task review, a frozen protocol and analysis plan, and the release gate; **zero prospective main episodes are eligible** today ([gate](MAIN_RELEASE_GATE_MATRIX_20261005.md)).

## Two-minute explanation (Russian)

«Я исследую, насколько честно бенчмарк оценивает ИИ-агента, который пытается исправлять проблемы безопасности в коде. Мы разобрали 40 сохранённых запусков одной локальной модели на пяти семействах небольших задач. Самое неожиданное: в девяти из двадцати запусков, помеченных как “невозможные”, итоговый код проходил реализованные тесты, но система всё равно ставила `FAIL`.

Причина оказалась в дополнительном скрытом условии в коде оценщика. Для этой группы оно запрещало принять решение независимо от результата тестов. То есть по такой оценке легко ошибочно решить, будто агент не умеет исправлять код или вовремя останавливаться. Мы перепроверили девять случаев по сохранённым итоговым записям.

Но я не утверждаю, что эти девять программ безопасны во всех реальных условиях: тесты были ограниченными. Также старые логи не сохраняли сырой результат каждой промежуточной проверки, поэтому нельзя доказать, что агент продолжал менять код *после* уже пройденного теста.

Теперь я предлагаю следующий, более сильный эксперимент: взять один и тот же проверенный кандидат, сообщить агенту либо правдивый, либо ложный результат и сравнить дальнейшие изменения. Это позволит проверить, может ли неверная обратная связь испортить исправление. Пока это план; его основной запуск требует независимой проверки задач и фиксации протокола.»

## Likely mentor questions

**Is this proof that the AI wrote secure code?** No. The programs passed a bounded set of implemented checks; broader security was not established.

**Is the hidden veto a secret attack by the model?** No. It is a condition in our evaluator's source code. “Hidden” means the experimental agent did not receive that rule.

**Did false feedback cause the agent to damage a fix?** The historical runs cannot answer that. A selected excluded pilot pair motivates the question, but a causal estimate needs the admitted matched study.

**Is the project ready for journal submission?** The exploratory article is formatted and reproducible to the stated extent, but the author declarations, privacy review, venue decision, and scientific sign-off remain open. The larger prospective experiment is still behind its release gate.
