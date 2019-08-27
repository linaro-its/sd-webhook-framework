#!/usr/bin/python3
"""
Handles all of the interaction with Service Desk and Jira.

Note that Basic authentication is used instead of OAuth. The latter
requires an element of user interaction in order to generate the OAuth
authentication token. There are Python libraries available that support
OAuth1 (Flask-Dance even supports Jira directly) but it is beyond the
scope of this project to support anything other than Basic authentication.

vault_auth can be found at https://github.com/linaro-its/vault_auth
"""


import json
from datetime import datetime
import requests
import shared.globals
import shared.custom_fields as custom_fields


class SharedSDError(Exception):
    """ Base exception class for the library. """

class MalformedIssueError(SharedSDError):
    """ Malformed issue exception. """

class CustomFieldLookupFailure(SharedSDError):
    """ Custom field lookup failure exception. """


def get_servicedesk_id(sd_project_key):
    """ Return the Service Desk ID for a given project key. """
    result = service_desk_request_get(
        "%s/rest/servicedeskapi/servicedesk" % shared.globals.ROOT_URL)
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
    sd_id = get_servicedesk_id(shared.globals.PROJECT)
    if sd_id != -1:
        result = requests.post(
            "%s/rest/servicedeskapi/servicedesk/%s/attachTemporaryFile" % (
                shared.globals.ROOT_URL, sd_id),
            headers=headers, files=files, auth=shared.globals.SD_AUTH)
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
                    shared.globals.ROOT_URL, shared.globals.TICKET),
                json.dumps(create))
        # Return the status code either from creating the attachment or
        # attaching the temporary file.
        return result.status_code
    # Indicate we couldn't find the ITS project ... which shouldn't happen!
    return -1


def ticket_request_type(ticket_data):
    """ Return the request type for the provided ticket data. """
    # The request type is stored in the Customer Request Type CF.
    crt_cf = custom_fields.get("Customer Request Type")
    if crt_cf is None:
        raise CustomFieldLookupFailure(
            "Failed to find 'Customer Request Type'")
    cf_name = "customfield_%s" % crt_cf
    if cf_name not in ticket_data["issue"]["fields"]:
        raise MalformedIssueError(
            "Failed to find '%s' in issue fields" % cf_name)
    return ticket_data["issue"]["fields"][cf_name]["requestType"]["id"]


def save_ticket_data_as_attachment(ticket_data):
    """ Save the ticket data as an attachment - used for debugging. """
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
    """ Try to determine if we (the automation) triggered the last comment. """
    if ("comment" in ticket_data and
            "author" in ticket_data["comment"] and
            "name" in ticket_data["comment"]["author"] and
            ticket_data["comment"]["author"][
                "name"] == shared.globals.CONFIGURATION["bot_name"]):
        return True
    return False


def trigger_is_assignment(ticket_data):
    """ Did a change of assignee trigger this event? """
    return look_for_trigger("assignee", ticket_data)


def trigger_is_transition(ticket_data):
    """ Did a transition trigger this event? """
    return look_for_trigger("status", ticket_data)


# Jira will trigger the jira:issue_updated webhook for any change to an issue,
# including comments.
def look_for_trigger(trigger_type, ticket_data):
    """ Try to find the specified trigger type in the ticket data. """
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
    """ Does the ticket data contain usable info? """
    if "webhookEvent" not in ticket_data:
        return False
    if ticket_data["webhookEvent"] != "jira:issue_updated":
        return False
    if "issue_event_type_name" not in ticket_data:
        return False
    ietn = ticket_data["issue_event_type_name"]
    if ietn not in ("issue_assigned", "issue_generic"):
        return False
    # It should be valid from hereon in
    return True


def get_field(ticket_data, field_id):
    """ Return the required custom field if it is in the data. """
    field_name = "customfield_%s" % field_id
    if ("issue" in ticket_data and
            "fields" in ticket_data["issue"] and
            field_name in ticket_data["issue"]["fields"]):
        return ticket_data["issue"]["fields"][field_name]
    return None


def reporter_email_address(ticket_data):
    """ Get the reporter's email address from the ticket data. """
    if ("issue" in ticket_data and
            "fields" in ticket_data["issue"] and
            "reporter" in ticket_data["issue"]["fields"] and
            "emailAddress" in ticket_data["issue"]["fields"]["reporter"]):
        return ticket_data["issue"]["fields"]["reporter"]["emailAddress"]
    return None


def post_comment(comment, public_switch):
    """ Post a comment to the current issue. """
    new_comment = {}
    new_comment['body'] = comment
    new_comment['public'] = public_switch
    json_comment = json.dumps(new_comment)
    # Quietly ignore any errors returned. If we can't comment, we can't do
    # much!
    result = service_desk_request_post(
        "%s/rest/servicedeskapi/request/%s/comment" % (
            shared.globals.ROOT_URL, shared.globals.TICKET),
        json_comment
    )
    # Trying to figure out why some comments go missing ...
    if result.status_code != 201:
        print("Got status code %s in post_comment" % result.status_code)
        print("Url: %s/rest/servicedeskapi/request/%s/comment" % (
            shared.globals.ROOT_URL, shared.globals.TICKET))
        print("Comment: %s" % comment)


def service_desk_request_get(url):
    """Centralised routine to GET from Service Desk."""
    headers = {'content-type': 'application/json', 'X-ExperimentalApi': 'true'}
    return requests.get(url, headers=headers, auth=shared.globals.SD_AUTH)


def service_desk_request_post(url, data):
    """Centralised routine to POST to Service Desk."""
    headers = {'content-type': 'application/json', 'X-ExperimentalApi': 'true'}
    return requests.post(url, headers=headers, auth=shared.globals.SD_AUTH, data=data)


def service_desk_request_put(url, data):
    """Centralised routine to PUT to Service Desk."""
    headers = {'content-type': 'application/json', 'X-ExperimentalApi': 'true'}
    return requests.put(url, headers=headers, auth=shared.globals.SD_AUTH, data=data)
