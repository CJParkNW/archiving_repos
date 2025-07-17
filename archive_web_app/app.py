"""
Building web app to create a more user-friendly/cohesive experience
while attempting to determine what GitHub Repos should be archived in an
organization.
"""

# Import packages
import os
from dotenv import load_dotenv
from dash import Dash, html, Output, Input, dcc
import dash_bootstrap_components as dbc
from PIL import Image
# Importing in modules
import transform_data as td
import create_visualizations as c_viz


# Loading in env variables from .env file for API Key
load_dotenv()
# Setting up the headers with API token to increase rate limit
# for GitHub REST API when making requests
HEADERS = {
    "Authorization": f"token {os.getenv('GITHUB_API_KEY')}"
}

# Setting the organization and repo to deep dive into
# Change the input here if you would like to investigate other orgs
ORG_NAME = 'plotly'
REPO_NAME = 'plotly.py'

# Temporary message for terminal -- To show that the UI is loading.
print("Loading...Please Wait...")

# Calls functions for the REST API to collect data on the repos in the org.
df_repos = td.create_entire_repo_dataframe(ORG_NAME, HEADERS)

# Generates visualizations to provide overview of organization and
# activity in a repository
fig_1 = c_viz.create_chart_per_language(df_repos)
fig_2 = c_viz.create_chart_top_repos_w_issues(df_repos)
fig_3 = c_viz.create_chart_top_repos_w_pull_requests(df_repos)
fig_4 = c_viz.create_chart_distribution_of_scores(df_repos)
fig_5 = c_viz.plot_all_code_frequency(ORG_NAME, REPO_NAME, HEADERS)
fig_6 = c_viz.request_data_participation(ORG_NAME, REPO_NAME, HEADERS)

# Extract out the top 10 repositories that can be archived (to display on UI)
sample_top_10_repos_to_archive = df_repos[['name', 'description',
                                           'last_push_time',
                                           'overall_score']][df_repos['is_archived'] == False].sort_values('overall_score',
                                                                                                             ascending = False).head(10)


# Take the dataframe for the top 10 repositories and create an interactive table
top_table_archive = dbc.Table.from_dataframe(sample_top_10_repos_to_archive,
                                             striped=True, bordered=True,
                                             hover=True)
# Extract out the data on the single repo that will be investigated further.
row_repo_deep_dive = df_repos.loc[df_repos['name'] == REPO_NAME].reset_index()

# Calling image for About Us page
github_logo_path = Image.open("images/github-mark.png")

# Initialize the app with external theme
app = Dash(external_stylesheets=[dbc.themes.UNITED])

# Building components on Web App/Dashboard
# The standard style arguments for the sidebar.
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "18rem",
    "padding": "2rem 1rem",
    "background-color": "#782c54",
    "color": 'white'
}

# The style for the main content to the right of the sidebar.
CONTENT_STYLE = {
    "margin-left": "22rem",
    "margin-right": "6rem",
    "padding": "2rem 1rem",
    "color": 'black'
}

# Build the structure of the side bar.
sidebar = html.Div(
    [html.H2("Archiving GitHub Repos", className="display-4"),
     html.Hr(),
     html.P("""Determine what repos should be archived with a
            few simple visualizations and metrics!"""),
        # Create different navigation tabs to display different data.
        dbc.Nav(
            [dbc.NavLink("Overview", href="/", active="exact"),
             dbc.NavLink("Repo Deep Dive", href="/deep-dive", active="exact"),
             dbc.NavLink("About this Tool", href="/about", active="exact")],
            vertical=True,
            pills=True),  # dbc.Nav()
     ],  # html.Div([])
    style=SIDEBAR_STYLE,
    )  # html.Div()

content = html.Div(id="page-content", style=CONTENT_STYLE)
app.layout = html.Div([dcc.Location(id="url"), sidebar, content])

# Create button to download the entire dataframe for all of the repos in an
# organization if the user would like to view it.
button_to_download = html.Div(
    [html.Button("Download All Data as CSV",
                 id="btn_csv"),
     dcc.Download(id="download-dataframe-csv"),]
)  # html.Div()

