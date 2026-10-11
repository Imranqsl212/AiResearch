# Blinded source-change coding protocol — draft for human review

**Status:** proposed codebook; no blinded coding or agreement statistic has
been performed. It applies to the 37 adjacent candidate pairs in the
historical 40-episode exploratory cohort. The source-fidelity
[inventory](../analysis/source_fidelity_v1.json) identifies each pair by
logged-source hashes without publishing source text. Twenty-five pairs have
two parseable logged sources; 12 do not. Missing structure is UNASSESSABLE,
never a zero change or an unchanged strategy.

## Unit and materials

One unit is a pair of successive agent-submitted candidates within the same
episode. The coding packet should show both exact logged sources, their
task objective and allowed environment, and a byte/AST diff when available.
It must withhold condition label, feedback arm, checker verdict, oracle result,
episode outcome and the other coder's labels. The private source packet needs
privacy review before it is shared. The reviewer register should use opaque
pair IDs; a separate local mapping connects those IDs to the hash inventory.

Because the logger replaced some credential-like assignments with the
REDACTED marker, a parseable surrogate made by adding quotes is **not** the
original AST. Coders may label observable edits outside the redacted span
only when the scope is explicit; otherwise they select UNASSESSABLE.
The three other malformed logged sources also remain unassessable for full
AST comparisons. Exact executed-source hashes are mismatched in two final
episodes. A source-to-outcome claim needs an independently linked executed
candidate, not only the logged string.

## Primary change category

Choose one category for the substantive difference visible in the pair.
If several changes occur, choose the most consequential for the task's stated
security property and explain the choice in the rationale field.

| Code | Category | Decision rule |
| --- | --- | --- |
| SURFACE | Surface or parameter edit | Names, formatting, literals, salts or thresholds change, but the security mechanism and inputs it checks remain the same. |
| EQUIVALENT_API | Similar API substitution | A library or function changes while the security property and decision rule appear equivalent for the task, such as swapping two cryptographic randomness sources. |
| MECHANISM | Security mechanism or state change | The code newly checks a relevant fact, changes the state model, or changes how the required security property is enforced. A changed API name alone is insufficient. |
| WRONG_DOMAIN | Irrelevant or false fix | The edit acts on a different security domain or output transformation and does not address the stated vulnerability, such as HTML escaping in place of SQL parameterization. |
| OTHER | Visible but outside taxonomy | A substantive change is visible but none of the above rules fits; explain it. |
| UNASSESSABLE | Evidence insufficient | The logged sources or task context cannot support a full comparison because of redaction, malformed text, missing bytes or ambiguous behavior. |

Separately code security_direction as PLAUSIBLE_IMPROVEMENT,
PLAUSIBLE_REGRESSION, NO_CLEAR_CHANGE, or UNKNOWN. These are judgments
about the authored finite task, not certifications of real-world security.
Record a short source-specific rationale and confidence as HIGH, MEDIUM,
or LOW. Do not use a test pass to infer a mechanism label.

## Review and analysis

Two independent coders should label all 37 opaque IDs after a practice round
on separate examples. Lock both registers before revealing condition or
outcome. Report the raw category cross-tabulation, percent agreement and
Cohen's kappa on pairs both coders can assess, together with the number and
reasons for UNASSESSABLE pairs. Adjudicate disagreements in a third,
separately recorded column. For the full 37-pair denominator, report category
counts with missingness; do not turn the 25 parseable pairs into a population
prevalence estimate. A small family-level descriptive summary may be shown,
but actions and pairs are nested within five selected families.

Examples in the manuscript are **illustrations, not adjudicated labels**:
slot 15 changes secrets.token_bytes to os.urandom and may fit
EQUIVALENT_API; slot 39 moves toward HTML escaping in an SQL-injection
task and may fit WRONG_DOMAIN. Slot 10 changes counter state and may fit
MECHANISM, but the hidden veto and limited checker prevent a security
success claim. These provisional examples must not be counted as a blinded
taxonomy result.
