# TTT-011 live model-probe evidence

This directory is populated by `.github/workflows/model-probes.yml`.

The workflow is intentionally separate from ordinary CI because it downloads and
executes the selected GGUF artifacts. It verifies artifact SHA-256 values before
inference, runs the common TTT-011 characterization battery, uploads the complete
evidence as a workflow artifact, and commits the JSON reports plus `SHA256SUMS`
back to the TTT-011 PR branch.

A merged TTT-011 admission must contain the generated `*-probe.json` files,
`probe-run.json`, and `SHA256SUMS`. This README alone is not evidence that the
live probes ran.