# Frozen source provenance

This directory keeps small, version-controlled copies of the source manifests required to audit the local data build. The corresponding raw files remain excluded from Git because they total approximately 1.98 GB in compressed form.

| File | Local source | Records | Purpose |
|---|---|---:|---|
| `aemo_history_manifest.csv` | `data/raw/history_manifest.csv` | 216 | FY2020–FY2025 regional-demand, price and SCADA archive URLs, sizes and SHA-256 hashes |
| `aemo_pilot_manifest.csv` | `data/raw/manifest.csv` | 47 | Two pilot windows used for parser and daylight-saving validation |
| `reference_manifest.csv` | `data/external/reference_manifest.csv` | 2 | AEMO DUID registration archive and frozen OpenElectricity facility capture |

Task 11 verified every local file against its recorded byte size and SHA-256 hash. When local data are rebuilt or an official source vintage changes, update the source manifest through the pipeline and then deliberately refresh this frozen copy; do not edit checksums by hand.
