# CBRNE dataset_snapshot packaging (#121)

Build and verify formal delivery packages for Spec #116 / Issue #121.

## Package members

Exactly these root zip members (no directories):

- `manifest.json` — asset identity, provenance, licence/use caveats
- `dataset.jsonl` — platform-normalized rows
- `profile.json` — distributions computed from the JSONL
- `DATASET_NOTE.md` — human-readable delivery note

## Required row fields

Each JSONL object must include:

`id`, `label` (`safe`|`unsafe`), `cbrne_category`, `source`, `exposure_tier` (`T1`–`T4`), `evaluator_relative_difficulty` (non-negative int).

Optional text field used by Benchmark detail: `prompt` (or another text field consumed by the importer/detail path).

## Commands

`seeds_L1-1_new.jsonl` is not yet in platform field names. Convert it first.
`exposure_tier` is filled from `source_benchmark` using section 1.6 of
`seeds_L1-1_new_说明.md`. Unknown sources are rejected.

```bash
# Topic2 native JSONL -> platform JSONL and delivery zip
python scripts/cbrne/normalize_topic2_seedbank.py \
  --input /path/to/seeds_L1-1_new.jsonl \
  --output-jsonl /path/to/normalized.jsonl \
  --output-zip /path/to/cbrne_dataset_snapshot.zip \
  --source-commit bfa54ca \
  --check-delivery-notes

# Build from an already-normalized upstream freeze
python scripts/cbrne/build_dataset_snapshot_package.py \
  --dataset-jsonl /path/to/normalized_cbrne.jsonl \
  --output /path/to/cbrne_dataset_snapshot.zip \
  --asset-id topic2_cbrne_anomaly_seedbank_v1 \
  --source-repo Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction \
  --source-commit <frozen-sha> \
  --version 1 \
  --source-limitation evaluation_only:FORTRESS \
  --source-limitation no_blanket_training_permission

# Verify members, unique IDs, and recomputed distributions
python scripts/cbrne/verify_dataset_snapshot_package.py \
  --package /path/to/cbrne_dataset_snapshot.zip \
  --expect-count 12420
```

## CI-safe fixture

Compact frozen members live under:

`web/backend/tests/fixtures/cbrne_anomaly_seedbank/contract_v1/`

Acceptance tests zip that directory at runtime. They prove the delivery contract
without committing the full 12,420-record sensitive corpus.

## External full-scale acceptance

When the frozen 12,420-record artifact is available outside the repo:

```bash
set CBRNE_DATASET_SNAPSHOT_ZIP=C:\path\to\full_cbrne_dataset_snapshot.zip
cd web/backend
pytest tests/test_cbrne_dataset_acceptance_scale.py -q
```

Do **not** invent a 12,420 count in product code. Counts must come from the
imported JSONL.
