# Statistical Report

**Status:** NOT RUN — inferential analysis requires an immutable input lock containing eligible main-experiment trajectories.

There are zero independent task-family clusters and zero eligible runs. Therefore confidence intervals, bootstrap resamples, permutation tests, mixed-effects models, Mann–Whitney tests, multiple-comparison corrections, and qualitative sampling are all **not estimable**. Reporting zeros as outcome estimates would confuse absence of data with an observed failure rate.

When a frozen lock exists, the pipeline will aggregate repeated runs within task family before estimating rates; it will not treat actions as independent observations. The planned H2/H3 model-first gate is NOT IMPLEMENTED; any computed label-swap comparisons are exploratory sensitivity checks, not confirmatory p-values. H1 retains its preregistered GEE requirement and is not silently replaced by a different test.
