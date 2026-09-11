# Domain docs

## Layout

This repository uses a single-context layout:

- CONTEXT.md at the repository root: domain vocabulary and context.
- docs/adr/: architecture decision records.

## Before exploring

Read CONTEXT.md and any ADRs relevant to the area being explored.

If these files are absent, proceed silently. The domain-modeling skill
creates them lazily when terms or decisions are resolved.

## Vocabulary

Use the terms defined in CONTEXT.md when naming domain concepts in
issues, proposals, hypotheses, and tests.

If a needed concept is missing, reconsider whether it fits the domain
or note the gap for domain-modeling.

## Decision conflicts

If a proposal contradicts an existing ADR, identify the ADR and explain
why the decision should be reconsidered.
