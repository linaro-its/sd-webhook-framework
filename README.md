[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=linaro-its_sd-webhook-framework&metric=alert_status)](https://sonarcloud.io/dashboard?id=linaro-its_sd-webhook-framework)

# Introduction

This repository provides a foundation for supporting webhook automation with Atlassian's Jira Service Desk. The aim of the framework is to provide a high quality foundation for providing webhook extensions to request types on Service Desk while  reducing the amount of code needed to be written. The framework provides the core webhook handling code plus common functions for interacting with Service Desk and LDAP, thus allowing the handlers for each request type to focus on the "business logic" required.

## What the framework supports

The framework can be triggered by the following actions:

* Creation of a ticket
* Comment added to a ticket
* Assignment change on a ticket
* Status change on a ticket

The first two actions are triggered by Service Desk webhooks. The last two actions are triggered by Jira webhooks.

Each *request type* has its own code file. The main code loads the code file appropriate to the ticket being handled.

Since the webhooks can be generic across all of the issue/request types, each code file has a CAPABILITIES section that the main code queries in order to determine whether or not the code can support the desired action, e.g.:

    CAPABILITIES = [ "CREATE", "ASSIGNMENT" ]

The sample test handler `rt_example_handler.py` lists all of the supported transition names. Handlers used by Linaro can be found in https://github.com/linaro-its/sd-webhook-handlers.

## Installation

Development of the code is done using a Pipenv-maintained virtual environment. The required modules are listed in `Pipfile` and can be installed with:

    pipenv install

Note that Python 3 is **required**.

## Code execution

On a development system, [Flask](http://flask.pocoo.org) is used to run the code. In production, you can either use something like Apache with a WSGI handler or [Chalice](https://github.com/aws/chalice/). Currently, WSGI is easier to use as it doesn't require any code modifications, but Chalice allows the code to be run serverless. To make it easier to use the framework with WSGI, this repository includes the files and configuration required to build a Docker container for running everything. See [WSGI](WSGI.md) for more details about how to use the Docker container.

## Webhook Configuration

For full functionality, both Jira and Service Desk webhooks need to be configured. If none of the request type handlers support assignment or status changes, it is safe to omit the Jira webhook since it will never be fired.

In the text below, `<base URL>` is the URL that is mapped onto the framework web service. If the framework is being run on the same server as Jira Service Desk, this could be (for example) `http://localhost:8000`.

### Service Desk webhook

The Service Desk webhook is created through the Automation rules for a given SD project. Generally, two rules are required:

* When: Issue Created
   * Then: Webhook
   * URL: `<base URL>`/create
   * Include payload in request body
* When: Comment Added
   * Then: Webhook
   * URL: `<base URL>`/comment
   * Include payload in request body

You can use the `IF` clause to only fire when request types matching those supported by the webhook are affected. This is done by adding an `Issue matches` clause with JQL like this:

    "Customer Request Type" = "Name of the request type"

Note that if you change the name of the request type, you **must** update the JQL clause to match otherwise it will not fire. The clause does not get updated automatically.

Note that the framework will work out which request type has been used, so it is safe to omit the `IF` clause, with the understanding that the framework will be called for *all* issues created and commented on.

### Jira webhook

Create a WebHook in Jira with the following settings:

* URL: `<base URL>`/jira-hook
* Events: Issue>updated

The framework looks at the data sent by Jira and determines if it was an assignment or transition that triggered the event and acts accordingly.

Optionally, you can specify a JQL query to restrict the webhook to appropriate projects and request types in order to ensure that the webhook only fires when appropriate. To filter on request types, use `Customer Request Type`.

## Development

The additional modules required for development can be installed with:

    pipenv install --dev

Unit tests and coverage tests can be executed with:

    pipenv shell
    pytest

If any Python packages are added via Pipenv, please remember to update `requirements.txt` as the latter is used by the Docker container's build process.

### Code contributions

Contributions to the framework are more than welcome. Please ensure that tests are provided for all new code and that code coverage is maintained.
