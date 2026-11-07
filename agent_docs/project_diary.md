# Project Diary

## Decisions and Lessons

- 2026-11-06: S2.3 will be a separate deterministic labeling step rather than
  a change to the S2.2 normalized-work schema. Raw OpenAlex records are joined
  by `work_id` only to recover topic names; normalized works retain topic IDs.
- Candidate query and taxonomy configuration may drive provisional rules, but
  remain explicitly unpromoted and unvalidated. Missing topic/raw joins must be
  counted rather than dropping works.
- Specialized workflow roles attempted unsupported `gpt-6-luna`; explicit
  `gpt-5.6-luna` was also rejected by the active collaboration API. Ordinary
  workers were moved to the supported lower-cost `gpt-5.6-terra` fallback in
  that earlier interface. The current interface exposes the installed
  specialized roles again; route selection still controls whether to use them.
- 2026-11-06: Roadmap safety now attaches to an atomic task checkpoint rather
  than a fresh chat. Continuous Goal-mode execution may advance across tasks
  only after each task is independently verified, documented, committed, and
  pushed when configured.
