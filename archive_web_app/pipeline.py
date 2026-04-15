"""
Pipeline for fetching GitHub repo data, scoring it, and writing to SQLite.
Run this script directly to refresh the database for a given org:

    python pipeline.py
"""

import logging
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

import database as db
import datadog_utils as dd
import transform_data as td

load_dotenv()

HEADERS = {
    "Authorization": f"token {os.getenv('GITHUB_API_KEY')}"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("repo_archiver.pipeline")

ARCHIVE_SCORE_THRESHOLD = 0.8
RATE_LIMIT_THRESHOLD = 500


def run(org_name: str):
    """
    Fetch all repos for org_name, score them, and persist to SQLite.

    Args:
        org_name: GitHub organization name
    """
    start_time = time.time()
    logger.info("Pipeline started — org: %s", org_name)
    org_tags = [f"org:{org_name}"]

    db.init_db()
    prev_df = db.read_repos(org_name)

    logger.info("Fetching repos from GitHub API...")
    try:
        df, api_calls_made = td.create_entire_repo_dataframe(org_name, HEADERS)
        rate_limit_remaining = td.get_rate_limit_remaining(HEADERS)
        api_calls_made += 1  # rate limit check call
        logger.info(
            "GitHub API fetch complete — repos fetched: %d, "
            "rate limit remaining: %d",
            len(df),
            rate_limit_remaining,
        )

        score_col = df["overall_score"]
        logger.info(
            "Scoring complete — repos scored: %d, "
            "score distribution: min=%.1f, mean=%.2f, max=%.1f",
            len(df),
            score_col.min(),
            score_col.mean(),
            score_col.max(),
        )

        logger.info(
            "Writing results to SQLite — rows to write: %d", len(df)
        )
        db.write_repos(org_name, df)
        logger.info(
            "DB write successful — %d rows written for org '%s'",
            len(df),
            org_name,
        )
    except Exception as exc:
        logger.error("Pipeline failed for org '%s': %s", org_name, exc)
        dd.send_metric(
            "repo_archiver.pipeline.failed", 1, tags=org_tags
        )
        raise

    duration = round(time.time() - start_time, 2)
    archive_candidates = int(
        (score_col >= ARCHIVE_SCORE_THRESHOLD).sum()
    )

    # Compute how many repos changed score since the last run.
    if not prev_df.empty:
        merged = df[["name", "overall_score"]].merge(
            prev_df[["name", "overall_score"]].rename(
                columns={"overall_score": "prev_score"}
            ),
            on="name",
            how="inner",
        )
        repos_score_changed = int(
            (merged["overall_score"] != merged["prev_score"]).sum()
        )
    else:
        repos_score_changed = 0

    # Pipeline-level event and metrics
    dd.send_event(
        title="repo_archiver.pipeline.run",
        text=f"Pipeline completed for org '{org_name}'",
        tags=org_tags + [
            f"repo_count:{len(df)}",
            f"duration_seconds:{duration}",
        ],
    )
    dd.send_metric(
        "repo_archiver.pipeline.repos_score_changed",
        repos_score_changed,
        tags=org_tags,
    )

    # GitHub API metrics
    dd.send_metric(
        "repo_archiver.github.api_calls_made",
        api_calls_made,
        tags=org_tags,
    )
    if rate_limit_remaining < RATE_LIMIT_THRESHOLD:
        dd.send_event(
            title="repo_archiver.github.rate_limit_exhausted",
            text=(
                f"GitHub API rate limit below {RATE_LIMIT_THRESHOLD} "
                f"for org '{org_name}'"
            ),
            tags=org_tags + [f"rate_limit_remaining:{rate_limit_remaining}"],
        )

    # Org-level aggregate metrics
    dd.send_metric(
        "repo_archiver.repos.total", len(df), tags=org_tags
    )
    dd.send_metric(
        "repo_archiver.repos.archive_candidates",
        archive_candidates,
        tags=org_tags,
    )
    dd.send_metric(
        "repo_archiver.repos.already_archived",
        int(df["is_archived"].sum()),
        tags=org_tags,
    )
    dd.send_metric(
        "repo_archiver.repos.forked",
        int(df["is_fork"].sum()),
        tags=org_tags,
    )

    # Per-repo metrics — score + raw criteria values, one series per
    # repo per metric, sent in a single batched request.
    per_repo_metrics = []
    for _, row in df.iterrows():
        repo_tags = org_tags + [f"repo:{row['name']}"]
        last_push = row.get("last_push_time")
        days_since_push = (
            (datetime.now(timezone.utc) - datetime.strptime(
                last_push, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)).days
            if last_push else None
        )
        per_repo_metrics += [
            {"metric": "repo_archiver.repo.score",
             "points": row["overall_score"], "tags": repo_tags},
            {"metric": "repo_archiver.repo.open_issues",
             "points": row["num_open_issues"], "tags": repo_tags},
            {"metric": "repo_archiver.repo.open_prs",
             "points": row["num_open_pull_requests"], "tags": repo_tags},
            {"metric": "repo_archiver.repo.stars",
             "points": row["num_star_watchers"], "tags": repo_tags},
            {"metric": "repo_archiver.repo.forks",
             "points": row["num_forks"], "tags": repo_tags},
        ]
        if days_since_push is not None:
            per_repo_metrics.append(
                {"metric": "repo_archiver.repo.days_since_push",
                 "points": days_since_push, "tags": repo_tags}
            )
    dd.send_metrics_batch(per_repo_metrics)

    logger.info(
        "Datadog metrics emitted — org: %s, repos: %d, "
        "candidates: %d, duration: %.2fs",
        org_name,
        len(df),
        archive_candidates,
        duration,
    )

    return df


if __name__ == "__main__":
    ORG_NAME = "plotly"
    run(ORG_NAME)
