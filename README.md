# Service Desk Webhook Framework <!-- omit in toc -->

- [Introduction](#introduction)
- [What the framework supports](#what-the-framework-supports)
- [Production Usage](#production-usage)
- [Webhook Configuration](#webhook-configuration)
  - [Service Desk (Server) webhooks](#service-desk-server-webhooks)
  - [Jira (Server) webhook](#jira-server-webhook)
  - [Service Desk (Cloud) webhooks](#service-desk-cloud-webhooks)
- [Development](#development)
  - [Local testing](#local-testing)
  - [Code contributions](#code-contributions)

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=linaro-its_sd-webhook-framework&metric=alert_status)](https://sonarcloud.io/dashboard?id=linaro-its_sd-webhook-framework)

## Introduction

This repository provides a foundation for supporting webhook automation with Atlassian's Jira Service Desk. The aim of the framework is to provide a high quality foundation for providing webhook extensions to request types on Service Desk while  reducing the amount of code needed to be written. The framework provides the core webhook handling code plus common functions for interacting with Service Desk and LDAP, thus allowing the handlers for each request type to focus on the "business logic" required.

## What the framework supports

The framework can be triggered by the following actions:

- Creation of a ticket (`CREATE`)
- Comment added to a ticket (`COMMENT`)
- Organization change on a ticket (`ORGCHANGE`)
- Status change on a ticket (`TRANSITION`)
- Assignment change on a ticket (`ASSIGNMENT`)

Each *request type* has its own code file. The main code loads the code file appropriate to the ticket being handled.

Since the webhooks can be generic across all of the issue/request types, each code file has a CAPABILITIES section that the main code queries in order to determine whether or not the code can support the desired action, e.g.:

    CAPABILITIES = [ "CREATE", "ASSIGNMENT" ]

The sample test handler `rt_example_handler.py` lists all of the supported transition names. Handlers used by Linaro can be found in <https://github.com/linaro-its/sd-webhook-handlers>.

## Production Usage

There are a few options for running the framework in production:

- Apache with WSGI
- [Chalice](https://github.com/aws/chalice/)
- [Zappa](https://github.com/Miserlou/Zappa)

Both Chalice and Zappa are serverless options, but Chalice requires code changes in order to work.

To make it easier to use the framework with WSGI, this repository includes the files and configuration required to build a Docker container for running everything. See [WSGI](WSGI.md) for more details about how to use the Docker container, including how to debug the code if required.

To use the framework with Zappa, there are some additional steps required. To simplify the steps required, a sample repo has been created that shows how to use this framework repo with the sample handlers repo. See [Linaro SD Webhook](https://github.com/linaro-its/linaro-sd-webhook) for more details.

There is a commented configuration file - `configuration.sample.jsonc` - which needs to be copied as `configuration.jsonc` and then edited. This configuration file controls how the framework behaves to meet your specific needs, e.g. Service Desk bot account authentication, which handler file to use for which request type, etc. It is safe to leave the comments in the file - the framework copes with them being there when the file is read in.

## Webhook Configuration

If you are self-hosting Service Desk and you have [Automation for Jira](https://marketplace.atlassian.com/apps/1215460/automation-for-jira-server) installed, use the instructions for Service Desk Cloud configuration, otherwise follow the instructions for "Service Desk (Server) webhooks" and "Jira (server) webhook".

In the text below, `<base URL>` is the URL that is mapped onto the framework web service. If the framework is being run on the same server as Jira Service Desk, this could be (for example) `http://localhost:8000`.

### Service Desk (Server) webhooks

The Service Desk (Server) webhooks are created through Project Settings > Automation for a given SD project. Generally, the following rules should be configured, depending on the needs of the handlers:

- When: Issue created
  - Then: Webhook
  - URL: `<base URL>`/create
  - Include payload in request body
  
- When: Comment added
  - Then: Webhook
  - URL: `<base URL>`/comment
  - Include payload in request body

- When: Organizations added to issue
  - Then: Webhook
  - URL: `<base URL>`/org-change
  - Include payload in request body

You can use the `IF` clause to only fire when request types matching those supported by the webhook are affected. This is done by adding an `Issue matches` clause with JQL like this:

    "Customer Request Type" = "Name of the request type"

or

    Issue matches status = "Open"

Note that if you change the name of the request type, you **must** update any JQL clauses that reference it to match otherwise it will not fire. The clause does not get updated automatically.

Note that the framework will work out which request type has been used, so it is safe to omit the `IF` clause, with the understanding that the framework will be called for *all* issues created and commented on.

### Jira (Server) webhook

Create a WebHook in Jira with the following settings:

- URL: `<base URL>`/jira-hook
- Events: Issue>updated

The framework looks at the data sent by Jira and determines if it was an assignment or transition that triggered the event and acts accordingly. Note that a Jira webhook is used for transitions rather than the Service Desk "Status changed" event because it is then possible to track the before and after states.

Optionally, you can specify a JQL query to restrict the webhook to appropriate projects and request types in order to ensure that the webhook only fires when appropriate. To filter on request types, use `Customer Request Type`.

### Service Desk (Cloud) webhooks

If you have "Automation for Jira" installed on Service Desk (Server), you can configure these rules via Project settings > Project automation. For Service Desk (Cloud), you can configure these rules via Project settings > Automation.

Create automation rules for each of the following triggers:

1. Issue created
2. Issue commented
3. Field value changed
   - Fields to monitor for changes: Organizations
   - For: All issue operations
4. Issue transitioned
5. Issue assigned

For each rule:

- Optionally add a condition of:
  - Issue fields condition
  - Field: Request Type:
  - Condition: is one of
  - Value: request types that you want to limit the rule to
- New action
  - Notifications - Send web request
    - Webhook URL: `<base URL>`/`<action>`
    - (Optional) Headers
    - HTTP method: `POST`
    - Webhook body: `Issue data`

For the webhook URLs, the `action` value should be one of the following according to the trigger:

1. `create`
2. `comment`
3. `org-change`
4. `transition`
5. `assignment`

If using the framework with Zappa (see below), the optional headers can be used to set `x-api-key` to the appropriate API Gateway key value. This must be done on **all** or **none** of the webhooks.

## Development

On a development system, [Flask](http://flask.pocoo.org) is used to run the code.

Development of the code is done using a Pipenv-maintained virtual environment. The required modules are listed in `Pipfile` and can be installed with:

    pipenv install

Note that Python 3 is **required**.

The additional modules required for development can be installed with:

    pipenv install --dev

Unit tests and coverage tests can be executed with:

    pipenv shell
    pytest

If any Python packages are added via Pipenv, please remember to update `requirements.txt` as the latter is used by the Docker container's build process. Note that only the "top-level" packages are included, rather than generating the file automatically from Pipenv.

### Local testing

One way to troubleshoot the code is as follows:

1. Modify the webhooks so that the content is delivered to [RequestBin](https://requestbin.com/) rather than the framework. This allows you to capture the data sent from Service Desk.
2. Save the content to a file, e.g. "comment.json"
3. Modify "local_test.py" to read the correct file **and** trigger the correct path.
4. If using VS Code, use "Run and Debug" on "local_test.py". It is necessary to select "Raised Exceptions" in order to get VS Code to stop when the code breaks. Please note that there are some valid occurrences of raised exceptions in the framework.

Please note: if testing the `comment` route, please note that the framework explicitly reads the latest comment from the ticket, rather than using the comment data sent in the payload.

### Code contributions

Contributions to the framework are more than welcome. Please ensure that tests are provided for all new code and that code coverage is maintained.
