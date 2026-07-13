---
name: issue-flow
description: Use when creating, labeling, triaging, or closing GitHub issues in qkt-lab, or when deciding what to work on next. Defines the phase/spec/plan/issue lifecycle, the issue body format, and the label taxonomy.
---

# Issue flow in qkt-lab

## The lifecycle

Work moves through four artifacts, in order. Skipping one is how a project ends
up with code nobody can explain.

```
SPEC  →  PLAN  →  ISSUE  →  PR
```

| artifact | lives in | answers | written when |
|---|---|---|---|
| **spec** | `docs/specs/phase-N-<name>.md` | *what* and *why*, and how we'll know it worked | before any code for that phase |
| **plan** | `docs/plans/phase-N-<name>.md` | *how* — task breakdown, file-by-file | when the phase starts |
| **issue** | GitHub | the unit of work; tracks state | one per phase, plus one per discrete task |
| **PR** | GitHub | the change | `Closes #N` |

A phase issue is an umbrella. Its body links the spec and the plan and checkboxes
the tasks. Task issues link back to the phase issue.

**No AI attribution in any issue or PR body.** See the `committing` skill.

## Issue body format

```markdown
## Context
One paragraph. Why this exists. Link the spec.

## Scope
- [ ] concrete, checkable thing
- [ ] concrete, checkable thing

## Out of scope
What this deliberately does not do, so the PR doesn't sprawl.

## Acceptance
How we know it's done. Must be observable — a command that runs, a row that
appears, a number that matches. "It works" is not acceptance.

## Refs
Spec: docs/specs/phase-N-....md
Plan: docs/plans/phase-N-....md
Blocked by: #N
```

## Labels

**Type** (exactly one)
- `type:feat` — new capability
- `type:fix` — something is broken
- `type:docs` — spec, plan, README
- `type:chore` — tooling, CI, deps
- `type:spike` — time-boxed investigation whose output is a decision, not code

**Phase** (exactly one, for work items)
- `phase:0-spikes` `phase:1-loop` `phase:2-context` `phase:3-journal`
  `phase:4-memory` `phase:5-learning` `phase:6-proof`

**Area** (zero or more)
- `area:qkt` `area:gates` `area:store` `area:join` `area:memory`
  `area:research` `area:journal` `area:config` `area:ci`

**Status** (zero or one)
- `status:blocked` — cannot start; say what by
- `status:needs-decision` — waiting on elitekaycy
- `status:parked` — deliberately deferred; say why in a comment

**Risk** (use sparingly, and mean it)
- `risk:money` — touches order placement, sizing, or a gate. Held to a higher
  review bar. Never merged without a spike or a test that exercises the failure.
- `risk:invalidates-design` — if this comes back wrong, a phase gets rethought.

## Rules

- **A spike issue must state the kill condition.** "Passes if X, and if it fails
  we do Y." A spike with no kill condition is just work.
- **Every `risk:money` issue names its failure mode** in the body. Not "add a
  gate" but "without this, a proposal with no stop reaches the venue."
- **Close with evidence.** The closing comment shows the command and its output,
  or the row that appeared. Not "done".
- **Park, don't drop.** If we decide against something, it gets `status:parked`
  and a comment saying why. Silently closing loses the reasoning, and the
  reasoning is the expensive part.
- Phase issues close only when every task issue under them is closed and the
  spec's acceptance criteria are demonstrably met.

## Picking what's next

In order:
1. Anything `risk:money` that is open and unblocked.
2. The lowest-numbered open issue in the current phase.
3. Spikes for the *next* phase, if the current phase is blocked.

Do not start a phase whose spec isn't written.
