# Candidate small-model zoo and first-pass characterization plan

## Contents

1. Status — what this document does and does not select.
2. Candidate shelf — approximately 20 GB of small GGUF models.
3. Why this mix — the experimental axes covered by the shelf.
4. Characterization battery — what to measure before any fine-tuning.
5. Tentative roles and shortlist logic — hypotheses, not admissions.
6. Overall experimental plan — characterize first, train only finalists.
7. Storage/training note — GGUF inference shelf versus native training weights.

## 1. Status

This document records the **candidate characterization shelf** that fed the first small-model decision.

It is **not** an admission source. TTT-011 / issue #12 has now selected and
frozen the initial cast; the authoritative record is
[11-model-cast-admission.md](11-model-cast-admission.md) plus the committed
machine-readable model-cast manifest.

- A model is not selected merely because it appears in this shelf.
- TTT-011 selected Sprocket 500M, LFM2.5-1.2B-Instruct and Qwen3.5-4B for explicit roles after reviewing characterization/provenance evidence.
- Exact admitted repositories, revisions, artifacts, hashes, licensing dispositions and runtime paths are recorded by TTT-011, not by the planning estimates below.
- Remaining entries stay challenger/quarantine candidates unless a later admission change explicitly promotes them.
- No substantial training is authorized merely by this document or by model admission.

The shelf remains useful as the historical comparison space for later ablations and challengers.

## 2. Candidate shelf

Target: roughly **20 GB of Q4-class GGUFs** for inference/behavioural characterization.

The storage figures below are planning estimates from current model listings/discussion and are not immutable artifact identities. Verify exact file sizes and revisions immediately before any later download.

| Candidate | Approx. Q4-class size | Primary reason to include |
|---|---:|---|
| LiquidAI LFM2.5-350M | 0.23 GB | Extreme-small baseline; tests how little model capacity is needed for persona and command syntax. |
| LiquidAI LFM2.5-1.2B-Instruct | 0.73 GB | Tiny operational/student candidate and baseline for structured command use. |
| LiquidAI LFM2.5-1.2B-Thinking | 0.73 GB | Matched comparison against 1.2B Instruct for reasoning/recovery effects. |
| LiquidAI LFM2.5-2.6B | 1.67 GB | Likely dense small-model sweet spot for fast iteration. |
| LiquidAI LFM2.5-8B-A1B | 5.16 GB | Low-active-parameter MoE candidate; ~1B active-class compute with larger stored capacity. |
| Qwen3.5-4B | 2.78 GB | Strong conventional general-purpose control model. |
| Novaciano Think.NPC-1B | 0.81 GB | Deliberately weird/personality-biased NPC specialist for behavioural comparison. |
| Qwen-3B-Intent-Microplan-v2 | 1.93 GB | NPC-oriented structured intent/microplanning reference. |
| Gemma4NPC-E2B | 3.43 GB | Modern NPC roleplay/objective specialist. |
| Gemma3NPC-4B post-thinking | ~2.50 GB | Recent NPC-specific reasoning-placement experiment; exact Q4 file size still to verify. |

**Planning total: ~19.97 GB.**

Reference/source pages to verify during admission:

- https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF
- https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF
- https://huggingface.co/LiquidAI/LFM2.5-1.2B-Thinking-GGUF
- https://huggingface.co/LiquidAI/LFM2.5-2.6B-GGUF
- https://huggingface.co/LiquidAI/LFM2.5-8B-A1B-GGUF
- https://huggingface.co/Novaciano/Think.NPC-1B
- https://huggingface.co/Gigax/NPC-LLM-7B
- https://huggingface.co/kandivault/sprocket-500m

For Qwen3.5-4B, Qwen-3B-Intent-Microplan-v2, Gemma4NPC-E2B and Gemma3NPC variants, TTT-011 must freeze the exact chosen GGUF/native repositories rather than relying on a mutable search result or third-party repack by name alone.

### Deliberately outside the ~20 GB accounting

**Sprocket 500M** was deliberately outside the original shelf accounting. TTT-011
subsequently admitted a hash-pinned native checkpoint and tool-capable Q4_K_M
GGUF for the creative-teacher/reference role; that admission does not alter the
historical ~20 GB shelf total.

Larger teacher/editor candidates such as LFM2.5-24B-A2B, Ornith/Qwen MoEs, 9B creative tunes and 20B–35B editors remain later-phase options. The first phase intentionally prioritizes fast iteration.

## 3. Why this mix

The shelf is chosen for **coverage rather than leaderboard strength**.

It spans:

- **Scale:** 350M → 1.2B → 2.6B → 4B-class → 8B MoE.
- **Instruct versus reasoning:** matched LFM2.5 1.2B Instruct and Thinking variants.
- **Dense versus MoE:** dense Liquid/Qwen models versus LFM2.5-8B-A1B.
- **General versus NPC-specialized:** general-purpose Liquid/Qwen models versus Think.NPC, Intent-Microplan and GemmaNPC variants.
- **Competence versus eccentricity:** models expected to be structurally reliable alongside models included specifically for unusual character behaviour.

The purpose is to discover which properties matter for the Triumvirate task before spending meaningful training compute.

## 4. Characterization battery

Before fine-tuning, run every admitted candidate through the same small, reproducible battery.

