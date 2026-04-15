"""
Tests for calculate_archiving_score() in transform_data.py.

Score breakdown (each condition contributes 0.2, partial conditions 0.1):
  - No open issues           → +0.2  (issues < 5 → +0.1)
  - No open pull requests    → +0.2  (PRs < 5 → +0.1)
  - Stars < 5                → +0.2  (stars < 10 → +0.1)
  - Forks < 5                → +0.2  (forks < 10 → +0.1)
  - Last push >= 1 year ago  → +0.2  (>= 6 months → +0.1)
Max score = 1.0 (strong archive candidate)
Min score = 0.0 (should not be archived)
"""
from datetime import datetime, timedelta

import pytest

from transform_data import calculate_archiving_score

# A date guaranteed to be more than a year in the past
OLD_PUSH = "2020-01-01T00:00:00Z"
# A date guaranteed to be within the last month
RECENT_PUSH = (
    datetime.now() - timedelta(days=7)
).strftime("%Y-%m-%dT%H:%M:%SZ")
SIX_MONTHS_AGO = (
    datetime.now() - timedelta(days=200)
).strftime("%Y-%m-%dT%H:%M:%SZ")


class TestPerfectArchiveCandidate:
    def test_returns_max_score(self):
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        assert score == 1.0

    def test_score_is_float(self):
        score = calculate_archiving_score(0, 0, 1, 1, OLD_PUSH)
        assert isinstance(score, float)


class TestShouldNotArchive:
    def test_returns_zero_for_active_popular_repo(self):
        score = calculate_archiving_score(
            num_open_issues=50,
            num_open_pull_requests=10,
            star_watcher_count=100,
            num_forks=200,
            last_push_time=RECENT_PUSH,
        )
        assert score == 0.0


class TestPartialScores:
    def test_no_issues_no_prs_but_active(self):
        # +0.2 (no issues) +0.2 (no PRs) +0.2 (stars<5) +0.2 (forks<5) = 0.8
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=RECENT_PUSH,
        )
        assert score == 0.8

    def test_moderate_stars_and_forks(self):
        # +0.2 (no issues) +0.2 (no PRs) +0.1 (stars 5-9)
        # +0.1 (forks 5-9) +0.2 (old push)
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=7,
            num_forks=6,
            last_push_time=OLD_PUSH,
        )
        assert score == 0.8

    def test_push_between_six_months_and_one_year(self):
        # +0.2 (no issues) +0.2 (no PRs) +0.2 (stars<5)
        # +0.2 (forks<5) +0.1 (6-12mo push)
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=SIX_MONTHS_AGO,
        )
        assert score == 0.9

    def test_few_issues_gives_partial_credit(self):
        # issues 1-4 → +0.1 (not the full +0.2)
        score = calculate_archiving_score(
            num_open_issues=3,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        assert score == pytest.approx(0.9)

    def test_many_issues_gives_no_credit(self):
        # issues >= 5 → +0.0
        score = calculate_archiving_score(
            num_open_issues=5,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        assert score == 0.8

    def test_open_issues_reduces_score(self):
        score_with_issues = calculate_archiving_score(
            num_open_issues=5,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        score_without_issues = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        assert score_with_issues < score_without_issues

    def test_few_prs_gives_partial_credit(self):
        # PRs 1-4 → +0.1 (not the full +0.2)
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=2,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        assert score == pytest.approx(0.9)

    def test_many_prs_gives_no_credit(self):
        # PRs >= 5 → +0.0
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=5,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        assert score == 0.8

    def test_open_prs_reduces_score(self):
        score_with_prs = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=3,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        score_without_prs = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            last_push_time=OLD_PUSH,
        )
        assert score_with_prs < score_without_prs


class TestNullLastPushTime:
    def test_none_push_time_does_not_raise(self):
        # Repos that were never pushed should not crash the scorer
        score = calculate_archiving_score(0, 0, 1, 1, None)
        assert isinstance(score, float)

    def test_none_push_time_treated_as_inactive(self):
        # A repo with no push history should score the same as one pushed
        # more than a year ago (full credit for the time component)
        score_none = calculate_archiving_score(0, 0, 1, 1, None)
        score_old = calculate_archiving_score(0, 0, 1, 1, OLD_PUSH)
        assert score_none == score_old


class TestScoreBounds:
    def test_score_never_below_zero(self):
        score = calculate_archiving_score(999, 999, 9999, 9999, RECENT_PUSH)
        assert score >= 0.0

    def test_score_never_above_one(self):
        score = calculate_archiving_score(0, 0, 0, 0, OLD_PUSH)
        assert score <= 1.0
