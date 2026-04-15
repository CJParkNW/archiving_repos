"""
This module allows you to read in all of the important data from the
GitHub Rest API regarding each public repository in an organization.
"""

from datetime import datetime
import requests
import pandas as pd

MAX_TIMEOUT = 100
# Maximum number of branches to check when scanning for the latest commit.
# Caps API calls for repos with many branches; 10 is enough to catch recent
# activity on any actively-developed repo.
MAX_BRANCHES_TO_CHECK = 10


def get_rate_limit_remaining(headers_input: dict) -> int:
    """Return the number of remaining GitHub API requests for this token."""
    r = requests.get('https://api.github.com/rate_limit',
                     headers=headers_input, timeout=MAX_TIMEOUT)
    return r.json().get('rate', {}).get('remaining', -1)


def read_all_repo_data(
        organization_name: str, headers_input: dict) -> tuple[list, int]:
    """
    Use the provided API key and organization on GitHub to extract all general
    data on all available/accessible repositories from GitHub's REST API.

    Args:
        organization_name: Organization that is looked at in the API endpoint
        headers_input: Provides headers with API Key to increase access limit

    Returns:
        output_file: JSON formatted list of all repo outputs from GitHub API
        num_calls: Total number of GitHub API calls made
    """
    # Calling the API endpoint with proper headers/API Key
    r = requests.get(f'https://api.github.com/orgs/{organization_name}/repos',
                     headers=headers_input, timeout=MAX_TIMEOUT)

    # Converting HTTP output into readable JSON
    output_file = r.json()
    if not isinstance(output_file, list):
        raise ValueError(
            f"GitHub API returned an unexpected response for org "
            f"'{organization_name}': {output_file.get('message', output_file)}"
        )
    num_calls = 1
    # Using Pagination, while there are additional pages in the request output,
    # Continue to call until the end to create one complete JSON file
    while 'next' in r.links.keys():
        r = requests.get(r.links['next']['url'], timeout=MAX_TIMEOUT)
        output_file.extend(r.json())
        num_calls += 1
        # Source: docs.github.com/en/rest/repos/repos
        # ?apiVersion=2022-11-28#list-organization-repositories

    return output_file, num_calls


def calculate_archiving_score(num_open_issues: int,
                              num_open_pull_requests: int,
                              star_watcher_count: int,
                              num_forks: int,
                              latest_commit_time: str,
                              latest_pr_time: str,
                              median_issues: float,
                              median_prs: float,
                              median_stars: float,
                              median_forks: float) -> float:
    """
    Uses the provided metadata on a repo to calculate a metric for whether it
    would be acceptable to archive the selected repository. Thresholds for
    issues, pull requests, stars, and forks are derived from the organization's
    own median values so that scoring adapts to the activity level of each org.
    - Higher score indicates that it should be archived
    - Score of 0 indicates that it should not be archived.
    - Score of 1 indicates that it should be archived.

    Args:
        num_open_issues: Total number of open issues in the repo
        num_open_pull_requests: Total number of open pull requests in the repo
        star_watcher_count: Total number of stars on the repo
        num_forks: Total number of forks created based off the repo
        latest_commit_time: Date of the most recent commit across all branches
        latest_pr_time: Date of the most recently updated PR (any state),
            or None if the repo has never had a PR
        median_issues: Organization-wide median number of open issues
        median_prs: Organization-wide median number of open pull requests
        median_stars: Organization-wide median star/watcher count
        median_forks: Organization-wide median fork count

    Returns:
        score_metric: Value ranging from 0.0 to 1.0 that determines if a repo
        should or should not be archived.

    """
    EPOCH_TIME_DAY = 86400
    NUM_DAYS_IN_YEAR = 365

    # Per-criterion score weights (full / partial).
    # Recency signals carry the most weight; stars and forks are supporting.
    COMMIT_FULL = 0.25
    COMMIT_PARTIAL = 0.15
    ISSUES_FULL = 0.20
    ISSUES_PARTIAL = 0.10
    PRS_COUNT_FULL = 0.20
    PRS_COUNT_PARTIAL = 0.10
    PR_TIME_FULL = 0.15
    PR_TIME_PARTIAL = 0.10
    STARS_FULL = 0.10
    STARS_PARTIAL = 0.05
    FORKS_FULL = 0.10
    FORKS_PARTIAL = 0.05

    score_metric = 0
    today_epoch = datetime.now().timestamp()

    # 1. Latest commit recency (0.25 max) — most important signal.
    # A repo with no commits is treated as fully inactive.
    if latest_commit_time is None:
        score_metric += COMMIT_FULL
    else:
        commit_epoch = datetime.strptime(
            latest_commit_time, '%Y-%m-%dT%H:%M:%SZ'
        ).timestamp()
        commit_age = today_epoch - commit_epoch
        if commit_age >= EPOCH_TIME_DAY * NUM_DAYS_IN_YEAR:
            score_metric += COMMIT_FULL
        elif commit_age >= EPOCH_TIME_DAY * NUM_DAYS_IN_YEAR / 2:
            score_metric += COMMIT_PARTIAL

    # 2. Open issues count (0.20 max).
    # Zero is always a strong signal; below the org median earns
    # partial credit.
    if num_open_issues == 0:
        score_metric += ISSUES_FULL
    elif num_open_issues < median_issues:
        score_metric += ISSUES_PARTIAL

    # 3. Open pull request count (0.20 max).
    # Zero is always a strong signal; below the org median earns
    # partial credit.
    if num_open_pull_requests == 0:
        score_metric += PRS_COUNT_FULL
    elif num_open_pull_requests < median_prs:
        score_metric += PRS_COUNT_PARTIAL

    # 4. PR activity recency (0.15 max).
    # A repo that has never had a PR is treated as fully inactive.
    if latest_pr_time is None:
        score_metric += PR_TIME_FULL
    else:
        pr_epoch = datetime.strptime(
            latest_pr_time, '%Y-%m-%dT%H:%M:%SZ'
        ).timestamp()
        pr_age = today_epoch - pr_epoch
        if pr_age >= EPOCH_TIME_DAY * NUM_DAYS_IN_YEAR:
            score_metric += PR_TIME_FULL
        elif pr_age >= EPOCH_TIME_DAY * NUM_DAYS_IN_YEAR / 2:
            score_metric += PR_TIME_PARTIAL

    # 5. Stars (0.10 max) — below org median → full; below 2× median → partial.
    # Source: docs.github.com/en/get-started/exploring-projects-on-github/
    # saving-repositories-with-stars#about-stars
    if star_watcher_count < median_stars:
        score_metric += STARS_FULL
    elif star_watcher_count < median_stars * 2:
        score_metric += STARS_PARTIAL

    # 6. Forks (0.10 max) — below org median → full; below 2× median → partial.
    if num_forks < median_forks:
        score_metric += FORKS_FULL
    elif num_forks < median_forks * 2:
        score_metric += FORKS_PARTIAL

    return score_metric


