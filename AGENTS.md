# Autonomous implementation contract

This file applies to every implementation issue in this repository.

## Mission

Build a reproducible, model-agnostic training system for compact NPC commander models. Preserve the hard separation between deterministic operational truth and creative/model-generated material.

## Required workflow

For every issue:

1. Start from current `main`; inspect the issue, linked PRs, and the current RAG docs before editing.
2. Read `docs/rag/00-index.md` and every document listed by the issue under **Required reading**.
3. Reconcile the issue against current repository state. Do not reimplement work already merged.
4. Implement only the issue scope, plus the minimum compatible refactors/tests required to make it correct.
5. Add or update deterministic automated tests. Any randomness used by tests or generators must accept an explicit seed.
6. Run the repository's documented local validation commands. Keep expensive training or external-model calls out of default CI.
7. Update RAG docs when implementation changes a public contract, schema, CLI, file format, architecture decision, or workflow.
8. Open a focused PR that links and closes the issue. Include scope, design decisions, tests, compatibility notes, and reproducibility details.
9. Self-review the PR diff against the issue acceptance criteria and RAG contracts. Correct problems before relying on external review.
10. Observe automated checks. Fix failures; do not hide, bypass, weaken, or delete a check merely to obtain green CI.
11. Once required automated checks are green, the PR is mergeable, there are no unresolved blocking review findings, and the branch is current enough to merge safely, merge the PR.
12. Verify the merge landed on `main` and the issue closed. Record any deliberately deferred follow-up as a new issue rather than silently leaving TODO scope.

If repository permissions or an external service prevent a required action, leave the PR in the most complete state possible and document the exact blocker. Do not claim completion or merge.

## Non-negotiable architecture rules

- **World Authority owns truth.** Model output never decides whether a command actually succeeded, what hidden state exists, or what the world became.
- **Creative Teacher is untrusted input.** Teacher text/tactics are proposals until schema, policy, and operational validators accept them.
- **Student Commander sees only its admitted observation surface.** Hidden world state and player-only state must not leak into student inputs or labels.
- **Player intercepts derive from real dispatched command events.** Cosmetic distortion may hide information; it must not invent tactical facts unless explicit deception is itself an authoritative action.
- **The command layer is typed and bounded.** Never implement arbitrary model-authored host shell/script execution as the battlefield command interface.
- **Replay matters.** Generated scenarios, episodes, splits, and evaluations must carry enough version/seed/hash information to reproduce or diagnose them.
- **Model choice remains configurable.** No programme issue may silently hard-code a particular teacher or student family unless the model-cast admission document explicitly selects it.

## Compute and network policy

Default CI must run without paid model APIs, heavyweight model downloads, GPUs, or long training jobs. Provide recorded/replay fixtures and small deterministic doubles.

No large corpus generation, paid API campaign, GPU training run, or model publication is authorized merely because code for it exists. Such execution requires the relevant issue to define an admitted budget/configuration and, where the programme says owner selection is required, that selection must be recorded first.

## Data and licensing

Every externally sourced model, dataset, generated-output source, or checkpoint used for a corpus/training run must have recorded provenance and an explicit compatibility/licensing disposition before its outputs enter an admitted dataset.

Never copy a third party's non-redistributable training corpus into this repository.

## Security

Treat model outputs, generated commands, filenames, scenario text, and imported corpora as untrusted. Validate structured data, constrain paths, and sandbox any process execution used by test/synthetic environments.

## Definition of done

An issue is done only when implementation, tests, documentation, PR, automated checks, and merge are all complete, unless the issue explicitly defines an earlier evidence-only stopping point.
