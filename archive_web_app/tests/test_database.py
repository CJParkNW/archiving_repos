"""
Tests for database.py — all tests use a temporary SQLite file so the
production repos.db is never touched.
"""
import pandas as pd
import pytest
import database

# Marking as setup function to run before tests
@pytest.fixture(autouse=True)  # Apply to each test in the file automatically.
def isolated_db(tmp_path, monkeypatch):
    """Point database.DB_PATH at a fresh temp file for every test."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db() #Initializing new temp file/database for tests.

# Sample data to ensure that the return for DF is valid 
def _sample_df(**overrides):
    """Return a one-row DataFrame with valid repo data."""
    row = {
        "id": 1,
        "name": "test-repo",
        "url": "https://github.com/test-org/test-repo",
        "description": "A test repository",
        "is_fork": False,
        "num_forks": 2,
        "num_star_watchers": 3,
        "language": "Python",
        "num_open_issues": 0,
        "is_archived": False,
        "last_push_time": "2020-01-01T00:00:00Z",
        "created_time": "2019-01-01T00:00:00Z",
        "last_update_time": "2020-01-01T00:00:00Z",
        "num_open_pull_requests": 0,
        "overall_score": 1.0,
    }
    row.update(overrides)
    return pd.DataFrame([row])

# Confirming that after initalizing the database, reading_repos is able to work.
# Even if the dataframe returned is empty/the organization does not exist.
class TestInitDb:
    def test_creates_table(self):
        # init_db is called by the fixture; reading should not raise
        result = database.read_repos("any-org")
        assert result.empty

class TestWriteAndReadRepos:
    # Write a repo to check if the name remains intact
    def test_roundtrip_preserves_name(self):
        database.write_repos("test-org", _sample_df())
        df = database.read_repos("test-org")
        assert df.iloc[0]["name"] == "test-repo"
    # Checking for overall_score
    def test_roundtrip_preserves_score(self):
        database.write_repos("test-org", _sample_df(overall_score=0.6))
        df = database.read_repos("test-org")
        assert df.iloc[0]["overall_score"] == pytest.approx(0.6)
    # Checking if df is capable of handling both rows and not just one result.
    def test_multiple_repos_all_written(self):
        multi_df = pd.DataFrame([
            {**_sample_df().iloc[0].to_dict(), "name": "repo-a", "id": 1},
            {**_sample_df().iloc[0].to_dict(), "name": "repo-b", "id": 2},
        ])
        database.write_repos("test-org", multi_df)
        result = database.read_repos("test-org")
        assert len(result) == 2
    # Rewrites score to ensure updating works (doesn't duplicate)
    def test_insert_or_replace_updates_existing_row(self):
        database.write_repos("test-org", _sample_df(overall_score=0.4))
        database.write_repos("test-org", _sample_df(overall_score=0.9))
        result = database.read_repos("test-org")
        assert len(result) == 1
        assert result.iloc[0]["overall_score"] == pytest.approx(0.9)

    # Writes repos under two different names to ensure that each sees its own.
    def test_repos_isolated_by_org(self):
        database.write_repos("org-a", _sample_df())
        database.write_repos("org-b", _sample_df(name="other-repo", id=2))
        assert len(database.read_repos("org-a")) == 1
        assert len(database.read_repos("org-b")) == 1
        assert database.read_repos("org-a").iloc[0]["name"] == "test-repo"

    # Passes an empty df to ensure nothing gets written to ensure a crash
    # does not happen.
    def test_empty_df_does_not_write(self):
        database.write_repos("test-org", pd.DataFrame())
        assert database.read_repos("test-org").empty
    
    # Passes an incorrectly formatted DF to capture value errors and prevent crash
    def test_missing_required_columns_raises(self):
        bad_df = pd.DataFrame([{"id": 1, "url": "https://example.com"}])
        with pytest.raises(ValueError, match="missing required columns"):
            database.write_repos("test-org", bad_df)


class TestReadRepos:
    # Query a new org and ensure that the result is an empty DF 
    def test_returns_empty_df_for_unknown_org(self):
        result = database.read_repos("nonexistent-org")
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetLastFetched:
    # Confirm that the variable is None if the org has had no data yet.
    def test_returns_none_when_no_data(self):
        assert database.get_last_fetched("empty-org") is None

    # Write a repo and checks that fetching returns a timestamp equal or later
    # Ensures that it is recording the most recent write.
    def test_returns_timestamp_string_after_write(self):
        database.write_repos("test-org", _sample_df())
        ts = database.get_last_fetched("test-org")
        assert ts is not None
        assert "T" in ts  # ISO 8601 format

    # Calls repo twice to ensure that the most recent timestamp is recorded
    # Do not return the first recorded timestamp.
    def test_returns_most_recent_timestamp(self):
        database.write_repos("test-org", _sample_df())
        first_ts = database.get_last_fetched("test-org")
        database.write_repos("test-org", _sample_df(overall_score=0.5))
        second_ts = database.get_last_fetched("test-org")
        assert second_ts >= first_ts