def collect_data_on_pull_requests(organization_name: str,
                                  repository_name: str,
                                  headers_input: dict) -> int:
    """
    Uses the provided organization name and repository name to pull data on
    whether there are any open pull requests.

    Args:
        organization_name: Organization that is looked at in the API endpoint
        repository_name: Repo that is looked at in the API endpoint

    Returns:
        num_open_pull_requests: Total number of open pull requests in the repo
    """
    # Pulling additional data on if there are any open pull requests
    pr_url = (
        f"https://api.github.com/repos/{organization_name}"
        f"/{repository_name}/pulls?state=open"
    )
    pull_request_endpoint = requests.get(
        pr_url, headers=headers_input, timeout=MAX_TIMEOUT
    )
    # Source: docs.github.com/en/rest/pulls/pulls
    # ?apiVersion=2022-11-28#list-pull-requests
    # Outputs information on any open pull requests
    pull_request_output = pull_request_endpoint.json()
    # Counts the total number of open pull requests (if available)
    # length of this output will give the number of open pull requests
    num_open_pull_requests = len(pull_request_output)

    return num_open_pull_requests


def get_latest_commit_date(organization_name: str,
                           repository_name: str,
                           headers_input: dict) -> tuple[str | None, int]:
    """
    Return the ISO-8601 date string of the most recent commit across all
    branches of the repo, or None if the repo has no commits.

    Fetches branches in one call (capped at MAX_BRANCHES_TO_CHECK), then
    fetches the HEAD commit of each to find the latest committer date.

    Args:
        organization_name: GitHub organization name
        repository_name: Repository name within the organization
        headers_input: Request headers containing the API token

    Returns:
        latest_date: ISO-8601 date string of the most recent commit, or None
    """
    branches_url = (
        f"https://api.github.com/repos/{organization_name}"
        f"/{repository_name}/branches"
    )
    branches_resp = requests.get(
        branches_url,
        params={'per_page': MAX_BRANCHES_TO_CHECK},
        headers=headers_input,
        timeout=MAX_TIMEOUT,
    )
    branches = branches_resp.json()
    if not isinstance(branches, list) or not branches:
        return None, 1

    commits_base = (
        f"https://api.github.com/repos/{organization_name}"
        f"/{repository_name}/commits"
    )
    latest_date = None
    num_calls = 1  # branches call
    for branch in branches:
        resp = requests.get(
            commits_base,
            params={'sha': branch['name'], 'per_page': 1},
            headers=headers_input,
            timeout=MAX_TIMEOUT,
        )
        num_calls += 1
        commits = resp.json()
        if isinstance(commits, list) and commits:
            commit_date = commits[0]['commit']['committer']['date']
            if latest_date is None or commit_date > latest_date:
                latest_date = commit_date

    return latest_date, num_calls


