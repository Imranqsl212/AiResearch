# Local pilot benchmark

This is a nine-task engineering pilot for *When to Stop*. It is not the 32-family
confirmatory benchmark and it does not launch an agent.

The only executable command is a deterministic contract check:

~~~sh
python3 -m benchmark.quality --json
~~~

It loads declarative local finite-state manifests, runs evaluator-owned reference plans,
checks independent validator receipts, and verifies that the suite contains exactly:

- 3 SOLVABLE tasks;
- 3 DISTRACTOR tasks; and
- 3 UNSOLVABLE tasks.

No network, shell, subprocess, credential, or external-target capability exists in this
package. A future runtime must give an agent only the task card, family-matched tool
contract, and bounded simulator interface; evaluator manifests and validators must be
mounted outside the agent-visible workspace.

Key paths:

- schemas/task.schema.json — machine-readable task contract;
- schemas/trajectory.schema.json — immutable trajectory contract;
- tasks/pilot/ — nine evaluator manifests across three matched semantic families;
- validators/ — independent terminal state validator;
- quality.py — static task-quality gates, not an agent runner.
