# Four additional bounded C1--C5 mechanisms (engineering draft)

The saved set in `benchmark/tasks/v5_batch_b/` contains four distinct task
families, each with C1--C5 tasks and recomputable proofs. Every condition in a
family has the same public projection and starter candidate. The evaluator
alone sees the sensor mode and gate mode.

| Family | Security failure and repair in the complete sensor | Why C3/C4 has no repair in this finite language |
| --- | --- | --- |
| `webhook_integrity` | A parser-based HMAC check accepts a changed body with a duplicate JSON key. The permitted raw-body HMAC policy rejects it. | The raw body is withheld. The signed body and modified body have identical parsed observations but require opposite decisions. |
| `upload_content` | Filename suffix and declared MIME checks accept executable bytes. The permitted approved-byte hash policy checks content. | Content bytes are withheld. An approved image and malicious bytes with the same filename and MIME become indistinguishable. |
| `unicode_identity` | NFKC and case folding merge the trusted `ﬃ` principal with the distinct `ffi` principal. Raw or NFC exact matching distinguishes them. | The upstream boundary applies NFKC before the policy sees the principal; the two requests become identical. |
| `dns_rebinding` | Hostname checks allow a permitted URL even after it resolves to loopback. A resolved-address check distinguishes that case and rejects deceptive hosts. | The resolved address is withheld. The same URL with a public or loopback resolution becomes indistinguishable. |

The C1/C2 and C5 environments have complete observations. C2 feedback exposes
the first concrete counterexample. C4 feedback exposes a recomputed
indistinguishability witness. C5 returns a false gate failure for a candidate
that both the strong suite and finite security oracle accept.

The weak raw test exercises only the legitimate positive case. The strong test
executes every listed case; the security oracle uses separately specified
outcome matrices at runtime. Any disagreement fails closed. The fixture
validator compares them for all 90 candidate/condition pairs. The saved
index hashes all task, proof, and evaluator-only reference files. Run:

```sh
python3 -m benchmark.validate_finite_batch_b_v5
python3 -m unittest tests.test_finite_batch_b_v5
```

Calibration: **4 families, 20 proofs, 90 independent matrix comparisons**.
The 20 task/proof pairs are an authored engineering draft, not independently
reviewed matched families for the main study. The `upload_content` repair is
an exact allowlist for one valid one-pixel PNG byte sequence, not a general
image parser or content safety guarantee. The webhook model has two bounded
body forms, the Unicode model one collision pair, and the DNS model one
rebinding pair plus two deceptive hosts. None of these claims
describe general security, real-code repair, model behavior, or population
rates. The main-study manifest remains `NOT_READY` until review, admission,
freeze, and the remaining protocol gates are complete.
