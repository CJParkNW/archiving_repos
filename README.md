# Overview of Project
The main objective of this assignment is to develop code that provides an interactive summary or visualization that helps organizations determine which of its public repositories could/should be archived.

## Background
[Archiving repositories](https://docs.github.com/en/organizations/managing-organization-settings/archiving-an-organization) is a core part of maintaining code/technology that may no longer be relevant, but still beneficial to have as reference. By archiving, repositories become read-only for all users and indicates to a user that it is no longer actively maintained.

However, after some time it can become difficult to actively review and determine whether a repository should be archived or not. There are several factors that can impact whether a repository should be archived, such as: current issues, pull requests, change/commit history, influence, etc. If a repository is archived without consideration of this, there is a risk of needing to edit files/documentation associated with the repository in the future which can no longer be changed unless someone with access reverses archiving and allows these changes.

## Major Decisions in this Project
- In order to properly determine whether a repository can be archived, a set of standards across all repositories had to be set.
This standard led to a scale from 0.0 to 1.0 where 1.0 indicates that a repository should be archived. This was determined by the following qualities:
    1. Whether there are any active/open issues.
    2. Whether there are any active/open pull requests.
    3. Are there a substantial number of stars on this repository?
    4. Have there been a substantial number of forks based on this repository?
    5. Was the last change that was pushed in recent? Or has it been more than 6 months or a year ago?
- Each of these points can be answered with data from the REST API endpoint which was then used to score a repository on whether it should be archived. This allows for direct comparison across all repositories, while also taking into consideration a variety of factors/reasons why someone may wish to archive a repository.

- From there a set of interactive visualizations were created. When considering the overall organization, telling a story on the kinds of repositories that there are (coding language) and repositories with high activity provides good context as to what a repository that needs to be archived would not look like. Additionally, graphs directly demonstrating changes/activity over time for a repository can provide supplemental evidence as to why a repository should or should not be archived.

- This was all pulled together on a dash web-app. A web-app gives more options to the user for interaction and a cohesive experience. By utilizing a tab/navigation system as well as guiding a viewer through an organization's journey, they are given more of a user-friendly chance to understand archiving repositories.

## How to Run this Project
In order to run and access the visualizations for this project, please ensure the following:
- Ensure that any modules that need to be installed or updated as listed in the Dependencies is done so.
- While an API key is not necessary, it is beneficial to have one since it will increase the rate limits allowed for the REST API. If you proceed with [creating an API key](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28), please ensure that it has permissions to allow access to the following endpoints. 
    - [Get Weekly Commit Activity](https://docs.github.com/en/rest/metrics/statistics?apiVersion=2022-11-28#get-the-weekly-commit-activity)
    - [Get Weekly Commit Count](https://docs.github.com/en/rest/metrics/statistics?apiVersion=2022-11-28#get-the-weekly-commit-count)
    - [List Organization Repositories](https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#list-organization-repositories)
- Create an .env file with the following:
```
# API Key for GitHub REST API
GITHUB_API_KEY = <Fill in API Key>
```
- Navigate to the folder archive_web_app and run the script app.py.
```
python app.py
```
- Please give the web application a few minutes to load. Due to the data that is being processed from the REST API endpoints, it may take some time to load all of the data and the UI. Once the web app is finished loading, you will be asked to navigate to the server http://127.0.0.1:8050 where the UI should now be loaded.
    - While currently, no user input is needed to work this web application, if you would like to explore other organizations or repositories, please feel free to experiment with the following variables in the app.py script.
```
# Setting the organization and repo to deep dive into
# Change the input on lines 26 to 29 if you would like to investigate other organizations or repositories.
ORG_NAME = 'brown-ccv'
REPO_NAME = 'honeycomb'
```

### Dependencies
- Python v.3.13.0
    - python-dotenv v.1.0.1
    - dash v.2.18.2
    - dash_bootstrap_components v.1.6.0
    - pillow v.11.0.0 
    - plotly v.5.24.1
    - requests v.2.25.1
    - pandas v.2.2.3

## Future Steps
Originally, this web-app was planned with more user interaction which could not be implemented due to limitations in code and time constraints.
- Primarily, I was interested in being able to add options for filtering and a dropdown menu for selecting a repository to deep dive into. This would allow for a user to review what repositories should be archived or not directly from the UI rather than having to reload it through the code itself.
    - Search bar for Organization Name on Overview Page
    - Filter Options by Coding Language and Creation/Updated Date for Overview Page
    - Dropdown menu for all repositories in an organization when doing a deep dive.
- Additionally, I was interested in exploring potential alternatives to the REST API due to limitations that were faced with loading times as well as the formatting of data. Some data that were pulled from the endpoint was unnecessary, but could not be manually excluded. the [GraphQL API](https://docs.github.com/en/graphql/overview/about-the-graphql-api) provides a greater change to customize requests/data collected which may speed up loading times and increase what kind of visualizations can be made/metrics. 