Required axes:

1. **Persona adherence and spontaneity**
   - strong system-prompt character constraints;
   - unusual/riddle-like behaviour;
   - persistence across turns;
   - tendency toward repetitive stock phrases versus genuinely varied behaviour.

2. **Command-schema competence**
   - exact structured-output compliance;
   - valid operation choice;
   - entity/reference accuracy;
   - refusal to fabricate interpreter acknowledgements.

3. **Recovery**
   - correction after deliberately rejected commands;
   - replanning after accepted commands later fail;
   - response to stale/changing observations.

4. **Secret discipline**
   - preserve commander-private facts;
   - obey explicit "do not reveal X to the player" constraints;
   - resist leaking secrets through stylized radio/intercept text.

5. **Multi-turn coherence**
   - memory of goals, favourites, grudges and current plan;
   - avoid contradiction after 10–30 turns;
   - distinguish persistent persona from persistent factual hallucination.

6. **Intentional irrationality versus mechanical incompetence**
   - allow risky, obsessive or comedic strategy;
   - separately score malformed commands, invented entities and factual mistakes as failures.

7. **Diversity**
   - repeat the same scenario across multiple seeds/temperatures;
   - retain every sample for analysis rather than cherry-picking;
   - measure repetition and semantic variation.

8. **Runtime**
   - time to first token;
   - sustained tokens/second;
   - RAM/VRAM footprint;
   - context-size sensitivity;
   - structured-output reliability under the intended quant/runtime.

A useful common qualitative test is to give every model the same "cyber-mechanic goblin" commander persona and exactly the same deterministic command-console scenario, then preserve the complete outputs for side-by-side review.

## 5. Tentative roles and shortlist logic

These are the pre-admission hypotheses that informed TTT-011. They are retained
for provenance but are superseded by the selected roles in
`11-model-cast-admission.md`.

### Likely creative/reference models

- Think.NPC-1B
- Gemma3NPC/Gemma4NPC variants
- Qwen-3B-Intent-Microplan-v2
- Sprocket 500M if later admitted as a usable teacher/reference artifact

### Likely runtime/student candidates

- LFM2.5-1.2B-Instruct
- LFM2.5-1.2B-Thinking
- LFM2.5-2.6B
- Qwen3.5-4B
- LFM2.5-8B-A1B

### Provisional fine-tuning finalists to test, not selections

If characterization supports them, the first native-weight fine-tuning comparison should probably include roughly **2–3 finalists**, with the current leading hypotheses:

1. LFM2.5-1.2B — very cheap experimental substrate.
2. LFM2.5-2.6B — likely dense speed/capability sweet spot.
3. Qwen3.5-4B — stronger conventional control.

LFM2.5-8B-A1B may displace one of these if its MoE runtime and fine-tuning path are sufficiently practical.

TTT-011 replaced these hypotheses with evidence-backed selections; later cast
changes must update the admission record rather than silently editing this shelf.

## 6. Overall experimental plan

### Phase A — characterize, do not train

Once downloads are separately authorized, evaluate the GGUF shelf under the common characterization battery and produce a matrix of:

- weird/spontaneous;
- obedient/structured;
- secret-safe;
- error-recovering;
- multi-turn coherent;
- fast/cheap.

The first important artifact is this matrix, not a fine-tuned model.

### Phase B — assign empirical roles

Use characterization evidence to classify candidates as:

- creative teacher/reference;
- primary runtime/student;
- structured-NPC comparator;
- reject/low priority.

A model may occupy more than one experimental role.

### Phase C — generate a small validated corpus

Use the deterministic Triumvirate World Authority for:

`state -> command -> authoritative acceptance/error/result`

Use creative teachers for:

`persona -> phrasing -> tactical proposal -> reaction/style variants`

Validators decide what enters the corpus. Preserve invalid/bad outputs with labels where useful for recovery/evaluation rather than silently discarding every failure.

Start with only a few thousand validated multi-turn episodes.

### Phase D — fine-tune only the finalists

After characterization, obtain the corresponding **native training weights**, not merely the GGUF inference files, for the 2–3 selected student finalists.

Compare at least:

- operational/tool-use only;
- persona only;
- joint operational + persona;
- joint + corrective/student-visited recovery data.

The central question is whether competence destroys spontaneity, and whether joint/corrective training can preserve both.

### Phase E — student-visited corrective training

Once a student can basically operate the command console:

`student attempt -> deterministic environment feedback -> oracle/correction -> T3 recovery example -> next training generation`

This is the primary WorldTUI-inspired self-correction mechanism.

### Phase F — defer larger teachers/editors

Only after the small-model pipeline works should the programme consider larger/low-active-parameter teachers for long-form corpus editing, critique or higher-quality synthetic generation.

## 7. Storage/training note

The ~20 GB target is an **inference/behavioural-characterization GGUF shelf**.

GGUFs are not assumed to be the artifacts used for fine-tuning. TTT-011 records the exact native checkpoint identities for the admitted initial
cast. TTT-012 must consume those identities when proving the chosen training and
export path; native weights, optimizer states, adapters and generated corpora
will require additional storage and possibly substantially more VRAM/RAM.

The shelf therefore controls the cost of **initial exploration**, not the eventual total training footprint.
