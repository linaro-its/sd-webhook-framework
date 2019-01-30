#!/usr/bin/python3
#
# Handles all of the interaction with Service Desk and Jira.
#
# Note that Basic authentication is used instead of OAuth. The latter
# requires an element of user interaction in order to generate the OAuth
# authentication token. There are Python libraries available that support
# OAuth1 (Flask-Dance even supports Jira directly) but it is beyond the
# scope of this project to support anything other than Basic authentication.
#
# vault_auth can be found at https://github.com/linaro-its/vault_auth


import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime
import vault_auth
import config


sd_auth = None
root_url = None
ticket = None
project = None


class SharedSDError(Exception):
    pass


class MalformedIssueError(SharedSDError):
    pass


class MissingCredentials(SharedSDError):
    pass


class OverlappingCredentials(SharedSDError):
    pass


class CustomFieldLookupFailure(SharedSDError):
    pass


def initialise(ticket_data):
    global root_url, ticket, project
    # Get the ticket details from the data and save it
    if "issue" not in ticket_data:
        raise MalformedIssueError("Missing 'issue' in data")
    if "self" not in ticket_data["issue"]:
        raise MalformedIssueError("Missing 'self' in issue")
    if "key" not in ticket_data["issue"]:
        raise MalformedIssueError("Missing 'key' in issue")
    if "fields" not in ticket_data["issue"]:
        raise MalformedIssueError("Missing 'fields' in issue")
    if "project" not in ticket_data["issue"]["fields"]:
        raise MalformedIssueError("Missing 'project' in fields")
    if "key" not in ticket_data["issue"]["fields"]["project"]:
        raise MalformedIssueError("Missing 'key' in project")
    issue_url = ticket_data["issue"]["self"].split("/", 3)
    root_url = "%s//%s" % (issue_url[0], issue_url[2])
    ticket = ticket_data["issue"]["key"]
    project = ticket_data["issue"]["fields"]["project"]["key"]


def sd_auth_credentials():
    if config.configuration is None:
        config.initialise()
    if "bot_name" not in config.configuration:
        raise MissingCredentials(
            "Missing 'bot_name' in configuration file")
    if "bot_password" not in config.configuration:
        # Make sure that the Vault values are there
        if "vault_iam_role" not in config.configuration:
            raise MissingCredentials(
                "Missing 'vault_iam_role' in configuration file")
        if "vault_server_url" not in config.configuration:
            raise MissingCredentials(
                "Missing 'vault_server_url' in configuration file")
        secret = vault_auth.get_secret(
            config.configuration["bot_name"],
            iam_role=config.configuration["vault_iam_role"],
            url=config.configuration["vault_server_url"]
        )
        # This assumes that the password will be stored in the "pw" key.
        return config.configuration["bot_name"], secret["data"]["pw"]
    else:
        # Make sure that the Vault values are NOT there
        if "vault_iam_role" in config.configuration:
            raise OverlappingCredentials(
                "Can't have 'bot_password' and 'vault_iam_role'")
        if "vault_server_url" in config.configuration:
            raise OverlappingCredentials(
                "Can't have 'bot_password' and 'vault_server_url'")
        return config.configuration["bot_name"],\
            config.configuration["bot_password"]


def get_sd_auth():
    global sd_auth
    if sd_auth is None:
        name, password = sd_auth_credentials()
        sd_auth = HTTPBasicAuth(name, password)
    return sd_auth


def get_servicedesk_id(sd_project_key):
    result = service_desk_request_get(
        "%s/rest/servicedeskapi/servicedesk" % root_url)
    if result.status_code == 200:
        unpack = result.json()
        values = unpack["values"]
        for value in values:
            if value["projectKey"] == sd_project_key:
                return value["id"]
    return -1


def save_text_as_attachment(filename, content, comment, public):
    """Save the specified text as a file on the current ticket."""
    headers = {'X-Atlassian-Token': 'no-check', 'X-ExperimentalApi': 'true'}
    files = {'file': (filename, content, 'text/plain')}
    sd_id = get_servicedesk_id(project)
    if sd_id != -1:
        result = requests.post(
            "%s/rest/servicedeskapi/servicedesk/%s/attachTemporaryFile" % (
                root_url, sd_id),
            headers=headers, files=files, auth=get_sd_auth())
        if result.status_code == 201:
            json_result = result.json()
            create = {
                'temporaryAttachmentIds': [
                    json_result["temporaryAttachments"][
                        0]["temporaryAttachmentId"]
                ],
                'public': public,
                'additionalComment': {
                    'body': comment
                }
            }
            result = service_desk_request_post(
                "%s/rest/servicedeskapi/request/%s/attachment" % (
                    root_url, ticket),
                json.dumps(create))
        # Return the status code either from creating the attachment or
        # attaching the temporary file.
        return result.status_code
    # Indicate we couldn't find the ITS project ... which shouldn't happen!
    return -1


