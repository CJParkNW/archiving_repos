"""
Building web app to create a more user-friendly/cohesive experience
while attempting to determine what GitHub Repos should be archived in an
organization.
"""

import math
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from dash import Dash, html, Output, Input, State, dcc, callback_context, dash_table
import dash_bootstrap_components as dbc
from PIL import Image
import create_visualizations as c_viz
import database as db
import pipeline


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

# Refresh time estimate constants
SECONDS_PER_REPO = 0.37   # empirical: observed ~83s for 226 repos
ESTIMATE_ROUND_UP_SECONDS = 30  # round up to nearest N seconds for display

# Ensure the DB and schema exist on startup
db.init_db()

# Temporary message for terminal -- To show that the UI is loading.
print("Loading...Please Wait...")

# Load repo data from SQLite (run pipeline first if DB is empty)
df_repos = db.read_repos(ORG_NAME)
if df_repos.empty:
    print("No cached data found — running pipeline to populate database...")
    df_repos = pipeline.run(ORG_NAME)

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
app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Store(id="repos-store"),  # holds refreshed df as JSON
    sidebar,
    content
])


def build_freshness_bar(org: str):
    """Build the data freshness indicator + refresh button row."""
    last_fetched = db.get_last_fetched(org)
    if last_fetched:
        fetched_dt = datetime.strptime(last_fetched, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        delta = datetime.now(timezone.utc) - fetched_dt
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        if hours > 0:
            freshness_text = f"Last updated {hours} hour{'s' if hours != 1 else ''} ago"
        else:
            freshness_text = f"Last updated {minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        freshness_text = "No data cached yet"

    # Estimate refresh duration: ~0.37s per repo, rounded up to next 30s.
    # Falls back to a generic warning if no data is cached for this org yet.
    num_repos = len(db.read_repos(org))
    if num_repos == 0:
        est_label = "unknown — no cached data for this org"
    else:
        est_sec = math.ceil(
            num_repos * SECONDS_PER_REPO / ESTIMATE_ROUND_UP_SECONDS
        ) * ESTIMATE_ROUND_UP_SECONDS
        if est_sec >= 60:
            m, s = divmod(est_sec, 60)
            est_label = f"~{m}m {s}s" if s else f"~{m}m"
        else:
            est_label = f"~{est_sec}s"

    return dbc.Row(
        [
            dbc.Col(
                html.Span(freshness_text, id="freshness-label",
                          style={"fontSize": "0.85rem", "color": "#666",
                                 "lineHeight": "36px"}),
                width="auto"
            ),
            dbc.Col(
                dbc.Button("Refresh Data", id="refresh-btn", color="secondary",
                           size="sm", className="ms-2"),
                width="auto"
            ),
            dbc.Col(
                html.Span(f"est. {est_label}",
                          style={"fontSize": "0.78rem", "color": "#999",
                                 "lineHeight": "36px"}),
                width="auto"
            ),
            dbc.Col(
                dcc.Loading(
                    html.Div(id="refresh-status"),
                    type="circle",
                    color="#782c54",
                ),
                width="auto"
            ),
        ],
        align="center",
        className="mb-3"
    )


def build_overview(df):
    """Build the overview page content from a dataframe."""
    fig_1 = c_viz.create_chart_per_language(df)
    fig_2 = c_viz.create_chart_top_repos_w_issues(df)
    fig_3 = c_viz.create_chart_top_repos_w_pull_requests(df)
    fig_score = c_viz.create_chart_top_repos_by_score(df)

    table_df = (
        df[~df['is_archived'].astype(bool)]
        .sort_values('overall_score', ascending=False)
        [['name', 'overall_score', 'num_open_issues',
          'num_open_pull_requests', 'num_star_watchers',
          'num_forks', 'last_push_time']]
    )

    repo_table = dash_table.DataTable(
        data=table_df.to_dict('records'),
        columns=[
            {"name": "Repo",        "id": "name"},
            {"name": "Score",       "id": "overall_score"},
            {"name": "Open Issues", "id": "num_open_issues"},
            {"name": "Open PRs",    "id": "num_open_pull_requests"},
            {"name": "Stars",       "id": "num_star_watchers"},
            {"name": "Forks",       "id": "num_forks"},
            {"name": "Last Push",   "id": "last_push_time"},
        ],
        sort_action="native",
        page_size=20,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#782c54",
            "color": "white",
            "fontWeight": "bold",
            "textAlign": "left",
        },
        style_cell={
            "textAlign": "left",
            "padding": "8px",
            "fontFamily": "sans-serif",
            "fontSize": "13px",
            "maxWidth": "220px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_data_conditional=[
            {
                "if": {"filter_query": "{overall_score} >= 0.8"},
                "backgroundColor": "#d4edda",
                "color": "#155724",
            },
            {
                "if": {
                    "filter_query": "{overall_score} >= 0.4 && {overall_score} < 0.8"
                },
                "backgroundColor": "#fff3cd",
                "color": "#856404",
            },
            {
                "if": {"filter_query": "{overall_score} < 0.4"},
                "backgroundColor": "#f8d7da",
                "color": "#721c24",
            },
        ],
        tooltip_data=[
            {"name": {"value": row["name"], "type": "markdown"}}
            for row in table_df.to_dict("records")
        ],
        tooltip_duration=None,
    )

    button_to_download = html.Div([
        html.Button("Download All Data as CSV", id="btn_csv"),
        dcc.Download(id="download-dataframe-csv"),
    ])

    return dbc.Container([
        dbc.Row(
            [
                dbc.Col(
                    html.H2(f"Overview — {ORG_NAME}", className="mb-0"),
                    width=True,
                ),
                dbc.Col(
                    build_freshness_bar(ORG_NAME),
                    width="auto",
                ),
            ],
            align="center",
            className="py-3 border-bottom mb-3",
        ),
        html.P("""The following table shows all unarchived repositories scored
               from 0.0 (keep) to 1.0 (archive). Rows are color-coded:
               green = strong archive candidate, yellow = moderate,
               red = likely keep. Click any column header to sort."""),
        button_to_download,
        html.P(),
        dbc.Row([dbc.Col(repo_table)]),
        html.Hr(),
        html.H4(f"Visualizations — {ORG_NAME}", className="mb-3"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_score), width="auto"),
            dbc.Col(dcc.Graph(figure=fig_1), width="auto"),
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_2), width="auto"),
            dbc.Col(dcc.Graph(figure=fig_3), width="auto"),
        ]),
    ], fluid=True)


