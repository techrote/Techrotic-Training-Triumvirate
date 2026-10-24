# Optional-observation commander corpus-v4 data card

This corpus supports attempt-04 after attempt-03 failed independent development
rejection recovery. It is fresh synthetic training data, with no frozen response
or human rating copied into targets. It preserves the same native model, output
codec and registered three-epoch training recipe.

| Identity | Value |
|---|---|
| Semantic source | `f152cafc59bda5207b8cb1c5ef7d6d60133d1b41` |
| Curriculum version / seed | `3` / `938000` |
| Dataset SHA-256 | `028dfa357fd91e10e4aaa982deff583b4de0fae49e320e29df3a167de9822105` |
| Manifest file SHA-256 | `b09e1375b78476234c809ba3d36e1d10b3fb30577052377f61d6f3829674b918` |
| Source episode archive SHA-256 | `5dbcea3ad9612bc4f506ff32dc4bc548e3e7cc9e165f367878745d060031c35a` |
| Training shard SHA-256 | `1dd87e065119c854a9ea0dd927877491e5f504b026bb7b34dd4ca25a94593777` |
| Development shard SHA-256 | `69c838793e7995c8f536be93c57609064861ca8eeffad7860e7fc8c4f1ae3bc1` |
| Codec | `ttt-commander-wire-v2` |
| Local directory | `artifacts/ttt-017/corpus-v4` |

## Composition and coverage

The canonical assembler admitted all 168 episodes with zero quarantine and no
rejection reasons. There are 4,578 T1 command-and-communication examples, divided
by whole episode into 3,924 training rows and 654 development rows. The source
episodes retain environmental probes; probes are excluded from supervised labels.
`joint+corrective` names the registered training mix, not a separately collected
T3 learner-visited dataset.

| Training feature | Rows |
|---|---:|
| Request status target | 3,612 |
| Assign objective target | 312 |
| Single visible objective | 2,628 |
| No optional mission extension | 1,308 |
| Recent target-already-secured rejection | 24 |

Development has 602 status targets, 52 assignment targets, 438 single-objective
inputs, 218 inputs without a mission extension and four target-already-secured
rejection contexts. Status requests dominate both splits; successful scripted
demonstrations do not establish that a learned policy selects the right operation.

There are 112 single-objective and 56 dual-objective episodes, 84 two-unit and
84 three-unit worlds, and 42 mid-state starts. Initially secured objectives and
actual rejected assignments expose safe post-completion behavior. Optional
commander-private extensions, randomized generation offsets, changing/reopened
priorities, capability rejection and delayed stalls remain part of the corpus.
Every actual execution failure must have a later authoritative completion for the
same unit and target. Fully secured demonstrations request status, including after
an actual target-already-secured rejection. The validation manifest records 140
CAPABILITY_MISMATCH, 84 ENTITY_UNKNOWN and 28 PRECONDITION_FAILED feedback events.

Complexities one through five contribute 925, 925, 928, 901 and 899 examples.
The four template personas contribute 1,176, 1,050, 1,176 and 1,176 examples.
World Authority owns state, acceptance, hidden information, execution and results;
the demonstration policy sees only admitted observations and actual feedback.
Training/inference use the shared projection, without case-kind or evaluator labels.

## Splits and licensing

Whole episode indices divisible by seven go to development: 144 training episodes
and 24 development episodes. Seeds and episodes are disjoint; generator families
and deterministic style vocabulary overlap. The benchmark guard remains bound to
`22a93e8861e25d1b6b15fea298431b4023b28610884d1699d447cf8a85bb92aa` and all
reserved evaluation seeds are refused. Attempt-04 uses independent external
development seeds962000+ before any frozen readout.

All content comes from repository-authored scripts and local templates. No
model-generated teacher output, paid API, external corpus, human rating or actual
fine-tuned learner rollout enters the training data. Development failures informed
general coverage requirements; the new labels come from fresh authoritative worlds.

The disposition remains `LicenseRef-Project-Internal-Research`: owner-authorized
internal project research, redistribution permission ungranted pending owner
licence review. No new licence is granted here. The separately admitted LFM native
checkpoint retains its LFM Open License v1.0 and notices. No weights are published.

## Limitations

This is narrow English abstract-world research with scripted tactics and speech,
not representative gameplay or human conversation. Optional-field coverage does
not exhaust the admitted input space. Family overlap, fixed style templates,
few archetypes and lack of naturally learner-visited training states limit
generalization. Input coverage, corpus size, codec and training exposure are
confounded. String-based secrecy checks have limits. Loss, template adherence
and reload parity are insufficient evidence for operational or subjective quality.
Genuine blinded human review and actual Q4 qualification remain required.

The hashes identify actual local files. A card alone does not restore their bytes.
Earlier corpus-v3 and attempt-03 remain separately preserved historical evidence.
