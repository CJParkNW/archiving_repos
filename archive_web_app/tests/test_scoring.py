"""
Tests for calculate_archiving_score() in transform_data.py.

Thresholds for issues, PRs, stars, and forks are dynamic (org-wide medians).
Score breakdown — weights per criterion (full / partial):
  - Latest commit recency   → 0.25 / 0.15  (None or ≥1yr / 6–12mo)
  - Open issues count       → 0.20 / 0.10  (== 0 / below median)
  - Open PR count           → 0.20 / 0.10  (== 0 / below median)
  - PR activity recency     → 0.15 / 0.10  (None or ≥1yr / 6–12mo)
  - Stars                   → 0.10 / 0.05  (< median / < 2× median)
  - Forks                   → 0.10 / 0.05  (< median / < 2× median)
Max score = 1.0 (strong archive candidate)
Min score = 0.0 (should not be archived)

MED_* constants are set to 5.0 to replicate the original static thresholds,
keeping numeric assertions stable across tests.
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

# Median values that replicate the original static thresholds (5 / 10).
MED_ISSUES = 5.0
MED_PRS = 5.0
MED_STARS = 5.0
MED_FORKS = 5.0


class TestPerfectArchiveCandidate:
    # Generates an example that should produce an archiving score of 1.
    def test_returns_max_score(self):
        # commit OLD (+0.25) issues=0 (+0.20) prs=0 (+0.20)
        # pr=None (+0.15) stars<5 (+0.10) forks<5 (+0.10) = 1.0
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == 1.0

    # Since the scoring criteria can be a float --> Ensure that it does not
    # become an int.
    def test_score_is_float(self):
        score = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert isinstance(score, float)


class TestShouldNotArchive:
    # Creates a sample repo/score where it should not archive.
    # The repo is considered highly active.
    def test_returns_zero_for_active_popular_repo(self):
        score = calculate_archiving_score(
            num_open_issues=50,
            num_open_pull_requests=10,
            star_watcher_count=100,
            num_forks=200,
            latest_commit_time=RECENT_PUSH,
            latest_pr_time=RECENT_PUSH,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == 0.0


class TestPartialScores:
    # All the following functions verify that different combinations of
    # partial scores will be accurately calculated.
    def test_no_issues_no_prs_but_active(self):
        # commit RECENT (+0) issues=0 (+0.20) prs=0 (+0.20)
        # pr RECENT (+0) stars<5 (+0.10) forks<5 (+0.10) = 0.60
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=RECENT_PUSH,
            latest_pr_time=RECENT_PUSH,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.60)

    def test_moderate_stars_and_forks(self):
        # commit OLD (+0.25) issues=0 (+0.20) prs=0 (+0.20)
        # pr OLD (+0.15) stars 5-9 (+0.05) forks 5-9 (+0.05) = 0.90
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=7,
            num_forks=6,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=OLD_PUSH,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.90)

    def test_commit_between_six_months_and_one_year(self):
        # commit 6mo (+0.15) issues=0 (+0.20) prs=0 (+0.20)
        # pr 6mo (+0.10) stars<5 (+0.10) forks<5 (+0.10) = 0.85
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=SIX_MONTHS_AGO,
            latest_pr_time=SIX_MONTHS_AGO,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.85)

    def test_few_issues_gives_partial_credit(self):
        # commit OLD (+0.25) issues=3<5 (+0.10) prs=0 (+0.20)
        # pr=None (+0.15) stars<5 (+0.10) forks<5 (+0.10) = 0.90
        score = calculate_archiving_score(
            num_open_issues=3,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.90)

    def test_many_issues_gives_no_credit(self):
        # issues >= median (5) → +0.0
        # commit OLD (+0.25) issues=5 (+0) prs=0 (+0.20)
        # pr=None (+0.15) stars<5 (+0.10) forks<5 (+0.10) = 0.80
        score = calculate_archiving_score(
            num_open_issues=5,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.80)

    def test_open_issues_reduces_score(self):
        score_with_issues = calculate_archiving_score(
            num_open_issues=5,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        score_without_issues = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score_with_issues < score_without_issues

    def test_few_prs_gives_partial_credit(self):
        # commit OLD (+0.25) issues=0 (+0.20) prs=2<5 (+0.10)
        # pr OLD (+0.15) stars<5 (+0.10) forks<5 (+0.10) = 0.90
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=2,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=OLD_PUSH,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.90)

    def test_many_prs_gives_no_credit(self):
        # prs >= median (5) → +0.0
        # commit OLD (+0.25) issues=0 (+0.20) prs=5 (+0)
        # pr OLD (+0.15) stars<5 (+0.10) forks<5 (+0.10) = 0.80
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=5,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=OLD_PUSH,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.80)

    def test_open_prs_reduces_score(self):
        score_with_prs = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=3,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=OLD_PUSH,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        score_without_prs = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=OLD_PUSH,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score_with_prs < score_without_prs


class TestCommitRecency:
    def test_none_commit_time_does_not_raise(self):
        # Repos with no commits should not crash the scorer
        score = calculate_archiving_score(
            0, 0, 1, 1, None, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert isinstance(score, float)

    def test_none_commit_treated_as_inactive(self):
        # A repo with no commits should score the same as one with a commit
        # more than a year ago (full credit for the time component)
        score_none = calculate_archiving_score(
            0, 0, 1, 1, None, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        score_old = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert score_none == score_old

    def test_recent_commit_gets_no_credit(self):
        # A commit within the last month → no credit for commit recency
        score_recent = calculate_archiving_score(
            0, 0, 1, 1, RECENT_PUSH, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        score_old = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert score_recent < score_old

    def test_commit_six_months_ago_gets_partial_credit(self):
        # commit 6mo ago (+0.15) issues=0 (+0.20) prs=0 (+0.20)
        # pr=None (+0.15) stars<5 (+0.10) forks<5 (+0.10) = 0.90
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=SIX_MONTHS_AGO,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.90)


class TestPRRecency:
    def test_none_pr_time_does_not_raise(self):
        # Repos that have never had a PR should not crash the scorer
        score = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert isinstance(score, float)

    def test_none_pr_time_treated_as_full_credit(self):
        # A repo with no PRs gets full credit for PR recency (never had activity)
        score_none = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        score_old = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, OLD_PUSH,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert score_none == score_old

    def test_recent_pr_gets_no_credit(self):
        # PR activity within the last month → no credit for PR recency
        score_recent = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, RECENT_PUSH,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        score_old = calculate_archiving_score(
            0, 0, 1, 1, OLD_PUSH, OLD_PUSH,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert score_recent < score_old

    def test_pr_six_months_ago_gets_partial_credit(self):
        # commit OLD (+0.25) issues=0 (+0.20) prs=0 (+0.20)
        # pr 6mo (+0.10) stars<5 (+0.10) forks<5 (+0.10) = 0.95
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=SIX_MONTHS_AGO,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.95)


# Should hold regardless of the inputs and how high or low they are
class TestScoreBounds:
    def test_score_never_below_zero(self):
        score = calculate_archiving_score(
            999, 999, 9999, 9999, RECENT_PUSH, RECENT_PUSH,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert score >= 0.0

    def test_score_never_above_one(self):
        score = calculate_archiving_score(
            0, 0, 0, 0, OLD_PUSH, None,
            MED_ISSUES, MED_PRS, MED_STARS, MED_FORKS,
        )
        assert score <= 1.0


class TestDynamicThresholds:
    """Verify that score boundaries shift when org-wide medians change."""

    def test_issue_below_median_earns_partial_credit(self):
        # With median=10, a repo with 3 issues is below median → +0.10
        score_below = calculate_archiving_score(
            num_open_issues=3,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=10.0,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        # With median=2, a repo with 3 issues is above median → +0.0
        score_above = calculate_archiving_score(
            num_open_issues=3,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=2.0,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score_below > score_above

    def test_stars_above_2x_median_gets_no_credit(self):
        # stars=20, median=5 → 20 >= 2×5=10 → no stars credit
        # commit OLD (+0.25) issues=0 (+0.20) prs=0 (+0.20)
        # pr=None (+0.15) stars≥10 (+0) forks<5 (+0.10) = 0.90
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=20,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=5.0,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.90)

    def test_stars_between_1x_and_2x_median_earns_partial_credit(self):
        # stars=7, median=5 → between 5 and 10 → +0.05
        # commit OLD (+0.25) issues=0 (+0.20) prs=0 (+0.20)
        # pr=None (+0.15) stars partial (+0.05) forks<5 (+0.10) = 0.95
        score = calculate_archiving_score(
            num_open_issues=0,
            num_open_pull_requests=0,
            star_watcher_count=7,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=MED_ISSUES,
            median_prs=MED_PRS,
            median_stars=5.0,
            median_forks=MED_FORKS,
        )
        assert score == pytest.approx(0.95)

    def test_higher_median_makes_moderately_active_repo_more_archivable(self):
        # Same repo, different org medians — higher median → higher score
        score_high_median = calculate_archiving_score(
            num_open_issues=3,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=10.0,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        score_low_median = calculate_archiving_score(
            num_open_issues=3,
            num_open_pull_requests=0,
            star_watcher_count=1,
            num_forks=1,
            latest_commit_time=OLD_PUSH,
            latest_pr_time=None,
            median_issues=2.0,
            median_prs=MED_PRS,
            median_stars=MED_STARS,
            median_forks=MED_FORKS,
        )
        assert score_high_median > score_low_median