# Creates the structure for the deep dive repo page
def build_deep_dive(df):
    """Build the deep dive page content from a dataframe."""
    fig_5 = c_viz.plot_all_code_frequency(ORG_NAME, REPO_NAME, HEADERS)
    fig_6 = c_viz.request_data_participation(ORG_NAME, REPO_NAME, HEADERS)
    row_repo = df.loc[df['name'] == REPO_NAME].reset_index()

    return dbc.Container([
        dbc.Row(
            dbc.Col(html.H2(f"Deep Dive — {REPO_NAME}", className="mb-0")),
            className="py-3 border-bottom mb-3",
        ),
        html.P(f"Description: {row_repo['description'][0]}"),
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
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_5), width="auto"),
            dbc.Col(dcc.Graph(figure=fig_6), width="auto"),
        ]),
        html.Hr(),
        html.P([
            "View on GitHub: ",
            html.A(row_repo['url'][0], href=row_repo['url'][0],
                   target="_blank"),
        ]),
    ], fluid=True)


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
)


@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    """Provides interactive functionality to the navigation tabs."""
    current_df = db.read_repos(ORG_NAME)
    if current_df.empty:
        current_df = df_repos  # fall back to startup data

    if pathname == "/":
        return build_overview(current_df)
    elif pathname == "/deep-dive":
        return build_deep_dive(current_df)
    elif pathname == "/about":
        return about_content


@app.callback(
    Output("refresh-status", "children"),
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=True,
)
def refresh_data(n_clicks):
    """Re-run the pipeline and refresh the database when the button is clicked."""
    if not n_clicks:
        return ""
    start = time.time()
    pipeline.run(ORG_NAME)
    elapsed = int(time.time() - start)
    m, s = divmod(elapsed, 60)
    elapsed_text = f"{m}m {s}s" if m else f"{s}s"
    return html.Span(
        f"Refreshed! ({elapsed_text})",
        style={"color": "green", "fontSize": "0.85rem"}
    )


@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("btn_csv", "n_clicks"),
    prevent_initial_call=True,
)
def download_csv(n_clicks):
    """Allow the user to download the full dataset as a CSV."""
    current_df = db.read_repos(ORG_NAME)
    return dcc.send_data_frame(current_df.to_csv, "export_repos_archive_data.csv")


if __name__ == "__main__":
    app.run()
