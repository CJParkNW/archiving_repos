# Overview of Project
By using this web app, users can have an interactive visual summary that helps their organization determine which of its public repositories should be archived while also submitting data to Datadog for better monitoring.

## Background
[Archiving repositories](https://docs.github.com/en/organizations/managing-organization-settings/archiving-an-organization) is a core part of maintaining code/technology in an organization that may no longer be relevant to work on, but still beneficial to have as reference. By archiving, repositories become read-only for all users and explicitly indicates to a user that it is no longer actively maintained.

However, after some time it can become difficult and labor-intensive to actively review and determine whether a repository should be archived or not. There are several factors that can impact whether a repository should be archived, such as: current issues, pull requests, change/commit history, influence, etc. If a repository is archived without consideration of this, there is a risk of needing to edit files/documentation associated with the repository in the future which can no longer be changed unless someone with access reverses archiving and allows these changes.

## How to Run this Project
In order to run and access the visualizations for this project, please ensure the following:
- Ensure that any modules that need to be installed or updated as listed in the Dependencies is done so.
- Please proceed with [creating an API key](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28), and ensure that it has permissions to allow to the REST API endpoints. 
- If you would like to submit data to Datadog, please also create an API key.
- Create an .env file with the following:
```
# API Key for GitHub REST API
GITHUB_API_KEY = <Fill in API Key>
DATADOG_API_KEY = <Fill in API Key>
```
- Navigate to the folder archive_web_app and run the script app.py and load the server: http://127.0.0.1:8050 
```
python app.py
```

The following defaults are set for the UI:
ORG_NAME = 'plotly'
REPO_NAME = 'plotly.py'


### Dependencies
- Python v.3.13.0
    - APScheduler v.3.11.2
    - dash v.3.1.1
    - dash_bootstrap_components v.2.0.3
    - datadog v.0.52.1
    - pandas v.2.3.1
    - pillow v.11.3.0 
    - plotly v.6.2.0
    - pytest v.9.0.3
    - python-dotenv v.1.1.1
    - requests v.2.32.4