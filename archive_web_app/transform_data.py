"""
This module allows you to read in all of the important data from the
GitHub Rest API regarding each public repository in an organization.
"""

from datetime import datetime
import requests
import pandas as pd

MAX_TIMEOUT = 100


def read_all_repo_data(organization_name: str, headers_input: dict) -> list:
    """
    Use the provided API key and organization on GitHub to extract all general
    data on all available/accessible repositories from GitHub's REST API.

    Args:
        organization_name: Organization that is looked at in the API endpoint
        headers_input: Provides headers with API Key to increase access limit

    Returns:
        output_file: JSON formatted list of all repo outputs from GitHub API
    """
    # Calling the API endpoint with proper headers/API Key
    r = requests.get(f'https://api.github.com/orgs/{organization_name}/repos',
                     headers=headers_input, timeout=MAX_TIMEOUT)

    # Converting HTTP output into readable JSON
    output_file = r.json()
    # Using Pagination, while there are additional pages in the request output,
    # Continue to call until the end to create one complete JSON file
    while 'next' in r.links.keys():
        r = requests.get(r.links['next']['url'], timeout=MAX_TIMEOUT)
        output_file.extend(r.json())
        # Source: https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#list-organization-repositories

    return output_file


def calculate_archiving_score(num_open_issues: int,
                              num_open_pull_requests: int,
                              star_watcher_count: int, num_forks: int,
                              last_push_time: str) -> float:
    """
    Uses the provided metadata on a repo to calculate a metric for whether it
    would be acceptable to archive the selected repository.
    - Higher score indicates that it should be archived
    - Score of 0 indicates that it should not be archived.
    - Score of 1 indicates that it should be archived.

    Args:
        num_open_issues: Total number of open issues in the repo
        num_open_pull_requests: Total number of open pull requests in the repo
        star_watcher_count: Total number of stars on the repo
        num_forks: Total number of forks created based off the repo
        last_push_time: Last time a push has occurred in the repo

    Returns:
        score_metric: Value ranging from 0.0 to 1.0 that determines if a repo
        should or should not be archived.

    """
    # Defining core constants for calculating acceptable metric
    EPOCH_TIME_DAY = 86400
    NUM_DAYS_IN_YEAR = 365
    ACCEPTABLE_THRESHOLD = 5
    ACCEPTABLE_STATUS = 0.2
    MAY_BE_ACCEPTABLE_THRESHOLD = 10
    MAY_BE_ACCEPTABLE_STATUS = 0.1

    # Ensures that score_metric is set to 0 before calculating
    score_metric = 0

    # Checking to ensure that there are no open issues
    if num_open_issues == 0:
        # If there are no open issues, archiving is acceptable
        score_metric += ACCEPTABLE_STATUS

    # Checking to ensure that there are no open pull requests
    if num_open_pull_requests == 0:
        # If there are no open pull requests, archiving is acceptable
        score_metric += ACCEPTABLE_STATUS

    # Checking to see if there are any stars on the repo
    if star_watcher_count < ACCEPTABLE_THRESHOLD:  # If there are very few stars
        score_metric += ACCEPTABLE_STATUS  # Archiving is acceptable
    elif star_watcher_count < MAY_BE_ACCEPTABLE_THRESHOLD:  # If there are some stars
        score_metric += MAY_BE_ACCEPTABLE_STATUS  # Archiving may be okay to do.
    # Using stars since many of GitHub's own repo ranking is based off of stars
    # Source: https://docs.github.com/en/get-started/exploring-projects-on-github/saving-repositories-with-stars#about-stars

    # Checking to see if there are a lot of forks created from this repo
    if num_forks < ACCEPTABLE_THRESHOLD:  # If there are very few forks created
        score_metric += ACCEPTABLE_STATUS  # Archiving is acceptable
    elif num_forks < MAY_BE_ACCEPTABLE_THRESHOLD:  # If there are some forms created
        score_metric += MAY_BE_ACCEPTABLE_STATUS  # Archiving may be okay to do.

    # Convert the last time that the repo was pushed into epoch time
    push_epoch = datetime.strptime(last_push_time,
                                   '%Y-%m-%dT%H:%M:%SZ').timestamp()
    # Calculate epoch time of today
    today_epoch = datetime.now().timestamp()
    # Calculate the difference between today and when the last push was.
    time_diff_from_push = today_epoch - push_epoch

    # Checking to see when the last time a repo had a change pushed in.
    if time_diff_from_push >= (EPOCH_TIME_DAY * NUM_DAYS_IN_YEAR):
        # If the push was year or more ago
        score_metric += ACCEPTABLE_STATUS  # Archiving is acceptable
    elif time_diff_from_push >= (EPOCH_TIME_DAY * NUM_DAYS_IN_YEAR/2):
        # If the push was 6 months to a year ago
        score_metric += MAY_BE_ACCEPTABLE_STATUS  # Archiving may be okay

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
    pull_request_endpoint = requests.get(f"https://api.github.com/repos/{organization_name}/{repository_name}/pulls?state=open",
                                         headers=headers_input,
                                         timeout=MAX_TIMEOUT)
    # Source: https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28#list-pull-requests
    # Outputs information on any open pull requests
    pull_request_output = pull_request_endpoint.json()
    # Counts the total number of open pull requests (if available)
    # length of this output will give the number of open pull requests
    num_open_pull_requests = len(pull_request_output)

    return num_open_pull_requests


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

    output_file = read_all_repo_data(organization_name, headers_input)

    # Setting up empty pandas dataframe to save and
    # organize repo information from API endpoint
    df = pd.DataFrame(columns=['name', 'id', 'url', 'description',
                               'is_fork', 'num_forks',
                               'num_star_watchers',
                               'language', 'num_open_issues',
                               'is_archived', 'last_push_time',
                               'created_time', 'last_update_time',
                               'num_open_pull_requests',
                               'overall_score'])

    # Iterate through the entire output JSON to organize necessary
    # information on each repo
    num_repos = len(output_file)

    for i in range(num_repos):
        # Since output provides a lot of data -> Extracting out important parts
        # Name of the Repo
        repo_name = output_file[i]['name']
        # Unique ID of the Repo
        repo_id = output_file[i]['id']
        # URL to access Repo
        repo_url = output_file[i]['html_url']
        # Description used
        repo_description = output_file[i]['description']
        # Is this repo derived from a Fork
        is_fork = output_file[i]['fork']
        # How many forks have been made of this repo?
        num_forks = output_file[i]['forks_count']
        # Num of stars on repo
        star_watcher_count = output_file[i]['stargazers_count']
        # Source: https://docs.github.com/en/rest/activity/starring?apiVersion=2022-11-28#starring-versus-watching
        # Coding Language
        repo_language = output_file[i]['language']
        # Num of open issues
        num_open_issues = output_file[i]['open_issues_count']
        # Has the repo already been archived
        is_archived = output_file[i]['archived']
        # updated anytime commit is pushed to repo's branches
        last_push_time = output_file[i]['pushed_at']
        # when the repo was created
        created_time = output_file[i]['created_at']
        # updated any time repo object changed
        last_update_time = output_file[i]['updated_at']
        # Source: https://github.com/orgs/community/discussions/24442

        # Collecting information on any open pull requests in a repo
        num_open_pull_requests = collect_data_on_pull_requests(organization_name,
                                                               repo_name,
                                                               headers_input)

        # Calling function to calculate the score for whether the repo should
        # be archived or not
        total_score = calculate_archiving_score(num_open_issues,
                                                num_open_pull_requests,
                                                star_watcher_count,
                                                num_forks,
                                                last_push_time)
        rounded_score = round(total_score, 1)  # Rounding to ensure consistency

        # Create a row in the dataframe tracking all repos of an organization
        df.loc[len(df)] = [repo_name, repo_id, repo_url,
                           repo_description, is_fork, num_forks,
                           star_watcher_count, repo_language,
                           num_open_issues, is_archived,
                           last_push_time, created_time,
                           last_update_time,
                           num_open_pull_requests,
                           rounded_score]

    return df
