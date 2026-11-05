# Lessons (newest first; append-only)

## 2026-11-05 — Bootstrap environment
- GNU Make is not on PATH, but Rtools provides
  `C:\rtools45\usr\bin\make.exe`; direct Python equivalents also work.
- Do not rely on an ambient `PYTHONPATH` in acceptance checks. Pytest now gets
  `src` from `pyproject.toml`, so a clean `make test` imports the package.
- `gh` 2.89.0 is installed, so S0.2 can inspect and trigger GitHub Actions after
  repository authentication and permissions are confirmed.
