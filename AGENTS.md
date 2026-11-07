# Repository Agent Guidance

## Continuous roadmap execution

- Treat `.agent/TODO.md` as the canonical roadmap and `spec.md` Part B as the
  operating contract.
- Complete one dependency-satisfied roadmap task at a time as an atomic
  checkpoint. Do not mix implementation or commits from adjacent tasks.
- A single chat or Goal-mode run may complete multiple checkpoints. After a
  checkpoint is verified, documented, committed, and pushed when configured,
  re-read the current roadmap and continue with the next eligible task.
- Preserve unrelated and pre-existing work. Inspect Git status at every task
  boundary and stage only the current checkpoint's files.
- Pause only for an owner decision that blocks every eligible path, a required
  permission, a genuine technical blocker, an explicit user pause, or roadmap
  completion. Record skipped owner-gated work and continue another eligible
  branch when the dependency graph permits it.
- Follow the route selected by the user-level workflow instructions. Light is
  the default; use Medium or Heavy only when the user selects it.

Read `.agent/README.md`, `.agent/HANDOFF.md`, and the selected task contract
before editing. Keep acceptance checks, full-suite verification, durable
handoffs, narrow commits, and failure visibility intact at every checkpoint.
