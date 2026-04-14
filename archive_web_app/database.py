"""
SQLite integration for the GitHub Repo Archiver.
Handles schema creation, writes from the pipeline, and reads for the web app.
"""

import sqlite3
from datetime import datetime

DB_PATH = "repos.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the repos table if it doesn't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            id                    INTEGER,
            org                   TEXT NOT NULL,
            name                  TEXT NOT NULL,
            url                   TEXT,
            description           TEXT,
            is_fork               INTEGER,
            num_forks             INTEGER,
            num_star_watchers     INTEGER,
            language              TEXT,
            num_open_issues       INTEGER,
            is_archived           INTEGER,
            last_push_time        TEXT,
            created_time          TEXT,
            last_update_time      TEXT,
            num_open_pull_requests INTEGER,
            overall_score         REAL,
            last_fetched_at       TEXT NOT NULL,
            PRIMARY KEY (org, name)
        )
    """)
    conn.commit()
    conn.close()


def write_repos(org: str, df):
    """
    Write (or replace) all repos for an org into the database.

    Args:
        org: GitHub organization name
        df:  Pandas DataFrame produced by transform_data.create_entire_repo_dataframe()
    """
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()

    for _, row in df.iterrows():
        conn.execute("""
            INSERT OR REPLACE INTO repos (
                id, org, name, url, description,
                is_fork, num_forks, num_star_watchers,
                language, num_open_issues, is_archived,
                last_push_time, created_time, last_update_time,
                num_open_pull_requests, overall_score, last_fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("id"),
            org,
            row["name"],
            row.get("url"),
            row.get("description"),
            int(bool(row.get("is_fork"))),
            row.get("num_forks"),
            row.get("num_star_watchers"),
            row.get("language"),
            row.get("num_open_issues"),
            int(bool(row.get("is_archived"))),
            row.get("last_push_time"),
            row.get("created_time"),
            row.get("last_update_time"),
            row.get("num_open_pull_requests"),
            row.get("overall_score"),
            now,
        ))

    conn.commit()
    conn.close()


def read_repos(org: str):
    """
    Load all repos for an org from the database into a Pandas DataFrame.

    Args:
        org: GitHub organization name

    Returns:
        df: Pandas DataFrame (empty if no data found for org)
    """
    import pandas as pd
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM repos WHERE org = ?", (org,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


def get_last_fetched(org: str) -> str | None:
    """
    Return the most recent last_fetched_at timestamp for an org, or None.

    Args:
        org: GitHub organization name
    """
    conn = get_connection()
    cursor = conn.execute(
        "SELECT MAX(last_fetched_at) FROM repos WHERE org = ?", (org,)
    )
    result = cursor.fetchone()[0]
    conn.close()
    return result
