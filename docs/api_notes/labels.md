# S2.3 label-layer contract

The S2.3 label layer is local deterministic code, not an external API.  It
joins normalized `works.parquet` rows to raw OpenAlex work JSON by `work_id` so
topic IDs can recover display names and primary-topic names.  A normalized work
is retained when its raw row or a topic entry is absent; `docs/labels_qc.md`
counts both cases.

The ordered rules are exclusions first, then configured core terms, qualified
terms with an `any_context` match, and tier-2 chemicals.  Exclusions override
all inclusions.  `model_version=plastic-v2-candidate-rule-v1`,
`label_source=rule`, and nullable `confidence` make the owner-supplied
candidate status explicit; the module does not promote `plastic-v2-candidate`.

Run the fixture-safe CLI with:

```powershell
py -3.14 scripts/label_works.py
```

The acceptance check is:

```powershell
py -3.14 scripts/check_s2_3.py
```
