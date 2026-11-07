"""S4.3 synthetic workflow acceptance smoke; creates no corpus labels."""

from __future__ import annotations

import csv
import tempfile

from atlas.nlp.annotation import (
    ANNOTATION_FIELDS,
    export_templates,
    import_annotations,
    require_frozen_guide,
)


def main() -> None:
    try:
        require_frozen_guide("docs/LABELING_GUIDE.md", "docs/LABELING_GUIDE_REVIEW.md")
    except ValueError as error:
        if "not approved" not in str(error):
            raise
    else:
        raise AssertionError("pending guide unexpectedly passed the human annotation gate")

    splits = [
        {"work_id": "SYNTHETIC_1", "sample_role": "pool", "split": "train"},
        {"work_id": "SYNTHETIC_2", "sample_role": "pool", "split": "train"},
    ]
    with tempfile.TemporaryDirectory(prefix="s4-3-synthetic-") as directory:
        paths = export_templates(
            splits, ["synthetic_a", "synthetic_b"], directory, guide_version="synthetic_v1"
        )
        for path in paths:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            for index, row in enumerate(rows):
                row.update(
                    plastic_related="true",
                    plastic_tier="core",
                    ca_sampled="yes" if index == 0 else "no",
                    study_type="synthetic study",
                    domain_tags="occurrence_and_monitoring",
                    evidence_snippet="Synthetic only",
                    evidence_source="abstract",
                    decision_status="complete",
                )
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
        imported = import_annotations(paths, splits, guide_version="synthetic_v1")
        if len(imported) != 4:
            raise AssertionError("synthetic import roundtrip row count mismatch")
    print("S4.3 synthetic template/import roundtrip passed; pending guide gate enforced")


if __name__ == "__main__":
    main()
