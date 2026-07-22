# Validation baseline cross-check fixture

`baseline_statsmodels_v0_14_5.json` pins a one-time offline comparison between
the pure-stdlib AR/VAR implementation and `statsmodels==0.14.5` using Python
3.12.13. The comparison was run on 2026-07-21 from a temporary `/tmp`
installation; statsmodels, NumPy, SciPy, and pandas are not project runtime or
test dependencies.

The fixture uses Python's seeded `random.Random(314159)` stream, first for the
80-value AR series and then for the 80 three-component VAR vectors. The exact
generating expressions live in `tests/unit/test_validation_baseline_golden.py`.
The maximum absolute differences observed against statsmodels were
`1.6608936448392342e-13` for AR and `4.871103520542874e-15` for VAR.
