# V15 bounded target retransformation infrastructure — dormant, NOT submitted

Runtime source148290b,Python3.12.14,branch work/llm-upgrade-20261022.
ZIP `../solution-v15-smearing1.zip`,78709bytes,54flat files.
SHA `06ddee151c8af6abb8c08cb92621826890112063e79e449a19585d50a0929532`.
Original requirements unchanged,no added dependencies/pretrained weights.

Explicit target_smearing=true adds fitting-only held-out log-residual factor,
bounded[.8,1.25],minimum20calibration rows,matching selected iterations. History
recipes require actually enabled history in the calibration model. Ineligible/
invalid moments retain factor1; the identity inverse preserves exact dtype/values.
No default portfolio insertion yet; classification/numeric optimizer defaults
unchanged. All254unique checks PASS unchanged-source (171.007s), plus23repeated
exact-unpacked. Includes actual matching-floor, fullrefit, outer-label isolation
and insufficient-history CSV parity checks. Evidence here. Public3cut screen now
completed: active latest cut RMSE39.051678→40.160774 (worse), older cuts exact
control CSV parity. Gate FAIL, no default/portfolio promotion. See v15 results.

V11 remains the qualified score-improving release. This archive is NOT yet a
better ML model; no official upload authorized. Earlier artifacts immutable.
