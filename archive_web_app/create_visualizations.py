"""
This module allows you to create dynamic/interactive visualizations
representing the status of an organization's repositories as well as the
history of each individual repository.
"""

from datetime import datetime
from time import sleep
import plotly.express as px
# Color Palette - Prism
# Source: https://plotly.com/python/discrete-color/
import requests
import pandas as pd

MAX_TIMEOUT = 600  # 10 min timeout due to caching data taking some time


def create_chart_per_language(df):
    """
    Use the provided dataframe on an organizations GitHub data to plot a pie
    chart representing the distribution of coding languages amongst all
    of the repos (that have access to this data).

    Args:
        df: Pandas dataframe that contains the organization's repo data

    Returns:
        fig: plotly.express figure - Pie chart that represents distributions
    """
    # Take the provided dataframe on the organization and extract out the total
    # number of repos per coding language
    df_distr = df.groupby(['language']).size().reset_index(name='total_per_lang')
    # Extract the total repos that currently have language data points
    # This value may be different from the total repos that are in the df
    total_repos = sum(df_distr['total_per_lang'])

    # Add a new column to the df_distr where it calculates the percentage that
    # a coding language makes up an organization's set of repos
    df_distr['percent_language'] = df_distr.apply(divide_by_total_repos,
                                                  axis=1,
                                                  args=[total_repos])

    # Set up and create a pie chart representing distribution
    # with standard settings.
    fig = px.pie(df_distr, values='percent_language', names='language',
                 # Source: https://plotly.com/python/pie-charts/
                 color_discrete_sequence=px.colors.qualitative.Prism,
                 title="Overall Distribution of Coding Languages",
                 width=800,
                 height=600)

    return fig


def divide_by_total_repos(row, total) -> float:
    """
    FOR INTERNAL USE ONLY (with create_chart_per_language()).
    This function calculates the percentage in repos that are within a certain
    coding language. This function allows for this calculation to be applied
    to every row (each language) in a dataframe.

    Args:
        row: A row from the pandas dataframe
        total: Total number of repos in an organization that has coding
        language data

    Returns:
        Percentage of repos that are using that coding language in the row.
    """
    # Calculate percentage and return to the proper row
    percent = (row['total_per_lang']/total) * 100
    return round(percent, 1)


def create_chart_top_repos_w_issues(df):
    """
    Create a bar graph representing the top 10 repos in an organization with
    the most open issues.

    Args:
        df: Pandas dataframe that contains the organization's repo data

    Returns:
        fig: plotly.express figure - Bar graph that represents top 10
        repos with the most open issues.
    """
    # Create a dataframe that extracts out the top 10 repos with the most
    # open issues
    top_10_open_issues = df[['name', 'num_open_issues']].sort_values('num_open_issues',
                                                                     ascending=False).head(10)

    # Set up and create a bar graph representing top repos with open issues
    # with standard settings.
    fig = px.bar(top_10_open_issues, x='name', y='num_open_issues',
                 title='Top 10 Repos with the Most Open Issues',
                 color_discrete_sequence=[px.colors.qualitative.Prism[0]],
                 labels={"num_open_issues": 'Number of Open Issues',
                         "name": "Repository Name"},
                 width=800,
                 height=600)

    return fig


def create_chart_top_repos_w_pull_requests(df):
    """
    Create a bar graph representing the top 10 repos in an organization with
    the most open pull requests.

    Args:
        df: Pandas dataframe that contains the organization's repo data

    Returns:
        fig: plotly.express figure - Bar graph that represents top 10
        repos with the most open pull requests.
    """

    # Create a dataframe that extracts out the top 10 repos with the most
    # open issues.
    top_10_open_prs = df[['name',
                          'num_open_pull_requests']].sort_values('num_open_pull_requests',
                                                                 ascending=False).head(10)

    # Set up and create a bar graph representing top repos with open pull
    # requests with standard settings.
    fig = px.bar(top_10_open_prs, x='name', y='num_open_pull_requests',
                 title='Top 10 Repos with the Most Open Pull Requests',
                 color_discrete_sequence=[px.colors.qualitative.Prism[8]],
                 labels={"num_open_pull_requests": 'Number of Open Pull Requests',
                         "name": "Repository Name"},
                 width=800,
                 height=600)

    return fig


