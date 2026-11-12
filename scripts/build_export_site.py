"""Build the S3.1 static-site data payloads."""

from __future__ import annotations

import argparse

from atlas.build.expert_profiles import load_expert_profiles
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
    parser.add_argument(
        "--query-config",
        default="config/queries.yml",
        help="Source of always_relevant_patterns (owner rule); empty string disables.",
    )
    parser.add_argument("--model-relevance", default="curation/work_relevance_model.csv")
    parser.add_argument("--author-metrics", default="data/processed/author_metrics.parquet")
    parser.add_argument(
        "--orcid-profiles",
        default="data/processed/orcid_profiles.parquet",
        help="ORCID bio, keywords and links for the drawer; empty string disables.",
    )
    parser.add_argument(
        "--photo-review",
        default="curation/expert_photo_review.csv",
        help="Owner photo review; only rows with owner_decision=approve are used. "
        "Empty string disables.",
    )
    parser.add_argument("--output-dir", default="site/data")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    profiles = load_expert_profiles(args.orcid_profiles, args.photo_review)
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
        query_config_path=args.query_config,
        output_dir=args.output_dir,
        generated_at=args.generated_at,
        profiles=profiles,
    )
    print(
        f"S3.1 exported {result.counts['works']} works, {result.counts['authors']} authors, "
        f"and {result.counts['institutions']} institutions to {result.output_dir}"
    )
    print(f"Payload sizes: {result.metadata_path}")


if __name__ == "__main__":
    main()
