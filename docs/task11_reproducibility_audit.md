# Reproducibility audit

## Decision

**Reproducibility review passed.** The frozen data contracts, main estimates, robustness results, figures, executed notebooks and report are internally consistent and reproducible in a newly created repository-local `.venv`. The study remains a conditional-association analysis and does not acquire a causal interpretation through reproducibility alone.

No package was installed into system Python. The system interpreter was used only to create an isolated `.venv`; every project dependency and research command ran inside that environment.

## Clean-environment result

The existing project environment was moved intact to a temporary backup. A new `.venv` was created from scratch and installed only from `requirements.txt` using the official Python Package Index. After every fresh-environment gate passed, the obsolete 811 MB backup was moved to the user's Trash as a recoverable cleanup; it is no longer inside the project or `gjx/tmp`.

The fresh environment passed:

- `pip check`, with no broken requirements;
- all 36 repository tests;
- compilation of every `src/` module;
- execution of all three notebooks with 13 of 13 code cells executed and zero error outputs;
- the 42-check automated reproducibility audit, including full source SHA-256 verification; and
- a fresh rerun of the 22-model fixed-effect build, whose core coefficient, contrast and headline CSV files were byte-identical to the pre-audit artifacts.

The environment audit found that several declared support packages were absent. Recreating `.venv` from `requirements.txt` corrected that mismatch. `nbformat` is now also declared directly because the audit module imports it.

## Source and data integrity

Every locally retained immutable source matched both the recorded byte size and SHA-256 hash:

| Manifest | Records | Result |
|---|---:|---|
| FY2020–FY2025 AEMO history | 216 | Pass |
| Pilot dispatch archives | 47 | Pass |
| AEMO/OpenElectricity reference captures | 2 | Pass |

The full history contains 72 months for each of the regional-demand, price and SCADA table families. Its compressed files total 1,982,469,829 bytes. Small frozen manifest copies are now tracked under `provenance/`, while the large source files remain excluded from Git.

All four monthly partition contracts passed: 72 files spanning 2019-07 through 2025-06, 3,156,480 five-minute region intervals and 263,040 hourly region observations. The regenerated generation-demand panel, final price panel and model frame were each byte-identical to their pre-audit versions.

The frozen analysis snapshot was reproduced exactly:

- 263,040 five-region model-frame rows;
- 210,399 four-region headline observations;
- 209,928 dynamic observations;
- 314 AEST ISO-week clusters;
- p99.9 exposure cap 2.7891799386467846; and
- 211 headline rows above that cap.

## Estimate and inference reproducibility

The complete estimation chain was rerun: core fixed effects, distributed lags, heterogeneity, Logit/Probit and the compact headline summary. All five core result files were byte-identical to the audit baseline.

The complete robustness chain was also rerun: 38 robustness models, 42 heterogeneity comparisons, Holm corrections, the fixed-seed 399-replication AEST-week score-multiplier audit, leverage diagnostics, UNKNOWN-fuel diagnostics and compact result summaries. All seven audited robustness result files were byte-identical to the baseline.

The reproduced headline estimates per 10 percentage-point increase in the capped wind-plus-utility-solar share are:

| Outcome | Estimate | Clustered SE |
|---|---:|---:|
| `asinh(RRP)` | -0.2701236461 | 0.0125084191 |
| RRP level (AUD/MWh) | -11.8020494182 | 0.8679344094 |
| Any negative five-minute price | +0.0357689998 | 0.0013774835 |
| Intrahour RRP SD level (AUD/MWh) | -5.0251887222 | 0.6837490564 |

These numbers agree with the rounded values in both READMEs, both data READMEs, the executed final notebook, the Markdown report source and the DOCX report.

## Reader-artifact audit

All six generated figures were byte-identical after regeneration. The three tracked README figures are also byte-identical to their generated counterparts.

The DOCX rebuild differs only in ZIP-container metadata. After extraction, every OOXML member was identical. The rebuilt document rendered to the same ten page PNG files as the baseline. Every page was visually inspected: no clipping, overlap, table overflow, missing glyphs or broken page furniture was found. The document accessibility audit reported zero high-, medium- or low-severity findings.

All three notebooks were executed again with the fresh `.venv` kernel and their outputs were saved in place. The final-results notebook preserves the main tables, heterogeneity, robustness, figures and four explicit snapshot assertions.

## Issues found and corrected

1. **Incomplete declared environment.** Three declared packages were absent from `.venv`. A new `.venv` was created from `requirements.txt`, and the complete dependency set now passes `pip check`.
2. **Stale descriptive missingness table.** `price_panel_missingness.csv` predated the corrected five-minute −50 and −100 threshold fields. Rerunning the descriptive pipeline added both zero-missingness rows. No estimate changed.
3. **Fresh-clone reader gap.** All output CSVs were ignored even though the executed final notebook reads compact result tables. `.gitignore` now retains `outputs/tables/*.csv`; large data and generated figures remain excluded.
4. **Untracked source provenance.** Frozen copies of the three source manifests are now stored in `provenance/` so a reviewer can inspect exact URLs, vintages, sizes and hashes without the 2 GB local data tree.
5. **Incorrect licence wording.** Both READMEs previously referred to an included licence although no `LICENSE` file exists. They now state the legally accurate current position without selecting a licence on the author's behalf.

## Remaining limitations

- A fresh clone does not contain the 1.98 GB compressed AEMO history or derived Parquet panels. Full reconstruction requires network access, storage and materially more runtime than the compact result audit.
- The OpenElectricity facility export is dynamic. The local capture is frozen and hashed, but reproducing the exact fuel crosswalk requires retaining that vintage rather than silently substituting the current endpoint response.
- `requirements.txt` constrains direct dependencies but is not a platform-independent transitive lockfile. This audit verifies a fresh macOS arm64 / Python 3.13 installation; it does not promise byte-identical dependency resolution indefinitely on every platform.
- Full-sample unpenalised quantile regressions remain transparently unestimated under the bounded computation design.
- The data and code are reproducible, but the observational design remains exposed to region-specific simultaneous shocks. Results are conditional associations, not causal effects.
- No open-source licence is currently granted. The author should choose a licence separately before inviting code reuse.

## Reproduction command

The reusable audit entry point is:

```bash
.venv/bin/python -m src.reproducibility_audit --root . --full-checksums
```

Without `--full-checksums`, the same 42 contracts run while source files are checked by existence and recorded byte size rather than being re-hashed.
