# Eight additional finite mechanisms, batch C (engineering draft)

Batch C adds 40 C1–C5 task/proof rows over eight separate security mechanisms:
CSRF origin binding, nonce uniqueness, signature algorithm confusion,
deserialization type allowlisting, TLS hostname verification, stale key
acceptance after rotation, KDF salt separation, and environment-variable
allowlisting. Its validator checks **160 candidate/condition combinations**
against a separately coded reference matrix.

C3/C4 hide the observation required to distinguish the secure and insecure
cases; the resulting contradiction witness is finite and explicit. C5 uses a
secure candidate with a deliberately failing gate. The machine admission review
checks all 20 families together, but records human admission as missing.

These are synthetic finite languages, not real-code tasks or population rates.
They require independent threat-model review, leakage review, strong mutation
challenges, and human admission before any main schedule can use them.
