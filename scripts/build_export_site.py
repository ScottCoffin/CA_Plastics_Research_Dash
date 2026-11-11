"""Build the S3.1 static-site data payloads."""

from __future__ import annotations

import argparse

from atlas.build.export_site import export_site


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--works", default="data/processed/normalized/works.parquet")
    parser.add_argument("--authors", default="data/processed/normalized/authors.parquet")
    parser.add_argument("--authorships", default="data/processed/normalized/authorships.parquet")
    parser.add_argument("--institutions", default="data/processed/normalized/institutions.parquet")
    parser.add_argument("--labels", default="data/processed/work_labels.parquet")
    parser.add_argument("--suppressions", default="curation/suppressions.csv")
    parser.add_argument("--work-overrides", default="curation/overrides_works.csv")
    parser.add_argument("--author-merges", default="curation/author_merges.csv")
    parser.add_argument("--work-relevance", default="curation/work_relevance.csv")
    parser.add_argument("--model-relevance", default="curation/work_relevance_model.csv")
    parser.add_argument("--author-metrics", default="data/processed/author_metrics.parquet")
    parser.add_argument("--output-dir", default="site/data")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    result = export_site(
        works_path=args.works,
        authors_path=args.authors,
        authorships_path=args.authorships,
        institutions_path=args.institutions,
        labels_path=args.labels,
        suppressions_path=args.suppressions,
        work_overrides_path=args.work_overrides,
        work_relevance_path=args.work_relevance,
        model_relevance_path=args.model_relevance,
        author_metrics_path=args.author_metrics,
        author_merges_path=args.author_merges,
        output_dir=args.output_dir,
        generated_at=args.generated_at,
    )
    print(
        f"S3.1 exported {result.counts['works']} works, {result.counts['authors']} authors, "
        f"and {result.counts['institutions']} institutions to {result.output_dir}"
    )
    print(f"Payload sizes: {result.metadata_path}")


if __name__ == "__main__":
    main()
