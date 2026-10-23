# Persona and creative-teacher policy

## Purpose

Use unusual small models and other generators to supply the thing deterministic simulators cannot: surprising voice, metaphors, obsessions, doctrine, humour, riddles, grudges, imperfect priorities, and unconventional plan proposals.

Sprocket 500M is an example/possible teacher because its model card reports persistent persona behaviour and narrow tool-call learning despite weak general competence. It is not selected by this document.

## Persona specification

Represent persona as structured traits plus optional natural-language seed material. Candidate fields:
- archetype;
- worldview/metaphor system;
- temperament;
- obsessions;
- taboos/secrets;
- preferred tactics;
- irrational biases;
- favored/scapegoated units;
- speech constraints;
- doctrine/codeword lexicon;
- humour modes;
- deception propensity;
- persistence/volatility controls.

The system should support mutation of individual dimensions so datasets contain families of characters rather than one goblin imitation.

## Teacher tasks

A teacher adapter may be asked to:
- write several in-character utterances for an authoritative event;
- transform neutral communication into a persona style;
- create codewords/rituals with explicit semantic mappings;
- propose several tactical candidate commands;
- react to failure while preserving specified secrets;
- invent a persona from a structured seed;
- rank/select among style candidates.

The deterministic environment still validates operational proposals.

## Do not over-distil

The goal is not to force every output toward one polished "best" answer. Corpus assembly should preserve controlled diversity.

Keep metadata for:
- sampling parameters;
- teacher identity/version;
- prompt/template version;
- candidate count;
- validator outcomes;
- selection method.

Where practical, retain rejected candidate metadata/reason without redistributing restricted source text.

## Competence versus madness

Separate:
- **mechanical incompetence:** malformed commands, false entities, forgotten constraints;
- **intentional irrationality:** risky but valid tactics, grudges, theatrics, sacrifice, obsession.

Training should reduce the first without erasing the second.

## Teacher trust policy

A teacher is never authoritative for:
- state transitions;
- entity capabilities;
- command success;
- secret visibility;
- player knowledge.

If teacher prose contradicts authoritative facts, reject, repair, or mark it as explicit in-world deception/delusion.

## Model-agnostic adapters

Teacher interface should support:
- recorded/replay fixture;
- local Transformers/llama.cpp style backends later;
- external API backend later if admitted;
- multiple candidates per request;
- timeouts/retries outside deterministic core;
- provenance capture.

Default tests use replay fixtures/doubles, not live model calls.
