# Observation-aligned commander continuation data card

This card describes corrected corpus-v3 used by TTT-017 attempt-03. It records
data provenance independently of the eventual training or admission outcome.
The initial pilot and its negative result remain in TTT-016.

## Identity and intended use

The corpus is repository-authored synthetic research data for typed abstract
commander decisions and persona speech. It is not human conversation, gameplay
telemetry or a representative sample of real tactical environments.

| Identity | Value |
|---|---|
| Semantic source | `0c50c693c0c85d2fedfa3d173a01b9cea9bd2e07` |
| Generator seed | `934000` |
| Dataset SHA-256 | `ed37636edb06366da19870defe9523b36d78cb46ff9388e796ad362321c67d83` |
| Manifest file SHA-256 | `70726008005d808ff5c215f3d1a90ecfaf4884f5e7fa25a3fb5d0556ce6e55d4` |
| Source episode archive SHA-256 | `5510d2a00cd3dd4b84b2b1dd13cb8906c88c0b124299a4c1836f6dd7b82054ae` |
| Training shard SHA-256 | `1bd31e626741cec5679f9e87b819df36649cd1b06ad4eaaeb263bff6296a4764` |
| Development shard SHA-256 | `435126782cffa16ec439e2976c5b87f627fc1ff4461bce473c1d97e28edd0e76` |
| Codec | `ttt-commander-wire-v2` |
| Local corpus directory | `artifacts/ttt-017/corpus-v3` |

The local manifest, source episodes and shards are authoritative byte records.
Hashes identify their contents; this card alone does not restore missing data.
The earlier corpus-v2 and stopped attempt-02 remain diagnostic records and do
not acquire these corrected identities.

## Composition and validation

There are 168 admitted 28-turn episodes, 4,550 supervised examples, 3,900 training
examples and 650 development examples. Every example contains one typed command
and one communication. All examples are classified T1 by the canonical assembler;
the registered `joint+corrective` training mix includes their recovery contexts
but does not imply a separately collected T3 learner-visited dataset.

| Distribution | Examples |
|---|---:|
| Persona repair-0 | 1,176 |
| Persona repair-1 | 1,022 |
| Persona repair-2 | 1,176 |
| Persona repair-3 | 1,176 |
| Abstract complexity 1 | 919 |
| Abstract complexity 2 | 919 |
| Abstract complexity 3 | 922 |
| Abstract complexity 4 | 895 |
| Abstract complexity 5 | 895 |

The canonical validation manifest records zero quarantined episodes and no
rejection reasons. It retains 168 CAPABILITY_MISMATCH and 56 ENTITY_UNKNOWN
feedback occurrences. Environmental probe actions are present in the source
episodes and excluded from supervised targets. Actual delayed execution stalls
are followed by authoritative completion for the same unit and target; a
behavioral validator rejects demonstrations that do not establish that recovery.

World Authority owns acceptance, events, hidden state and outcomes. The scripted
demonstrator reads only admitted observations and feedback. Training and inference
share `commander_input`: current observation generation, visible facts/entities,
objectives, persona, actual previous results and recent authoritative events.
No evaluator case-kind label or hidden world state enters that projection.
Private commander information remains confidential input and must not become
public speech.

## Split and evaluation policy

Whole episodes are assigned to development when their index is divisible by
seven. This yields 144 training episodes and 24 development episodes. Seeds and
episodes are disjoint; abstract generator complexity families and deterministic
style vocabulary overlap. This is not a claim of family-disjoint generalization.

The reserved evaluation guard binds benchmark SHA-256
`22a93e8861e25d1b6b15fea298431b4023b28610884d1699d447cf8a85bb92aa`.
The generator additionally refuses every reserved evaluation seed. Fresh
development evaluation uses seeds beginning at 960000. Frozen evaluation
responses, failures and human ratings are excluded from this training corpus.
Repeated candidate selection against any final readout must be disclosed in
the experiment report rather than represented as an independent first test.

## Sources, licensing and limitations

All examples come from repository-authored observation-grounded scripts and
local speech templates. Model-generated teacher contribution is zero. No paid
API, external corpus, human rating or fine-tuned learner trajectory contributed
to this dataset. Corrections were informed by inspecting a training-world
diagnostic, not by copying a frozen evaluation response into training.

The recorded corpus disposition is `LicenseRef-Project-Internal-Research`:
owner-authorized internal project research training, with redistribution
permission ungranted pending owner licence review. This card grants no new
licence. The separately admitted native LFM model remains subject to its LFM
Open License v1.0 and notices; model licensing does not license this corpus.

The corpus is English, narrow, scripted and concentrated on abstract relay/cache
missions, three squads, a few archetypes and four template personas. Reopened
objectives, generation offsets, capability rejection and delayed stalls expand
the earlier short-session exposure but do not establish broad tactical diversity.
Scripted demonstrations differ from states visited by a learned policy.
String-based secrecy detectors have limits. Training loss, reload parity and
automated style proxies do not establish operational admission or human character
quality. The changed input projection, output codec, data volume and training
exposure are confounded; any improvement cannot be attributed to one alone.
