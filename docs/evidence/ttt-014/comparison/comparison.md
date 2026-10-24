# TTT-014 closed-loop comparison

Three frozen 24-turn episodes per candidate; all actions can be authoritatively replayed.

| Variant | Objectives | Failure recovery | Schema valid | Critical violations | Repetition |
|---|---:|---:|---:|---:|---:|
| scripted | 1.000 | 1.000 | 1.000 | **0** | 0.000 |
| prompt-only | 0.000 | 0.000 | 0.000 | **0** | 1.000 |
| operational | 0.000 | 0.000 | 0.819 | **0** | 1.000 |
| persona | 0.000 | 0.000 | 0.000 | **0** | 0.472 |
| joint | 0.000 | 0.000 | 0.000 | **0** | 0.667 |
| joint+corrective | 0.000 | 0.000 | 0.708 | **0** | 0.856 |

- `scripted`: reference/control evidence only; no real-model runtime admission
- `prompt-only`: reject continued runtime integration: operational/character gate miss
- `operational`: reject continued runtime integration: operational/character gate miss
- `persona`: reject continued runtime integration: operational/character gate miss
- `joint`: reject continued runtime integration: operational/character gate miss
- `joint+corrective`: reject continued runtime integration: operational/character gate miss

Missing substantive comparisons: none.

Automated character proxies do not measure humour, surprise, or distinctiveness. Human ratings remain null.

Full turn-by-turn operational and persona differences are in candidate JSON files; wall time is separate from semantic hashes.