def get_customfield_id_from_plugin(field_name):
    result = service_desk_request_get(
        "%s/rest/jiracustomfieldeditorplugin/1/admin/customfields" % root_url
    )
    if result.status_code == 200:
        fields = result.json()
        for field in fields:
            if field["fieldName"] == field_name:
                return field["fieldId"]
    else:
        print("Got status %s when requesting custom field %s" % (
            result.status_code, field_name))
        # Try to get the human readable error message
        fields = result.json()
        if "message" in fields:
            print(fields["message"])
    return None


def ticket_request_type(ticket_data):
    # The request type is stored in the Customer Request Type CF.
    crt_cf = get_customfield_id_from_plugin("Customer Request Type")
    if crt_cf is None:
        raise CustomFieldLookupFailure(
            "Failed to find 'Customer Request Type'")
    cf_name = "customfield_%s" % crt_cf
    if cf_name not in ticket_data["issue"]["fields"]:
        raise MalformedIssueError(
            "Failed to find '%s' in issue fields" % cf_name)
    return ticket_data["issue"]["fields"][cf_name]["requestType"]["id"]


def save_ticket_data_as_attachment(ticket_data):
    # Only do this if the data came from a Jira event or,
    # if it was triggered by a SD event, make sure that it wasn't a comment
    # created by this account ... otherwise we get into an event storm as
    # saving the attachment then triggers another event which triggers
    # saving the attachment ...
    if automation_triggered_comment(ticket_data):
        print(json.dumps(ticket_data))
    else:
        save_text_as_attachment(
            "%s.json" % datetime.now().strftime("%e%b-%H%M"),
            json.dumps(ticket_data),
            "Request payload for ticket creation",
            False)


def automation_triggered_comment(ticket_data):
    if ("comment" in ticket_data and
            "author" in ticket_data["comment"] and
            "name" in ticket_data["comment"]["author"] and
            ticket_data["comment"]["author"][
                "name"] == config.configuration["bot_name"]):
        return True
    return False


def trigger_is_assignment(ticket_data):
    return look_for_trigger("assignee", ticket_data)


def trigger_is_transition(ticket_data):
    return look_for_trigger("status", ticket_data)


# Jira will trigger the jira:issue_updated webhook for any change to an issue,
# including comments.
def look_for_trigger(trigger_type, ticket_data):
    # Make sure that we've got ticket data for an assignment or a transition.
    if usable_ticket_data(ticket_data):
        # Walk through the changelog to see if there was a state transition. If
        # there was, return the relevant data to help the webhook automation
        # code.
        if "changelog" not in ticket_data:
            raise MalformedIssueError(
                "Failed to find changelog")
        if "items" not in ticket_data["changelog"]:
            raise MalformedIssueError(
                "Failed to find changelog items")
        for item in ticket_data["changelog"]["items"]:
            if item["field"] == trigger_type and item["fieldtype"] == "jira":
                return True, item["from"], item["to"]
    return False, None, None


def usable_ticket_data(ticket_data):
    if "webhookEvent" not in ticket_data:
        return False
    if ticket_data["webhookEvent"] != "jira:issue_updated":
        return False
    if "issue_event_type_name" not in ticket_data:
        return False
    ietn = ticket_data["issue_event_type_name"]
    if ietn != "issue_assigned" and ietn != "issue_generic":
        return False
    # It should be valid from hereon in
    return True


def service_desk_request_get(url):
    """Centralised routine to GET from Service Desk."""
    headers = {'content-type': 'application/json', 'X-ExperimentalApi': 'true'}
    return requests.get(url, headers=headers, auth=get_sd_auth())


def service_desk_request_post(url, data):
    """Centralised routine to POST to Service Desk."""
    headers = {'content-type': 'application/json', 'X-ExperimentalApi': 'true'}
    return requests.post(url, headers=headers, auth=get_sd_auth(), data=data)


def service_desk_request_put(url, data):
    """Centralised routine to PUT to Service Desk."""
    headers = {'content-type': 'application/json', 'X-ExperimentalApi': 'true'}
    return requests.put(url, headers=headers, auth=get_sd_auth(), data=data)
