# Contributing to supplier-scorecard

Thanks for considering a contribution.

`supplier-scorecard` is an explainable procurement decision engine. Changes should preserve three properties: deterministic behavior, auditable scoring, and explicit policy decisions.

## Before opening a pull request

1. Open or reference an issue when the change affects scoring semantics, public JSON fields, CLI behavior, category profiles, or policy gates.
2. Keep changes narrowly scoped. Avoid combining refactors with behavioral changes.
3. Add or update tests for every behavior change.
4. Preserve backward compatibility unless the change is explicitly documented as a breaking change.

## Local development

Requirements: Python 3.11+.

```bash
git clone https://github.com/yigitcan-ozturk/supplier-scorecard.git
cd supplier-scorecard
python -m pip install -e .
python -m unittest discover -s tests -v
```

Validate the distribution before submitting packaging changes:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

## Contribution boundaries

Good contributions include:

- bug fixes with regression tests;
- clearer decision explanations without changing hidden semantics;
- additional validation for malformed procurement inputs;
- documentation and examples that make existing behavior easier to understand;
- deliberately scoped extensions to profiles, policy gates, exports, or integration contracts.

Please avoid:

- opaque or non-deterministic scoring logic;
- silent changes to weights, thresholds, or public JSON contracts;
- technical-compliance inference inside this repository — engineering compliance belongs to `bidlint`;
- automatic supplier approval that bypasses explicit policy gates.

## Pull requests

A strong pull request explains:

- what problem is being solved;
- whether public behavior changes;
- which tests prove the change;
- whether the JSON/CLI/package contract is affected;
- any migration or compatibility considerations.

All pull requests should keep CI green on the supported Python matrix.