def create_chart_top_repos_by_score(df):
    """
    Create a horizontal bar chart of the top 20 unarchived repos by
    archiving score, highest score at the top.

    Args:
        df: Pandas dataframe that contains the organization's repo data

    Returns:
        fig: plotly.express figure - horizontal bar chart
    """
    top_20 = (
        df[~df['is_archived'].astype(bool)]
        .sort_values('overall_score', ascending=False)
        .head(20)
        .sort_values('overall_score', ascending=True)  # highest at top
    )

    fig = px.bar(
        top_20,
        x='overall_score',
        y='name',
        orientation='h',
        title='Top 20 Archive Candidates by Score',
        color='overall_score',
        color_continuous_scale=[
            [0, '#f8d7da'], [0.5, '#fff3cd'], [1, '#d4edda']
        ],
        range_x=[0, 1],
        labels={
            'overall_score': 'Archiving Score (0 = keep, 1 = archive)',
            'name': 'Repository',
        },
        width=800,
        height=600,
    )
    fig.update_coloraxes(showscale=False)
    fig.update_layout(yaxis_title=None)
    return fig


def create_chart_distribution_of_scores(df):
    """
    Create a histogram representing the distribution of scores across all
    repositories in an organization

    Args:
        df: Pandas dataframe that contains the organization's repo data

    Returns:
        fig: plotly.express figure - Histogram that represents the distribution
        of scores in the entire organization.
    """
    # Set up and create a histogram representing the distribution of
    # scores across an organization's repos.
    fig = px.histogram(df, x="overall_score",
                       title="Distribution of Repositories by Archiving Score",
                       color_discrete_sequence=[px.colors.qualitative.Prism[2]],
                       labels={"count": "Number of Repos",
                               "overall_score": "Score for Archiving Repository"},
                       width=800,
                       height=600)

    return fig


def plot_all_code_frequency(organization_name: str, repo_name: str,
                            headers_input: dict):
    """
    Create a line graph representing the total additions/deletions over the time
    that a repository has been worked on.

    Args:
        organization_name: Organization that is looked at in the API endpoint
        repository_name: Repo that is looked at in the API endpoint

    Returns:
        fig: plotly.express figure - Line graph that represents the changes
        over time in a repository.
    """
    # Call recursively until the cached data from this endpoint is properly
    # filling out the dataframe
    request_data_code_frequency(organization_name, repo_name, headers_input)
    # Once the function returns, this will indicate that the endpoint is ready
    # to be pulled on the repository.
    # Pull endpoint one more time to ensure data is properly extracted
    r = requests.get(f'https://api.github.com/repos/{organization_name}/{repo_name}/stats/code_frequency',
                     headers=headers_input,
                     timeout=MAX_TIMEOUT)
    output_file = r.json()

    # Create a dataframe containing the commit history (additions/deletions)
    # over a repository's entire history.
    df_repo_commit_history = pd.DataFrame(columns=['week_epoch',
                                                   'converted_time',
                                                   'additions', 'deletions'])

    # Iterate through the entire endpoint output and extract out the total
    # changes by time stamp.
    for i in enumerate(output_file):
        index = i[0]
        # Time is originally in epoch which is converted to a readable timestamp
        week_time_in_epoch = output_file[index][0]
        timestamp = pd.to_datetime(week_time_in_epoch, unit='s')
        num_of_additions = output_file[index][1]
        num_of_deletions = output_file[index][2]
        # Fill up the dataframe for plotting
        df_repo_commit_history.loc[len(df_repo_commit_history)] = [week_time_in_epoch,
                                                                   timestamp,
                                                                   num_of_additions,
                                                                   num_of_deletions]

    # Set up and create a line graph representing the changes made (commits) to
    # a repository since creation.
    fig = px.line(df_repo_commit_history, x="converted_time", y="additions",
                  # Source: https://plotly.com/python/dot-plots/
                  title="History of all Additions Pushed to the Repository",
                  color_discrete_sequence=[px.colors.qualitative.Prism[3]],
                  labels={'additions': 'Total Additions from Commits',
                          'converted_time': 'Time'},
                  width=800,
                  height=600)

    return fig
    # Source: https://docs.github.com/en/rest/metrics/statistics?apiVersion=2022-11-28#get-the-weekly-commit-activity


