# Initial pilot data card

## Identity and intended use

Dataset: the benchmark-clean TTT-013E local pilot corpus generated on 24 October
2026 from source revision `11e70686b09a27cf7c784beaf8d7a46717b345a0`.
Its purpose is a small controlled operational/persona/corrective LoRA comparison
on the admitted native LFM checkpoint. It is not a representative corpus of
real game behaviour or human conversation.

- Dataset content SHA-256: `98fceb9b10b387a21fa8d711850653ff4edc06c9140c7f263bcb90fceacdb0a9`.
- Manifest file SHA-256: `861441cb7ac2d763d19cb539e4d50dd904496a6fc77cd3507d33416a7b295107`.
- Canonical source-episode archive SHA-256: `b94c4dc1d0883b13d8f0e10a2264ec847ebfe1640bef238a82b5154a7c2115bd`.
- Corpus seed: `750000`; split seed: `750001`; training seed: `24301`.
- Portable manifest, source archive and shards: `../ttt-013-execution/corpus/`.

## Composition and sources

The corpus has 36 admitted deterministic World Authority episodes, 252
supervised examples, 210 training examples and 42 development examples.

| Tier | Examples | Contribution |
|---|---:|---|
| T1 | 96 | Scripted high-level commands executed by the native authority |
| T2 | 96 | Accepted deterministic local style-template teacher enrichment |
| T3 | 60 | Scripted student-visited invalid/stale commands followed by authority-validated correction |

There are four persona identities with 63 examples each. Scenario complexities
one through five contribute 63, 63, 42, 42 and 42 examples. Every admitted example
contains a command and a communication before the mix-specific target projection.
The operational mix keeps commands, the persona mix keeps communications, joint
excludes corrective examples, and joint+corrective includes T3 recovery targets.

No Sprocket/Qwen/API-generated teacher text, external dataset, human rating or
game-derived trace contributed to this pilot. Model-generated training
contribution is **zero**. The T3 policy is a scripted student double; it is not
a claim of iterative collection from the fine-tuned LFM student. These limits
constrain conclusions about spontaneity and student-distribution correction.

## Validation and split policy

All episodes passed the existing TTT corpus schema, authority, target visibility,
licensing/provenance, protocol, exact/near deduplication and frozen-evaluation
guards. The manifest records zero quarantined episodes and zero rejection
reasons. Recovery contexts preserve 24 `ENTITY_UNKNOWN` and 12
`STALE_OBSERVATION` errors; rejected actions remain input context rather than
ordinary successful supervised targets.

Train/development assignment uses scenario families, rather than separating turns
from the same episode. The frozen TTT-009 guard is bound to benchmark hash
`22a93e8861e25d1b6b15fea298431b4023b28610884d1699d447cf8a85bb92aa`.
There are zero frozen-evaluation examples. The long-session benchmark derives
only from already reserved evaluation family/seed identities. Evaluation
responses, failures and human packets are excluded from this corpus.

Only commander-admitted observation/private context/persona and explicit recovery
feedback reach inputs. Targets contain student command/communication emissions;
World Authority owns acceptance, outcomes and hidden world state. The source
archive preserves authoritative episode records and provenance separately from
these training projections.

## Licensing and redistribution

All examples originate from repository-authored deterministic scripts and local
templates. Their recorded disposition is
`LicenseRef-Project-Internal-Research`: owner-authorized internal project research
training, with redistribution permission **ungranted pending owner licence
review**. The repository did not supply a blanket MIT/Apache licence at execution;
this programme does not invent one. No non-redistributable third-party training
corpus was copied into the repository.

The native LFM model remains subject to its separately recorded LFM Open License
v1.0 and notices. The existing TTT-011 model-cast admission records the project's
research-use disposition; downstream commercial use and model redistribution
must follow that source licence. Model licensing does not automatically grant
a licence for this project's corpus.

## Biases and limitations

The corpus is small, English, template-driven and focused on the abstract relay
scenario, typed commands, a few archetypes and four personas. The development
split tests held-out complexity families rather than broad tactical diversity.
T2 styles are deterministic phrasing; subjective humour or emergent personality
cannot be established from template membership. T3 immediate-error coverage is
narrow and does not replace broad learner-visited delayed-failure trajectories.

The abstract world has no low-level physics and does not establish CyberSand
performance. String-based secrecy checks cannot prove absence of paraphrased or
encoded disclosure. Development loss, training loss and export parity do not
establish command competence, character quality or runtime admission.
