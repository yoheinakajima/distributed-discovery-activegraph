# Evidence-gap triage

This report classifies the original 13 substantive ActiveGraph findings. It does not modify canonical evidence or open per-finding issues.

## Counts

- A. Current primary-evidence gap: 0
- B. Superseded or historical non-primary run: 5
- C. Intentionally failed or preliminary run: 2
- D. Importer-policy mismatch: 6
- False-positive rate among current-evidence findings: 100.0%
- Recorded review time: 39 minutes

## Findings

### `20260720T200124Z_DD-001_6eb12861_f9bcf73ec7` / `run_missing_verifier`

- Study: `DD-001`
- Role: earlier passing 17-point run; superseded by the 21-point primary run
- Exposure: no direct claim-ledger exposure
- Classification: **B. Superseded or historical non-primary run**
- Verifier: `not present`
- Corruption test: `not present`
- Canonical action: Preserve immutable historical evidence; no source mutation.
- Importer action: Recognize explicit primary/superseded evidence roles.
- CI blocking: `false`

### `20260720T225701Z_DD-002_a12ba3e8_e29b1460ae` / `run_missing_verifier`

- Study: `DD-002`
- Role: explicit preliminary disclosure run
- Exposure: no direct claim-ledger exposure
- Classification: **C. Intentionally failed or preliminary run**
- Verifier: `results/verified/20260720T225848Z_DD-002_94607423_e29b1460ae/outputs/witness-verification.json`
- Corruption test: `not present`
- Canonical action: Preserve the explicitly preliminary run and its label.
- Importer action: Downgrade findings for explicitly preliminary or failed runs.
- CI blocking: `false`

### `20260721T022739Z_DD-001_358cb1eb_cd16846ba5` / `run_missing_corruption_test`

- Study: `DD-001`
- Role: current primary alignment-bound evidence
- Exposure: public claim ledger: DD-C-0037, DD-C-0038
- Classification: **D. Importer-policy mismatch**
- Verifier: `results/verified/20260721T022739Z_DD-001_358cb1eb_cd16846ba5/outputs/independent-verification.json`
- Corruption test: `results/verified/20260721T022739Z_DD-001_358cb1eb_cd16846ba5/outputs/independent-verification.json`
- Canonical action: No canonical change; the visible evidence already supports the role.
- Importer action: Scope requirements to the specific run and recognize validation/verifier artifacts.
- CI blocking: `false`

### `20260720T200447Z_DD-001_6eb12861_ba766d1eba` / `run_missing_verifier`

- Study: `DD-001`
- Role: current primary initial-grid evidence
- Exposure: public claim ledger: DD-C-0019, DD-C-0020, DD-C-0021, DD-C-0022, DD-C-0024, DD-C-0036, DD-C-0038
- Classification: **D. Importer-policy mismatch**
- Verifier: `results/verified/20260720T200447Z_DD-001_6eb12861_ba766d1eba/validation.json`
- Corruption test: `not present`
- Canonical action: No canonical change; the visible evidence already supports the role.
- Importer action: Scope requirements to the specific run and recognize validation/verifier artifacts.
- CI blocking: `false`

### `20260721T153110Z_DD-008A_637f2b94_06307caab4` / `run_missing_verifier`

- Study: `DD-008A`
- Role: earlier non-primary registration run; replaced by the clean primary run
- Exposure: no direct claim-ledger exposure
- Classification: **B. Superseded or historical non-primary run**
- Verifier: `results/verified/20260721T163030Z_DD-008A_8b70668b_06307caab4/validation.json`
- Corruption test: `not present`
- Canonical action: Preserve immutable historical evidence; no source mutation.
- Importer action: Recognize explicit primary/superseded evidence roles.
- CI blocking: `false`

### `20260722T044453Z_DD-015_34bc4379_33e1da478b` / `run_missing_verifier`

- Study: `DD-015`
- Role: current secondary threshold-two extension evidence
- Exposure: public claim ledger: DD-C-0082
- Classification: **D. Importer-policy mismatch**
- Verifier: `src/distributed_discovery/dynamic_attention/verification.py`
- Corruption test: `results/verified/20260722T044453Z_DD-015_34bc4379_33e1da478b/outputs/corruption-tests.json`
- Canonical action: No canonical change; the visible evidence already supports the role.
- Importer action: Scope requirements to the specific run and recognize validation/verifier artifacts.
- CI blocking: `false`