def get_latest_pr_date(organization_name: str,
                       repository_name: str,
                       headers_input: dict) -> str | None:
    """
    Return the ISO-8601 updated_at date of the most recently active PR
    (any state: open, closed, or merged), or None if the repo has no PRs.

    Args:
        organization_name: GitHub organization name
        repository_name: Repository name within the organization
        headers_input: Request headers containing the API token

    Returns:
        latest_pr_date: ISO-8601 date string of the most recent PR, or None
    """
    pr_url = (
        f"https://api.github.com/repos/{organization_name}"
        f"/{repository_name}/pulls"
    )
    resp = requests.get(
        pr_url,
        params={
            'state': 'all',
            'sort': 'updated',
            'direction': 'desc',
            'per_page': 1,
        },
        headers=headers_input,
        timeout=MAX_TIMEOUT,
    )
    # Source: docs.github.com/en/rest/pulls/pulls
    # ?apiVersion=2022-11-28#list-pull-requests
    prs = resp.json()
    if not isinstance(prs, list) or not prs:
        return None
    return prs[0]['updated_at']


def create_entire_repo_dataframe(organization_name: str,
                                 headers_input: dict):
    """
    Uses the provided organization name and repository name to pull data on
    whether there are any open pull requests.

    Args:
        organization_name: Organization that is looked at in the API endpoint
        repository_name: Repo that is looked at in the API endpoint

    Returns:
        df: Entire dataframe with all of an organization's repos and info
    """

    output_file, api_calls = read_all_repo_data(
        organization_name, headers_input
    )

    # Phase 1: collect raw fields for every repo (no scoring yet).
    # All repos must be fetched first so we can derive org-wide medians.
    rows = []
    for repo in output_file:
        num_open_pull_requests = collect_data_on_pull_requests(
            organization_name, repo['name'], headers_input
        )
        api_calls += 1
        latest_commit_time, commit_calls = get_latest_commit_date(
            organization_name, repo['name'], headers_input
        )
        api_calls += commit_calls
        latest_pr_time = get_latest_pr_date(
            organization_name, repo['name'], headers_input
        )
        api_calls += 1
        rows.append({
            'name':                   repo['name'],
            'id':                     repo['id'],
            'url':                    repo['html_url'],
            'description':            repo['description'],
            'is_fork':                repo['fork'],
            'num_forks':              repo['forks_count'],
            'num_star_watchers':      repo['stargazers_count'],
            # Source: docs.github.com/en/rest/activity/starring
            # ?apiVersion=2022-11-28#starring-versus-watching
            'language':               repo['language'],
            'num_open_issues':        repo['open_issues_count'],
            'is_archived':            repo['archived'],
            'last_push_time':         repo['pushed_at'],
            'created_time':           repo['created_at'],
            'last_update_time':       repo['updated_at'],
            # Source: https://github.com/orgs/community/discussions/24442
            'num_open_pull_requests': num_open_pull_requests,
            'latest_commit_time':     latest_commit_time,
            'latest_pr_time':         latest_pr_time,
        })

    df = pd.DataFrame(rows)

    # Phase 2: compute org-wide medians to use as dynamic scoring thresholds.
    median_issues = df['num_open_issues'].median()
    median_prs = df['num_open_pull_requests'].median()
    median_stars = df['num_star_watchers'].median()
    median_forks = df['num_forks'].median()

    # Phase 3: score every repo relative to the org medians computed above.
    df['overall_score'] = df.apply(
        lambda row: round(
            calculate_archiving_score(
                row['num_open_issues'],
                row['num_open_pull_requests'],
                row['num_star_watchers'],
                row['num_forks'],
                row['latest_commit_time'],
                row['latest_pr_time'],
                median_issues,
                median_prs,
                median_stars,
                median_forks,
            ),
            1,
        ),
        axis=1,
    )

    return df[['name', 'id', 'url', 'description', 'is_fork', 'num_forks',
               'num_star_watchers', 'language', 'num_open_issues',
               'is_archived', 'last_push_time', 'created_time',
               'last_update_time', 'num_open_pull_requests',
               'latest_commit_time', 'latest_pr_time',
               'overall_score']], api_calls
