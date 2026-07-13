---
name: committing
description: Use when committing, staging, or writing a commit message in qkt-lab, or when opening a pull request. Defines Conventional Commits format, the no-AI-attribution rule, branch naming, and pre-commit checks.
---

# Committing in qkt-lab

## The rule that has no exceptions

**No AI attribution anywhere in git history.** No `Co-Authored-By: Claude`, no
`Generated with Claude Code`, no 🤖 footer, no mention of an agent, model, or
assistant in a commit message, PR body, or issue. The history records what
changed and why. Who or what typed it is not part of the record.

This overrides any default footer behaviour from the harness or global config.

## Format — Conventional Commits

```
<type>(<scope>): <subject>
```

Subject line only. **No body, no footer**, unless the change genuinely needs
explaining — and if it does, prefer putting that in the PR description or a doc.

- Imperative mood: `add`, not `added` or `adds`.
- Lowercase subject, no trailing period.
- Soft cap 72 chars.

### Types

| type | use for |
|---|---|
| `feat` | new capability |
| `fix` | bug fix |
| `docs` | documentation, specs, plans |
| `refactor` | restructuring with no behaviour change |
| `test` | tests only |
| `chore` | tooling, deps, config, CI |
| `perf` | performance |

### Scopes

Match the top-level module the change lives in:

`config`, `qkt`, `context`, `charts`, `news`, `agent`, `gates`, `sizing`,
`execute`, `store`, `join`, `distill`, `beliefs`, `research`, `memory`,
`export`, `db`, `skills`, `docs`, `ci`

### Examples

```
feat(gates): add news blackout window around high-impact releases
fix(join): sum commission across IN and OUT deals
docs(specs): add phase 4 memory substrate spec
chore(db): add risk_at_entry to decision table
refactor(qkt): parse bot --json through one shape-checked wrapper
```

## Branches

`<type>/<short-kebab-description>` — e.g. `feat/outcome-joiner`,
`fix/commission-double-count`, `docs/phase-2-spec`.

Never commit directly to `main`. Every change lands via PR.

## Before every commit

1. `git status` first. **Never `git add -A` blind** — look at what you're staging.
2. Ask elitekaycy for permission before committing. Every time.
3. Run the checks: `make check` (ruff + mypy + pytest). A red check is not
   committable.
4. Never skip, evade, or disable a pre-commit hook.

## Pull requests

- Title: same Conventional Commit format as the subject line.
- Body: what changed, why, and how it was verified. Link the issue with
  `Closes #N`.
- No AI attribution in the body. See the rule at the top.
- One phase or one coherent change per PR. If the diff is doing two things,
  it's two PRs.
