"""
End-to-end integration tests for the Dash web app.

Two test surfaces are covered:

  HTTP layer  — verify the Flask/Dash server boots and key endpoints respond.
  App layer   — call page-builder functions and callbacks directly with real
                data read from an isolated SQLite database, confirming that
                the full DB → transform → render pipeline works together.

Fixture strategy
----------------
`app.py` runs several statements at module level (init_db, read_repos,
Image.open) so we must prepare the environment *before* importing it:

  1. Patch ``database.DB_PATH`` to a temp file and seed it with sample repos.
  2. ``os.chdir`` to ``archive_web_app/`` so ``Image.open("images/...")``
     resolves correctly.
  3. Evict any stale ``app`` entry from ``sys.modules`` and re-import, so
     module-level code runs against our patched DB.

The fixture is module-scoped so the app is booted only once per test session.
"""
import json
import os
import sys

import pandas as pd
import pytest


ARCHIVE_WEB_APP_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
OLD_PUSH = "2020-01-01T00:00:00Z"
RECENT_PUSH = "2025-12-01T00:00:00Z"
TEST_ORG = "plotly"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sample_df(org=TEST_ORG, n=6):
    """
    Synthetic repos: one already-archived (repo-0, high score),
    the rest active at descending scores.
    """
    rows = [
        {
            "id": i + 1,
            "name": f"repo-{i}",
            "url": f"https://github.com/{org}/repo-{i}",
            "description": f"Description {i}",
            "is_fork": 0,
            "num_forks": i,
            "num_star_watchers": i * 2,
            "language": "Python",
            "num_open_issues": 0,
            "is_archived": 1 if i == 0 else 0,
            "last_push_time": OLD_PUSH if i < 4 else RECENT_PUSH,
            "created_time": "2019-01-01T00:00:00Z",
            "last_update_time": "2020-06-01T00:00:00Z",
            "num_open_pull_requests": 0,
            "overall_score": round(1.0 - i * 0.15, 2),
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Module-scoped fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def setup_app(tmp_path_factory):
    """
    Boot the app once against an isolated DB; yield (flask_client, app_module).
    Restores CWD and DB_PATH on teardown.
    """
    import database

    # 1. Redirect DB to a fresh temp file
    original_db_path = database.DB_PATH
    tmp_db = str(
        tmp_path_factory.mktemp("integration") / "app_test.db"
    )
    database.DB_PATH = tmp_db
    database.init_db()
    database.write_repos(TEST_ORG, _make_sample_df())

    # 2. Switch CWD so Image.open("images/...") works
    original_cwd = os.getcwd()
    os.chdir(ARCHIVE_WEB_APP_DIR)

    # 3. Force a fresh import of app with the patched DB in place
    sys.modules.pop("app", None)
    import app as dash_app  # noqa: PLC0415

    flask_client = dash_app.app.server.test_client()

    yield flask_client, dash_app

    # Teardown
    os.chdir(original_cwd)
    database.DB_PATH = original_db_path
    sys.modules.pop("app", None)


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

class TestHttpLayer:
    def test_root_returns_200(self, setup_app):
        client, _ = setup_app
        assert client.get("/").status_code == 200

    def test_layout_endpoint_returns_valid_json(self, setup_app):
        client, _ = setup_app
        response = client.get("/_dash-layout")
        assert response.status_code == 200
        data = json.loads(response.data)
        # Dash serialises components as objects with "type" and/or "props"
        assert "type" in data or "props" in data

    def test_dependencies_endpoint_returns_200(self, setup_app):
        client, _ = setup_app
        assert client.get("/_dash-dependencies").status_code == 200


# ---------------------------------------------------------------------------
# Overview page builder
# ---------------------------------------------------------------------------

class TestOverviewPage:
    def test_build_overview_returns_component(self, setup_app):
        _, app_module = setup_app
        result = app_module.build_overview(_make_sample_df(), TEST_ORG)
        assert result is not None

    def test_overview_includes_org_name(self, setup_app):
        _, app_module = setup_app
        result_str = str(
            app_module.build_overview(_make_sample_df(), TEST_ORG)
        )
        assert TEST_ORG in result_str

    def test_overview_table_excludes_archived_repos(self, setup_app):
        _, app_module = setup_app
        df = _make_sample_df(n=4)
        overview = app_module.build_overview(df, TEST_ORG)
        # The DataTable sits at overview.children[5].children[0].children.
        # Its `data` prop is built from the filtered table_df, so archived
        # repo-0 must be absent and repo-1 must be present.
        data_table = overview.children[5].children[0].children
        names = [row["name"] for row in data_table.data]
        assert "repo-0" not in names
        assert "repo-1" in names


# ---------------------------------------------------------------------------
# Calibration callout
# ---------------------------------------------------------------------------

class TestCalibrationCallout:
    def test_no_archived_repos_shows_secondary(self, setup_app):
        _, app_module = setup_app
        df = _make_sample_df(n=4)
        df["is_archived"] = 0
        assert app_module.build_calibration_callout(df).color == "secondary"

    def test_high_agreement_shows_success(self, setup_app):
        _, app_module = setup_app
        df = _make_sample_df(n=4)
        # Two archived repos both with high scores
        df.loc[0, "is_archived"] = 1
        df.loc[0, "overall_score"] = 1.0
        df.loc[1, "is_archived"] = 1
        df.loc[1, "overall_score"] = 0.9
        assert app_module.build_calibration_callout(df).color == "success"

    def test_low_agreement_shows_danger(self, setup_app):
        _, app_module = setup_app
        df = _make_sample_df(n=4)
        # Three archived repos all with low scores
        for idx in range(3):
            df.loc[idx, "is_archived"] = 1
            df.loc[idx, "overall_score"] = 0.1
        assert app_module.build_calibration_callout(df).color == "danger"


# ---------------------------------------------------------------------------
# Deep Dive page builder
# ---------------------------------------------------------------------------

class TestDeepDivePage:
    def test_build_deep_dive_returns_component(self, setup_app):
        _, app_module = setup_app
        assert app_module.build_deep_dive(_make_sample_df()) is not None

    def test_dropdown_excludes_archived_repo(self, setup_app):
        _, app_module = setup_app
        df = _make_sample_df(n=5)   # repo-0 is archived
        result_str = str(app_module.build_deep_dive(df))
        assert "repo-0" not in result_str
        assert "repo-1" in result_str

    def test_empty_df_shows_fallback_message(self, setup_app):
        _, app_module = setup_app
        empty_df = pd.DataFrame(columns=_make_sample_df().columns)
        result_str = str(app_module.build_deep_dive(empty_df))
        assert "No repos found" in result_str


# ---------------------------------------------------------------------------
# render_page_content callback (called directly, bypassing HTTP)
# ---------------------------------------------------------------------------

class TestRenderPageCallback:
    def test_overview_route(self, setup_app):
        _, app_module = setup_app
        assert app_module.render_page_content("/", TEST_ORG) is not None

    def test_deep_dive_route(self, setup_app):
        _, app_module = setup_app
        assert (
            app_module.render_page_content("/deep-dive", TEST_ORG) is not None
        )

    def test_about_route(self, setup_app):
        _, app_module = setup_app
        assert app_module.render_page_content("/about", TEST_ORG) is not None

    def test_unknown_org_falls_back_gracefully(self, setup_app):
        _, app_module = setup_app
        # An org with no DB data must not raise — app falls back to startup df
        result = app_module.render_page_content("/", "nonexistent-org")
        assert result is not None
