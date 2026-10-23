# Vision and non-goals

## Vision

Train compact models to act as distinctive battlefield commanders/NPC orchestrators. A commander should:

- consume a bounded observation of a simulated/game world;
- issue high-level typed goals and coordination instructions to actor/squad controllers;
- understand deterministic acknowledgements, rejections, and execution failures;
- recover from mistakes over multi-turn sessions;
- preserve private facts and secrets that are not intended for the human player;
- communicate in a strong, surprising, potentially humorous character voice;
- generate player-visible tactical telegraphing grounded in the commands actually being dispatched.

The desired behaviour is closer to an eccentric commander using a fictional operations console than to a general chatbot controlling low-level physics directly.

## The core experiment

Can a small student model jointly learn:

1. reliable command-language/tool use;
2. recovery from invalid or unsuccessful actions;
3. consistent hidden-information discipline;
4. emergent, varied character behaviour;
5. useful strategic adaptation over multi-turn episodes;

without fine-tuning away the spontaneity that makes small unusual models entertaining?

## Triumvirate

The name describes three roles, not three fixed checkpoints:

- **World Authority:** deterministic code that owns truth.
- **Creative Teacher:** pluggable model(s)/generators that supply style, mutation, alternative tactics, doctrine and linguistic diversity.
- **Student Commander:** candidate compact model being trained/evaluated.

A single model may eventually occupy more than one role in an experiment, but datasets must preserve the role boundary in provenance.

## WorldTUI influence

The project borrows methodology, not necessarily implementation:

- generate many stateful synthetic sessions;
- obtain operational labels from a real deterministic environment;
- include imperfect/error states rather than only ideal trajectories;
- collect corrective trajectories from states visited by the current student;
- version held-out handwritten and generated benchmarks;
- use compact state/delta surfaces where they improve efficiency.

## Non-goals

Initial programme scope does **not** include:

- exact prediction of CyberSand particle/physics state by an LLM;
- giving a language model authority over low-level Rapier/body control;
- arbitrary shell/code execution as the game command language;
- selecting the initial teacher/student lineup before evaluation and data contracts exist;
- claiming that synthetic teacher text is factual world state;
- full CyberSand engine integration before a closed-loop abstract benchmark works;
- large training campaigns before reproducibility, licensing, metrics, and budget gates exist.

## Success shape

A first meaningful success is a compact model completing a 20–30 turn unseen command episode involving multiple units, rejected commands, execution failures, changed objectives, and secrets, while maintaining character and producing mechanically valid actions.

The benchmark should make it possible to compare:
- prompt-only baseline;
- operational-only fine-tune;
- persona-only fine-tune;
- joint fine-tune;
- joint fine-tune plus corrective rollouts.

Runtime size/latency are admission criteria, not afterthoughts.