### `20260720T200245Z_DD-001_6eb12861_ba766d1eba` / `run_missing_verifier`

- Study: `DD-001`
- Role: earlier passing 21-point run; superseded by the figure-complete primary run
- Exposure: no direct claim-ledger exposure
- Classification: **B. Superseded or historical non-primary run**
- Verifier: `not present`
- Corruption test: `not present`
- Canonical action: Preserve immutable historical evidence; no source mutation.
- Importer action: Recognize explicit primary/superseded evidence roles.
- CI blocking: `false`

### `20260720T200124Z_DD-001_6eb12861_f9bcf73ec7` / `run_missing_corruption_test`

- Study: `DD-001`
- Role: earlier passing 17-point run; superseded by the 21-point primary run
- Exposure: no direct claim-ledger exposure
- Classification: **B. Superseded or historical non-primary run**
- Verifier: `not present`
- Corruption test: `not present`
- Canonical action: Preserve immutable historical evidence; no source mutation.
- Importer action: Recognize explicit primary/superseded evidence roles.
- CI blocking: `false`

### `20260720T200245Z_DD-001_6eb12861_ba766d1eba` / `run_missing_corruption_test`

- Study: `DD-001`
- Role: earlier passing 21-point run; superseded by the figure-complete primary run
- Exposure: no direct claim-ledger exposure
- Classification: **B. Superseded or historical non-primary run**
- Verifier: `not present`
- Corruption test: `not present`
- Canonical action: Preserve immutable historical evidence; no source mutation.
- Importer action: Recognize explicit primary/superseded evidence roles.
- CI blocking: `false`

### `20260720T200447Z_DD-001_6eb12861_ba766d1eba` / `run_missing_corruption_test`

- Study: `DD-001`
- Role: current primary initial-grid evidence; corruption requirement belongs to later milestones
- Exposure: public claim ledger: DD-C-0019, DD-C-0020, DD-C-0021, DD-C-0022, DD-C-0024, DD-C-0036, DD-C-0038
- Classification: **D. Importer-policy mismatch**
- Verifier: `results/verified/20260720T200447Z_DD-001_6eb12861_ba766d1eba/validation.json`
- Corruption test: `not present`
- Canonical action: No canonical change; the visible evidence already supports the role.
- Importer action: Scope requirements to the specific run and recognize validation/verifier artifacts.
- CI blocking: `false`

### `20260720T220911Z_DD-001_6822d4c6_40bf5b06a5` / `run_missing_corruption_test`

- Study: `DD-001`
- Role: explicit preliminary signature audit with superseded presentation key
- Exposure: no direct claim-ledger exposure
- Classification: **C. Intentionally failed or preliminary run**
- Verifier: `results/verified/20260720T220911Z_DD-001_6822d4c6_40bf5b06a5/outputs/certificate-verification.json`
- Corruption test: `not present`
- Canonical action: Preserve the explicitly preliminary run and its label.
- Importer action: Downgrade findings for explicitly preliminary or failed runs.
- CI blocking: `false`

### `20260720T223829Z_DD-001_b2cc23f4_5e16a90ad1` / `run_missing_corruption_test`

- Study: `DD-001`
- Role: current primary threshold evidence; study-wide text was misapplied per run
- Exposure: public claim ledger: DD-C-0026, DD-C-0027, DD-C-0028
- Classification: **D. Importer-policy mismatch**
- Verifier: `results/verified/20260720T223829Z_DD-001_b2cc23f4_5e16a90ad1/validation.json`
- Corruption test: `not present`
- Canonical action: No canonical change; the visible evidence already supports the role.
- Importer action: Scope requirements to the specific run and recognize validation/verifier artifacts.
- CI blocking: `false`

### `20260720T221139Z_DD-001_b1d8d431_40bf5b06a5` / `run_missing_corruption_test`

- Study: `DD-001`
- Role: current primary signature evidence
- Exposure: public claim ledger: DD-C-0023, DD-C-0024, DD-C-0025
- Classification: **D. Importer-policy mismatch**
- Verifier: `results/verified/20260720T221139Z_DD-001_b1d8d431_40bf5b06a5/outputs/certificate-verification.json`
- Corruption test: `results/verified/20260720T221139Z_DD-001_b1d8d431_40bf5b06a5/validation.json`
- Canonical action: No canonical change; the visible evidence already supports the role.
- Importer action: Scope requirements to the specific run and recognize validation/verifier artifacts.
- CI blocking: `false`
