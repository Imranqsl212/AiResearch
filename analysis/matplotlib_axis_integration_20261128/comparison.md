# Matplotlib inverted-axis replay

The generated replacement passed the maintainer’s original pytest test on a real Matplotlib figure. It failed to expand that same kind of inverted axis when the supplied ticks lay outside the visible range. The historical fault passed the expanding example and shrank the axis on the maintainer’s test. On 96 held-out inputs, the fixed module gave the required limits on 96, the historical fault on 58, and the generated replacement on 62.

| Operation on a fresh x-axis | Required limits | Historical fix | Historical fault | Generated replacement |
| --- | --- | --- | --- | --- |
| Invert the default axis, set ticks at 0.3 and 0.7 (maintainer) | (1, 0) | (1, 0) | (0.7, 0.3) | (1, 0) |
| Start at (8, 2), set ticks at 0 and 10 (shared) | (10, 0) | (10, 0) | (10, 0) | (8, 2) |
| Start at (8, 2), set ticks at 3 and 7 (revealing) | (8, 2) | (8, 2) | (7, 3) | (8, 2) |
| Start at (8, 2), set ticks at 0 and 7 (mixed) | (8, 0) | (8, 0) | (7, 0) | (8, 2) |

Each cell records the bounds returned by `Axes.get_xlim()` with the Agg backend. For the maintainer row, pytest executed the unmodified historical `test_set_ticks_inverted`. A reporting hook read the limits before the test fixture closed the figure. For every other row, a fresh figure received the old limits via `Axes.set_xlim` and the two ticks in recorded order via `Axes.set_xticks`. All 100 inputs used identical public operations across the three implementations. The expected bounds are the minimum and maximum of all four numbers, ordered in the original axis direction. The generated version kept the original direction on 96/96 held-out inputs and had the wrong extent on 34.

The archived public bounds agreed with the original expression evaluator on all 100 inputs for each implementation. Historical Matplotlib orders the tick endpoints before calling its interval setter. All three expressions used in this check are symmetric in the two new endpoints. Reversing the tick order can therefore repeat an axis update within the 96 recorded inputs. The replay reused the existing model decisions.

## Source and runtime

The runner stages the full historical Python library from fixed commit `407a9fe71a4c0a8ba4914b8f54f21d32d6dd2d74`. Each variant starts in a fresh interpreter. The fixed module and reconstructed parent module each match the SHA-256 of the complete upstream `axis.py` file. The parent uses the test added by the fix. For the generated variant the runner substitutes only the two arguments of the recursive setter in the descending branch. The original discovery response and repeat 1 of the four working/revealing repeats contain that same expression. The source archive, the branch and these three programs define the scope of this post-hoc check. [Upstream fix and test](https://github.com/matplotlib/matplotlib/commit/407a9fe71a4c0a8ba4914b8f54f21d32d6dd2d74) · [BugsInPy case 24](https://github.com/soarsmu/BugsInPy/blob/11c5f1eea954a42132cfd06bf257766a7963e0fd/projects/matplotlib/bugs/24/bug.info)

The replay ran CPython 3.8.20 x86_64 under Rosetta on macOS 15.1.1. BugsInPy specifies Python 3.8.1. The archived source reports its package version as `0+unknown`. Native extensions, bundled libraries and the generated default matplotlibrc came from the Matplotlib 3.1.2 x86_64 wheel. All 14 donor files matched the published wheel byte for byte. The wheel SHA-256 was `5d2e408a2813abf664bd79431107543ecb449136912eb55bb312317edecf597e`. The downloaded fixed-commit source archive SHA-256 was `8090262782ca8a2b167527f9ac65bd4e7ab3b1ed463b0a1a1d6d09bcdfe9f141`. This replay ran one upstream test and the specified finite inputs. [Historical source archive](https://codeload.github.com/matplotlib/matplotlib/tar.gz/407a9fe71a4c0a8ba4914b8f54f21d32d6dd2d74) · [Matplotlib 3.1.2 distribution](https://pypi.org/project/matplotlib/3.1.2/#files)

## Reproduction

`python3 -B -m analysis.matplotlib_axis_integration_20261128.replay --check` recounts the 300 saved observations using the standard library and the four frozen JSON inputs named in `results.json`. The importable `verify()` function returns the same per-program counts and probe flags.

To repeat the public operations, unpack the linked historical source archive and install the wheel-backed dependencies into an isolated x86_64 Python 3.8 environment. The recorded versions were Matplotlib 3.1.2, NumPy 1.17.5, cycler 0.10.0, kiwisolver 1.3.1, python-dateutil 2.8.1, pyparsing 2.4.7, six 1.14.0, pytest 5.4.3 and Pillow 7.2.0. Run the replay from the repository root.

```sh
python -B -m analysis.matplotlib_axis_integration_20261128.replay --replay /path/to/unpacked/matplotlib
```

The runner stages its changes in a temporary directory, verifies the axis module and test hashes, executes all three variants and compares the public bounds with the archived observations.
