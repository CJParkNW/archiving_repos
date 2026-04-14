"""
Pipeline for fetching GitHub repo data, scoring it, and writing to SQLite.
Run this script directly to refresh the database for a given org:

    python pipeline.py
"""

import logging
import os
from dotenv import load_dotenv
import transform_data as td
import database as db

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

# Datadog — optional; skipped gracefully if API key is not configured.
_DD_API_KEY = os.getenv("DATADOG_API_KEY")
if _DD_API_KEY:
    try:
        from datadog import initialize, api as _dd_api
        initialize(api_key=_DD_API_KEY)
        _dd_enabled = True
        logger.info("Datadog initialized successfully.")
    except Exception as _dd_exc:
        logger.warning("Datadog initialization failed: %s", _dd_exc)
        _dd_enabled = False
else:
    _dd_enabled = False
    logger.info(
        "DATADOG_API_KEY not set — Datadog metrics/events will be skipped."
    )


def run(org_name: str):
    """
    Fetch all repos for org_name, score them, and persist to SQLite.

    Args:
        org_name: GitHub organization name
    """
    logger.info("Pipeline started — org: %s", org_name)

    db.init_db()

    logger.info("Fetching repos from GitHub API...")
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
        "Scoring complete — repos scored: %d, score distribution: "
        "min=%.1f, mean=%.2f, max=%.1f",
        len(df),
        score_col.min(),
        score_col.mean(),
        score_col.max(),
    )

    logger.info("Writing results to SQLite — rows to write: %d", len(df))
    try:
        db.write_repos(org_name, df)
        logger.info(
            "DB write successful — %d rows written for org '%s'",
            len(df),
            org_name,
        )
    except Exception as exc:
        logger.error("DB write failed for org '%s': %s", org_name, exc)
        raise

    if _dd_enabled:
        try:
            _dd_api.Event.create(
                title="repo_archiver.pipeline.run",
                text=f"Pipeline completed for org '{org_name}'",
                tags=[f"org:{org_name}", f"repo_count:{len(df)}"],
            )
            _dd_api.Metric.send(
                metric="repo_archiver.api.rate_limit_remaining",
                points=rate_limit_remaining,
                tags=[f"org:{org_name}"],
            )
            logger.info(
                "Datadog event and metric emitted for org '%s'.", org_name
            )
        except Exception as exc:
            logger.warning("Datadog emit failed: %s", exc)

    return df


if __name__ == "__main__":
    ORG_NAME = "plotly"
    run(ORG_NAME)
