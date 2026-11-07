# Project Progress

## Goal

Complete the staged CA Plastics Research Atlas roadmap one dependency-satisfied
task per session.

## Overall Progress

S0 through S2.4 are complete. S2.4 adds the guarded daily OpenAlex works
workflow, typed rate-limit/budget deferral, and optional generated-output
commits. S3.1 is complete; S3.2 is the next unchecked dependency-satisfied
task.

## Current Position

`py -3.14 scripts/check_s3_1.py`, the full Python test suite, Ruff, build, and
`git diff --check` pass. No owner input is required for S3.1. OpenAlex query
promotion remains intentionally separate from this workflow.

## Next Milestone

Implement exactly S3.2: build the accessible mobile app shell and stub tabs,
loading the fixture and real site data, and stop before S3.3.
