# Planning review and revisions

This document records the critique applied before publishing the implementation programme.

## Initial plan

The initial concept was:
1. generate synthetic military-console sessions;
2. use an eccentric small model such as Sprocket for personality/tactical variation;
3. fine-tune a more capable compact model;
4. use WorldTUI-like error/recovery training;
5. expose encoded enemy command traffic to the player.

## Review findings

### Risk: teacher hallucination becomes ground truth

If a creative model generates both command and console result, the student may learn nonexistent capabilities or fabricated success.

**Revision:** World Authority exclusively generates command acceptance, errors, state transitions, and observation truth. Teacher output is proposal/style only.

### Risk: choosing models before knowing the task

Hard-coding Sprocket/Qwen/WorldTUI early would bias tokenizer, context, tool syntax, training format, and runtime around unmeasured assumptions.

**Revision:** build contracts/evaluation first; select the model cast at TTT-011.

### Risk: prompt-only secrets

"Do not tell the player X" is easy to violate and difficult to score if secrets are only prose.

**Revision:** represent visibility/private state structurally and add leakage validators/evaluation.

### Risk: synthetic train/eval leakage

Random turn-level splits can place nearly identical worlds into training and evaluation.

**Revision:** split by scenario/world families and freeze separate handwritten/adversarial suites.

### Risk: fine-tuning away the interesting behaviour

A single canonical "good answer" corpus can collapse humour and spontaneity.

**Revision:** retain multiple accepted persona variants, record sampling provenance, score diversity/repetition separately from command competence, and compare persona-only/operational-only/joint ablations.

### Risk: confusing intentional irrationality with model failure

A villain can be reckless or obsessive while still using tools correctly.

**Revision:** encode irrational preferences in persona/objective policy; treat malformed commands, false state, and accidental leakage as mechanical failures.

### Risk: brittle terminal imitation

A literal framebuffer/ANSI representation would unnecessarily couple the project to presentation details.

**Revision:** canonical state/events stay semantic. Console/delta rendering is an interchangeable view inspired by WorldTUI.

### Risk: unsafe execution

A scripting-flavoured interface could accidentally become arbitrary shell execution.

**Revision:** use typed bounded command IR and sandbox any synthetic process execution; model text never becomes host shell by default.

### Risk: irreproducible expensive experiments

Remote teachers and GPU training can create untraceable corpora/checkpoints.

**Revision:** require run manifests, hashes, versions, seeds, split identities, budget/config admission, and preserved readback artifacts.

### Risk: fake tactical telegraphs

Independently generated player hints could promise attacks that were never ordered.

**Revision:** normal intercepts are rendered from authoritative dispatched command events; lies require explicit deception actions.

## Improved plan

The published programme therefore builds in this order:

1. reproducible repository foundation;
2. semantic schemas;
3. deterministic typed command system;
4. abstract world/scenario generator;
5. console/session/replay views;
6. creative teacher/persona subsystem in parallel;
7. provenance-valid corpus assembly;
8. grounded player intercept codec;
9. frozen evaluation;
10. student-visited corrective rollouts;
11. owner-approved model cast;
12. training/export machinery;
13. small pilot experiments and ablations;
14. closed-loop commander benchmark;
15. runtime/bridge contract;
16. release/admission evidence.

This ordering intentionally postpones expensive/model-specific work until success can be measured.
