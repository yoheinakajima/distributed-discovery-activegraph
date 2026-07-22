# Schema drift

One schema-based compatibility change was required: treat the relationship registry as optional when the source snapshot predates it. No commit-specific branch was added.

## `63c235c2` → `8ac0700e`

Cause: real repository evolution; no commit-specific importer branch.

- `chapter`: added ['duplication_risk', 'maturity', 'missing_theorem_gate']; removed []; type changes {}
- `decision`: added ['admission_gate', 'decision']; removed []; type changes {}
- `roadmap_item`: added ['family_id', 'state']; removed []; type changes {}
- `theorem_family`: added ['central_question', 'editorial_disposition', 'family_id', 'likely_literature']; removed []; type changes {}

## `8ac0700e` → `a560bb77`

Cause: real repository evolution; no commit-specific importer branch.

- `lab`: added ['output_connected']; removed []; type changes {}
- `paper`: added []; removed []; type changes {'central_question': {'from': ['NoneType'], 'to': ['str']}, 'editorial_disposition': {'from': ['NoneType'], 'to': ['str']}}
- `research_program`: added ['program_id']; removed []; type changes {}

## `a560bb77` → `06523c8d`

Cause: real repository evolution; no commit-specific importer branch.

No attribute-field or value-type drift.