def request_data_code_frequency(organization_name: str, repo_name: str,
                                headers_input: dict):
    """
    FOR INTERNAL USE ONLY (For plot_all_code_frequency()). Used to keep checking
    an API endpoint for the entire data since this endpoint takes longer
    than other data to load. Continues to iterate through until data is
    available or if the timeout is surpassed (whichever comes first).
    # Source: https://docs.github.com/en/rest/metrics/statistics?apiVersion=2022-11-28#best-practices-for-caching

    Args:
        organization_name: Organization that is looked at in the API endpoint
        repository_name: Repo that is looked at in the API endpoint

    Returns:
        None - Exit function once data begins to load in order for the
        plot_all_code_frequency() to be able to properly create the line graph.
    """
    # Call API endpoint to check if the cached data is ready to pull
    r = requests.get(f'https://api.github.com/repos/{organization_name}/{repo_name}/stats/code_frequency',
                     headers=headers_input,
                     timeout=MAX_TIMEOUT)
    # Convert to JSON to check on file
    file = r.json()

    # If there is no data/file is empty
    if not file:
        # Wait 10 seconds before running a pull to the endpoint again.
        sleep(10)
        request_data_code_frequency(organization_name, repo_name, headers_input)
    # If data has been successfully detected, exit this function
    else:
        return


def request_data_participation(organization_name: str, repo_name: str,
                               headers_input: dict):
    """
    Create a line graph representing the total participation/commits from all
    collaborators in a repository in the past 52 weeks.

    Args:
        organization_name: Organization that is looked at in the API endpoint
        repository_name: Repo that is looked at in the API endpoint

    Returns:
        fig: plotly.express figure - Line graph that represents the total
        commits over the past year in a repository.
    """
    # Pull API endpoint to extract out data on a repository's commits
    # in the past year.
    r = requests.get(f'https://api.github.com/repos/{organization_name}/{repo_name}/stats/participation',
                     headers=headers_input,
                     timeout=MAX_TIMEOUT)
    output_file = r.json()

    # Calculate epoch time of today in order to figure out when data collection
    # was first done
    today_epoch = datetime.now().timestamp()  # Get current timestamp
    epoch_per_week = 86400 * 7  # Calculate epoch time for a week
    epoch_per_year = epoch_per_week * 52  # Calculate epoch time for a year

    start = today_epoch - epoch_per_year  # Calculate the start time for data

    # Create a dataframe to keep track of the repo's history in the past year
    df_all_weekly_commit_count = pd.DataFrame(columns=['epoch',
                                                       'converted_time',
                                                       'commit_count'])

    # Iterate through only the values of the endpoint that totals the
    # changes made by all collaborators in the past year
    for i in range(len(output_file['all'])):
        # Start at the earliest time (a year ago)
        epoch_time_of_commit = start + epoch_per_week*i
        # Convert to a readable timestamp and extract out the associated point
        timestamp = pd.to_datetime(epoch_time_of_commit, unit='s')
        num_of_commits = output_file['all'][i]

        # Extract out data on the commits made for a repo over time.
        df_all_weekly_commit_count.loc[len(df_all_weekly_commit_count)] = [epoch_time_of_commit,
                                                                           timestamp,
                                                                           num_of_commits]

    # Set up and create a line graph representing the changes made (commits) to
    # a repository over the past year (all collaborators).
    fig = px.line(df_all_weekly_commit_count, x="converted_time",
                  y="commit_count",
                  title="Total Commits over the Past Year",
                  color_discrete_sequence=[px.colors.qualitative.Prism[4]],
                  labels={'commit_count': 'Total Commits',
                          'converted_time': 'Time'},
                  width=800,
                  height=600)

    return fig
