"""
Pipeline for fetching GitHub repo data, scoring it, and writing to SQLite.
Run this script directly to refresh the database for a given org:

    python pipeline.py
"""

import logging
import os
import time

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

    logger.info("Fetching repos from GitHub API...")
    try:
        df = td.create_entire_repo_dataframe(org_name, HEADERS)
        rate_limit_remaining = td.get_rate_limit_remaining(HEADERS)
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

    # Pipeline-level event and metrics
    dd.send_event(
        title="repo_archiver.pipeline.run",
        text=f"Pipeline completed for org '{org_name}'",
        tags=org_tags + [f"repo_count:{len(df)}"],
    )
    dd.send_metric(
        "repo_archiver.pipeline.duration_seconds",
        duration,
        tags=org_tags,
    )
    dd.send_metric(
        "repo_archiver.api.rate_limit_remaining",
        rate_limit_remaining,
        tags=org_tags,
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
        "repo_archiver.repos.score.mean",
        round(float(score_col.mean()), 3),
        tags=org_tags,
    )
    dd.send_metric(
        "repo_archiver.repos.score.min",
        float(score_col.min()),
        tags=org_tags,
    )
    dd.send_metric(
        "repo_archiver.repos.score.max",
        float(score_col.max()),
        tags=org_tags,
    )

    # Per-repo scores — one time-series per repo, sent in a single
    # batched request so each series carries its own repo: tag.
    dd.send_metrics_batch([
        {
            "metric": "repo_archiver.repo.score",
            "points": row["overall_score"],
            "tags": org_tags + [f"repo:{row['name']}"],
        }
        for _, row in df.iterrows()
    ])

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
