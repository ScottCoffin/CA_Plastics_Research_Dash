# Repository Agent Guidance

## Continuous roadmap execution

- Treat `.agent/TODO.md` as the canonical roadmap and `spec.md` Part B as the
  operating contract. Add-on task contracts live in `docs/add_on_spec.md`
  (A1: SPK/AT tasks) and `docs/add_on_spec_2.md` (A2: EM tasks); their
  conflicts and defaults are in `.agent/DECISIONS.md` and `.agent/QUESTIONS.md`.
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
- When delegation is authorized, use Luna task agents by default. Use a
  higher-intelligence executor only for an exceptional task whose difficulty
  or risk is documented before dispatch.
- Give every task agent a bounded context capsule: name the exact task,
  owned files, required contract sections, preserved interfaces, and
  verification commands. Instruct it to read only that context and any direct
  dependency it must inspect; do not send agents through broad repository or
  documentation intake for a narrow assignment.

Claude Code sessions: start with `CLAUDE.md`. It maps the Luna/Terra/Sol roles
onto Claude agents and lists the verified local commands and cheap read paths.

Read `.agent/README.md`, `.agent/HANDOFF.md`, and the selected task contract
before editing. Keep acceptance checks, full-suite verification, durable
handoffs, narrow commits, and failure visibility intact at every checkpoint.
