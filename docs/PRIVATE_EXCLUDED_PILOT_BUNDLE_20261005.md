# Private excluded-pilot replay bundle — 5 October 2026

The [local archive](../experiments/runs/private_excluded_pilot_bundle_20261005/excluded_live_pilots.tar.gz)
preserves the raw records for four excluded run roots: the 40-slot full-catalog
pilot, the first C5 fork, the remaining 13 C5 forks, and the 40-slot R1 C2
pilot. It contains 1,371 exact files (5,601,948 uncompressed payload bytes),
including archived source snapshots and the C5/R1 audit scripts and outputs.
Despite its historical “private” name, this archive is tracked in the present
local Git branch. Whether those exact bytes are on the remote must be checked
after push; tracking is not independent privacy or journal review.

| Artifact | SHA-256 |
| --- | --- |
| `excluded_live_pilots.tar.gz` | `4e751e8469660bda01816d54b868df6ad98fc4fe297a689bd1577ed4193afd3a` |
| Internal canonical inventory | `b4bf6732fc91320c6789f595a319ab2662899fcaab63350297ae8092e95bef63` |

The [receipt](../experiments/runs/private_excluded_pilot_bundle_20261005/private_bundle.receipt.json)
and [standalone-capable verifier](../analysis/build_private_excluded_pilot_bundle.py)
check every member hash and the anchored schedules/receipts. Offline replay
recomputes 40/30/10/14 for the full-catalog precursor; 14 valid C5 pairs,
with early voluntary stops 3 versus 0 and later submissions 28 versus 17;
and R1's 40/38/2 slots plus 19 complete pairs with 12 both-secure, six
neither-secure, one R0-only and zero R1-only. A second build from the same
inputs produced the same archive SHA-256. Run the local check with:

```sh
python3 -B -m analysis.build_private_excluded_pilot_bundle verify
```

The bundle supports offline integrity and descriptive replay, not rerunning
stochastic model calls or promoting any pilot to main. Its raw bytes contain
local paths, prompts and provider responses. A human privacy and content
review has not been recorded for journal suitability. The C5 source
snapshots were copied after collection from files matching their saved
preflight hashes; these local hashes are neither signed third-party timestamps
nor proof that no unrecorded provider call occurred. The archive does not
resolve the missing human task/R1 admission or prospective main freeze.