# Creates the structure for the main overview navigation page.
overview_content = (
    html.H1(f"Overview of Organization: {ORG_NAME}"),
    html.P(),
    html.Hr(),
    html.P("""The following table demonstrates a sample of repositories that
           have been deemed as acceptable to archive. This can be seen by an
           overall_score leaning/equivalent towards 1 on a scale from 0.0
           (likely unacceptable to archive) to 1.0 (likely acceptable to
           archive). While the table displays some data both calculated and
           extracted from the GitHub REST API, it is highly recommended to
           Download the entire CSV and review other repositories."""),
    # Adds in button for downloading csv.
    button_to_download,
    html.P(),
    html.Div([
        dbc.Row([
            dbc.Col(top_table_archive, width='auto'),
            html.Hr(),
            html.H1(f"Interactive Visualizations on {ORG_NAME}"),
            dbc.Col(dcc.Graph(figure=fig_1), width='auto')]),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_2), width='auto'),
            dbc.Col(dcc.Graph(figure=fig_3), width='auto')]),
        ])  # html.Div()
)  # overview_content

# Creates the structure for the deep dive repo page
deep_dive_content = (
    html.H1(f"Repository Deep Dive for {REPO_NAME}"),
    html.Hr(),
    html.H4(f"This repository is described to do the following: {row_repo_deep_dive['description'][0]}"),
    html.P("""When determining what criteria should be used for understanding
           whether a repository should be archived or not, there is a key
           component to understand."""),
    html.P("""Even if a repository has not been updated recently,
           it is important to ensure that any open issues or pull requests
           are closed. Otherwise, you run the risk of leaving these issues
           and pull requests in collaborator's accounts forever (with no way
           to edit them unless if the repo is unarchived again). Commits or
           changes made in the past year may be a huge determining factor for
           whether a repository should be archived, but other metrics are
           essential to review as well. While the history of a repository's
           changes may tell us a lot, it is not the only part of the story."""),
    html.Hr(),
    html.Div(
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_5), width='auto'),
            dbc.Col(dcc.Graph(figure=fig_6), width='auto')
        ])  # dbc.Row()
        ),  # html.Div()
    html.Hr(),
    html.H4(f"Access this repository at the following link: {row_repo_deep_dive['url'][0]}"),
    )  # deep_dive_content

# Creates the structure for the about page
about_content = (
    html.H1("About this Tool"),
    html.Hr(),
    html.P("""As organizations on GitHub grow, maintaining and cleaning all
           existing repositories can become an extensive task since each
           repository holds a unique role with various sets of files, history,
           and collaborators. It is imperative to communicate publicly whether
           a repository is kept updated or is no longer actively maintained for
           future users. Archiving provides an alternative to permanently
           deleting repositories where it indicates that a repository is
           read-only and is no longer actively maintained."""),
    html.P("""Prior to archiving a repository in GitHub, it is essential to
           determine if the repository is fit to be archived. It is highly
           recommended to close all issues and pull requests as well as provide
           an update on the repository itself before archiving. Editing any
           part of an archived repository (issues, pull requests, code, labels,
           milestones, projects, wiki, etc.) is only possible to do if you
           unarchive the repository first."""),
    html.P("""However, due to the number of repositories an organization can
           have, it can become difficult to track what repositories would be
           ideal for archiving. Therefore, having a tool (such as this one!)
           that can pick up the top repositories that should be archived based
           on a set of standards supported by various visualizations can help
           easily pick up the ideal repositories to review and archive."""),
    html.Hr(),
    html.P("""Please feel free to test out this (unofficial) tool for your
           organization today!"""),
    html.Img(src=github_logo_path, width="100", height="100")
)  # about_content


@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    """Provides interactive functionality to the navigation tabs"""
    if pathname == "/":
        return overview_content
    elif pathname == "/deep-dive":
        return deep_dive_content
    elif pathname == "/about":
        return about_content


@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("btn_csv", "n_clicks"),
    prevent_initial_call=True,
)
def func(n_clicks):
    """Provides interactive functionality for the download button to allow the
    user to extract ou the most vital data on their organization's repos
    and the metric used to score whether they should be archived."""
    return dcc.send_data_frame(df_repos.to_csv,
                               "export_repos_archive_data.csv")


if __name__ == "__main__":
    app.run()
