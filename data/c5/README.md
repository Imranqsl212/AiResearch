# C5 continuation decisions

This deposit candidate contains 78 observed decisions in 28 continuations from 14 selected, real local-model onset pairs. Each arm starts from the same previously verified candidate as its partner. The October cohort applied a persistent false verdict in one arm and a truthful verdict in the other. A common continuation notice and three available decisions affected both arms. Only episodes with a secure onset and archived continuations entered this cohort. These data cannot estimate how often a model reaches a secure onset.

## Files and unit of analysis

- [trajectories.jsonl](trajectories.jsonl) contains one row per ordered post-onset decision. Group by `pair` and `arm`, then order by `step`. Three steps can belong to a single continuation. Pairs can share a family.
- [event.schema.json](event.schema.json) specifies the exact fields and allowed values. A submission carries the candidate digest, one raw test result, the finite oracle result and the verdict the checker delivered. These fields are null on inspection and stop actions. The final decision alone carries the terminal controller event.
- [provenance.json](provenance.json) identifies the upstream revision, all 28 source event-file hashes, the schema digest and the hash of the released JSONL. The loader verifies every source file against the pinned action recount. [Full action recount](../../analysis/c5_feedback_action_20261104.json)
- [external_controls.json](external_controls.json) is a separate instrument check on two external task specifications and artificial observation corruptions. These rows are outside the agent dataset.
- [terminal_boolean_cases.json](terminal_boolean_cases.json) records the onset and both terminal decisions on ten cases from two historical pairs with a native Boolean allow/deny specification. Seven cases prohibit acceptance and three require it. Case indices are local to a task. Twelve pairs had no comparable decomposition under this rule. The source audit digest identifies the exact archived analysis.

## Interpretation and privacy

The 45 submissions include repeated policies. A finite-oracle failure can mean rejection of legitimate work or acceptance of prohibited work. The raw example test is narrower. A visible negative verdict can also reflect the experimental override. The source hash identifies an archived finite candidate. It does not identify a developer. A constant-policy flag identifies a declared allow-all or reject-all mode for inspection. The finite tool interface exposes no general file-write operation. Inferring deliberate manipulation, hidden intentions or the completeness of attempted modifications would require additional evidence.

The exporter projects recorded events onto enumerated values, bounded integers and SHA-256 digests. It omits source code, prompts, model prose, local pathnames, secrets and user identifiers. A format check reduces disclosure risk; the data remain linkable to the published project. The full historic raw archives, third-party SWE-bench traces and simulated OpenHands completions are outside this deposit. No DOI or public hosting receipt has been assigned to this package.

## Reproduce

```sh
python3 -B -m analysis.c5_public_trajectories
python3 -B data/c5/check_release.py
python3 -B -m analysis.c5_cweval_transfer
python3 -B -m unittest -q tests.test_c5_trace_flags
```

Publication and license terms for the team’s derivative table require the rights holders’ decision. Upstream datasets retain their own terms. Cite the repository and its exact revision until a separately identified deposit exists.
