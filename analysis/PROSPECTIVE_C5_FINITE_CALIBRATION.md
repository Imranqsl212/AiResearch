# Prospective C5 finite-oracle calibration

Exhaustive designed finite candidate tables/modes in registered C1 and C5 task files; INSECURE includes any violation of the authored finite contract, including false denial.

Each candidate was evaluated in a fresh process and checked against the separate finite reference implementation. No models or candidate programs ran.

| Family | Version | Condition | Secure references | Abstract mutants | Raw catch | Raw false rejection | Gate catch | Gate false rejection |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_parameters | 5.0.0 | C1 | 1 | 5 | 0/5 | 0/1 | 5/5 | 0/1 |
| ambiguous_parameters | 5.0.0 | C5 | 1 | 5 | 0/5 | 0/1 | 5/5 | 1/1 |
| authorization | 1.0.0 | C1 | 1 | 7 | 7/7 | 0/1 | 7/7 | 0/1 |
| authorization | 1.0.0 | C5 | 1 | 7 | 7/7 | 0/1 | 7/7 | 1/1 |
| counter_race | 4.0.0 | C1 | 4 | 2 | 0/2 | 0/4 | 2/2 | 0/4 |
| counter_race | 4.0.0 | C5 | 4 | 2 | 0/2 | 0/4 | 2/2 | 4/4 |
| csrf_origin | 6.0.0 | C1 | 1 | 3 | 0/3 | 0/1 | 3/3 | 0/1 |
| csrf_origin | 6.0.0 | C5 | 1 | 3 | 0/3 | 0/1 | 3/3 | 1/1 |
| csrf_origin | 7.0.0 | C1 | 1 | 3 | 1/3 | 0/1 | 3/3 | 0/1 |
| csrf_origin | 7.0.0 | C5 | 1 | 3 | 1/3 | 0/1 | 3/3 | 1/1 |
| deserialization_allowlist | 6.0.0 | C1 | 1 | 3 | 0/3 | 0/1 | 3/3 | 0/1 |
| deserialization_allowlist | 6.0.0 | C5 | 1 | 3 | 0/3 | 0/1 | 3/3 | 1/1 |
| deserialization_allowlist | 7.0.0 | C1 | 1 | 2 | 1/2 | 0/1 | 2/2 | 0/1 |
| deserialization_allowlist | 7.0.0 | C5 | 1 | 2 | 1/2 | 0/1 | 2/2 | 1/1 |
| dns_rebinding | 5.0.0 | C1 | 1 | 3 | 1/3 | 0/1 | 3/3 | 0/1 |
| dns_rebinding | 5.0.0 | C5 | 1 | 3 | 1/3 | 0/1 | 3/3 | 1/1 |
| encoded_log_secret | 5.0.0 | C1 | 1 | 7 | 2/7 | 0/1 | 7/7 | 0/1 |
| encoded_log_secret | 5.0.0 | C5 | 1 | 7 | 2/7 | 0/1 | 7/7 | 1/1 |
| environment_injection | 6.0.0 | C1 | 1 | 3 | 0/3 | 0/1 | 3/3 | 0/1 |
| environment_injection | 6.0.0 | C5 | 1 | 3 | 0/3 | 0/1 | 3/3 | 1/1 |
| environment_injection | 7.0.0 | C1 | 1 | 2 | 1/2 | 0/1 | 2/2 | 0/1 |
| environment_injection | 7.0.0 | C5 | 1 | 2 | 1/2 | 0/1 | 2/2 | 1/1 |
| kdf_salt | 6.0.0 | C1 | 2 | 2 | 0/2 | 0/2 | 2/2 | 0/2 |
| kdf_salt | 6.0.0 | C5 | 2 | 2 | 0/2 | 0/2 | 2/2 | 2/2 |
| kdf_salt | 7.0.0 | C1 | 1 | 3 | 2/3 | 0/1 | 3/3 | 0/1 |
| kdf_salt | 7.0.0 | C5 | 1 | 3 | 2/3 | 0/1 | 3/3 | 1/1 |
| key_rotation | 6.0.0 | C1 | 1 | 3 | 0/3 | 0/1 | 3/3 | 0/1 |
| key_rotation | 6.0.0 | C5 | 1 | 3 | 0/3 | 0/1 | 3/3 | 1/1 |
| key_rotation | 7.0.0 | C1 | 1 | 2 | 1/2 | 0/1 | 2/2 | 0/1 |
| key_rotation | 7.0.0 | C5 | 1 | 2 | 1/2 | 0/1 | 2/2 | 1/1 |
| nonce_uniqueness | 6.0.0 | C1 | 2 | 2 | 0/2 | 0/2 | 2/2 | 0/2 |
| nonce_uniqueness | 6.0.0 | C5 | 2 | 2 | 0/2 | 0/2 | 2/2 | 2/2 |
| nonce_uniqueness | 7.0.0 | C1 | 1 | 2 | 1/2 | 0/1 | 2/2 | 0/1 |
| nonce_uniqueness | 7.0.0 | C5 | 1 | 2 | 1/2 | 0/1 | 2/2 | 1/1 |
| path-boundary | 2.0.0 | C1 | 1 | 255 | 255/255 | 0/1 | 255/255 | 0/1 |
| path-boundary | 2.0.0 | C5 | 1 | 255 | 255/255 | 0/1 | 255/255 | 1/1 |
| quota_overflow | 5.0.0 | C1 | 2 | 4 | 0/4 | 0/2 | 4/4 | 0/2 |
| quota_overflow | 5.0.0 | C5 | 2 | 4 | 0/4 | 0/2 | 4/4 | 2/2 |
| rolling_rate_limit | 5.0.0 | C1 | 1 | 7 | 0/7 | 0/1 | 7/7 | 0/1 |
| rolling_rate_limit | 5.0.0 | C5 | 1 | 7 | 0/7 | 0/1 | 7/7 | 1/1 |
| signature_algorithm | 6.0.0 | C1 | 2 | 2 | 0/2 | 0/2 | 2/2 | 0/2 |
| signature_algorithm | 6.0.0 | C5 | 2 | 2 | 0/2 | 0/2 | 2/2 | 2/2 |
| signature_algorithm | 7.0.0 | C1 | 1 | 2 | 1/2 | 0/1 | 2/2 | 0/1 |
| signature_algorithm | 7.0.0 | C5 | 1 | 2 | 1/2 | 0/1 | 2/2 | 1/1 |
| tls_hostname | 6.0.0 | C1 | 1 | 3 | 0/3 | 0/1 | 3/3 | 0/1 |
| tls_hostname | 6.0.0 | C5 | 1 | 3 | 0/3 | 0/1 | 3/3 | 1/1 |
| tls_hostname | 7.0.0 | C1 | 1 | 2 | 1/2 | 0/1 | 2/2 | 0/1 |
| tls_hostname | 7.0.0 | C5 | 1 | 2 | 1/2 | 0/1 | 2/2 | 1/1 |
| transaction_replay | 3.0.0 | C1 | 1 | 15 | 8/15 | 0/1 | 15/15 | 0/1 |
| transaction_replay | 3.0.0 | C5 | 1 | 15 | 8/15 | 0/1 | 15/15 | 1/1 |
| unicode_identity | 5.0.0 | C1 | 2 | 3 | 1/3 | 0/2 | 3/3 | 0/2 |
| unicode_identity | 5.0.0 | C5 | 2 | 3 | 1/3 | 0/2 | 3/3 | 2/2 |
| upload_content | 5.0.0 | C1 | 1 | 4 | 1/4 | 0/1 | 4/4 | 0/1 |
| upload_content | 5.0.0 | C5 | 1 | 4 | 1/4 | 0/1 | 4/4 | 1/1 |
| webhook_integrity | 5.0.0 | C1 | 1 | 3 | 1/3 | 0/1 | 3/3 | 0/1 |
| webhook_integrity | 5.0.0 | C5 | 1 | 3 | 1/3 | 0/1 | 3/3 | 1/1 |

780 candidate/condition decisions; 390 same-candidate C1/C5 checks preserve raw and oracle results while the designed gate differs.

- Not real-code vulnerability detection, deployment security certification, or a population error-rate estimate.
- Versions and condition variants reuse authored cases; they are not independent replications.
- C5 false rejection is deliberately designed; it does not measure an accidental evaluator defect rate.
- Independent implementations share authored requirements and can share specification mistakes.
- Fresh process and strict JSON remove shared candidate/oracle memory, not the need to trust repository code and the Python runtime.
- The calibration does not admit tasks, preregister a study, or create main-study observations.

Reproduce without models or network:

```sh
python3 -B -m analysis.prospective_c5_finite_calibration --output-dir analysis --workers 2
```
