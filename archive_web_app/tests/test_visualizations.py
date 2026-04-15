"""
Tests for create_visualizations.py — verifies each chart function returns
a valid Plotly figure given a well-formed DataFrame.
"""
import pandas as pd
import plotly.graph_objects as go
import pytest
import create_visualizations as c_viz

# Generates a sample DF to test the functions/tests
def _sample_df(n=15):
    """Return a DataFrame of n synthetic repos suitable for all chart functions."""
    return pd.DataFrame([
        {
            "name": f"repo-{i}",
            "language": ["Python", "JavaScript", "Go", "Ruby"][i % 4],
            "num_open_issues": i % 5,
            "num_open_pull_requests": i % 3,
            "num_star_watchers": i * 10,
            "num_forks": i * 2,
            "overall_score": round((i % 11) * 0.1, 1),
            "is_archived": 0,
            "last_push_time": "2020-01-01T00:00:00Z",
            "description": f"Description for repo-{i}",
            "url": f"https://github.com/test-org/repo-{i}",
        }
        for i in range(n)
    ])

# Ensures that a chart is returned and at least one instance of data exists.
class TestCreateChartPerLanguage:
    def test_returns_figure(self):
        fig = c_viz.create_chart_per_language(_sample_df())
        assert isinstance(fig, go.Figure)

    def test_figure_has_data(self):
        fig = c_viz.create_chart_per_language(_sample_df())
        assert len(fig.data) > 0

#Ensures that the chart returns and that chart caps are displaying.
class TestCreateChartTopReposWithIssues:
    def test_returns_figure(self):
        fig = c_viz.create_chart_top_repos_w_issues(_sample_df())
        assert isinstance(fig, go.Figure)

    def test_shows_at_most_ten_repos(self):
        fig = c_viz.create_chart_top_repos_w_issues(_sample_df(n=20))
        assert len(fig.data[0].x) <= 10

# Ensures that a figure is returned and that it is showing the max caps.
class TestCreateChartTopReposWithPullRequests:
    def test_returns_figure(self):
        fig = c_viz.create_chart_top_repos_w_pull_requests(_sample_df())
        assert isinstance(fig, go.Figure)

    def test_shows_at_most_ten_repos(self):
        fig = c_viz.create_chart_top_repos_w_pull_requests(_sample_df(n=20))
        assert len(fig.data[0].x) <= 10

# Ensures that that the horiz bar chart exists 
class TestCreateChartTopReposByScore:
    def test_returns_figure(self):
        fig = c_viz.create_chart_top_repos_by_score(_sample_df())
        assert isinstance(fig, go.Figure)

    def test_shows_at_most_twenty_repos(self):
        fig = c_viz.create_chart_top_repos_by_score(_sample_df(n=30))
        assert len(fig.data[0].y) <= 20

    def test_excludes_archived_repos(self):
        df = _sample_df(n=5)
        df.loc[0, "is_archived"] = 1
        df.loc[0, "overall_score"] = 1.0  # highest score but archived
        fig = c_viz.create_chart_top_repos_by_score(df)
        repo_names = list(fig.data[0].y)
        assert "repo-0" not in repo_names

    def test_highest_score_appears_last_on_y_axis(self):
        # Bars are flipped so the highest score is at the top visually
        df = _sample_df(n=5)
        fig = c_viz.create_chart_top_repos_by_score(df)
        scores = list(fig.data[0].x)
        assert scores[-1] == max(scores)
