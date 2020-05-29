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


def get_request_type_id(name, sdid):
    """ Return the ID for the specified request type in the specified project. """
    result = service_desk_request_get(
        "%s/rest/servicedeskapi/servicedesk/%s/requesttype" % (
            shared.globals.ROOT_URL, sdid))
    if result.status_code == 200:
        json_content = result.json()
        for value in json_content["values"]:
            if value["name"] == name:
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
            if result.status_code == 404:
                print(
                    "WARNING! It doesn't look like %s has permission to add attachments to %s"
                    % (shared.globals.CONFIGURATION["bot_name"], shared.globals.PROJECT)
                )
        # Return the status code either from creating the attachment or
        # attaching the temporary file.
        return result.status_code
    # Indicate we couldn't find the project for this ticket ... which shouldn't happen!
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
    return look_for_trigger("assignee", ticket_data, "from", "to")


def trigger_is_transition(ticket_data):
    """ Did a transition trigger this event? """
    return look_for_trigger("status", ticket_data, "fromString", "toString")


# Jira will trigger the jira:issue_updated webhook for any change to an issue,
# including comments.
def look_for_trigger(trigger_type, ticket_data, from_tag, to_tag):
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
                return True, item[from_tag], item[to_tag]
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


def get_reporter_field(ticket_data, field_name):
    """ Generalised function to get a field back for the reporter. """
    if ("issue" in ticket_data and
            "fields" in ticket_data["issue"] and
            "reporter" in ticket_data["issue"]["fields"] and
            field_name in ticket_data["issue"]["fields"]["reporter"]):
        return ticket_data["issue"]["fields"]["reporter"][field_name]
    return None


def reporter_email_address(ticket_data):
    """ Get the reporter's email address from the ticket data. """
    return get_reporter_field(ticket_data, "emailAddress")


def groups_for_user(email_address):
    """ Get all of the groups that the user is in. """
    result = service_desk_request_get(
        "%s/rest/api/2/user?username=%s&expand=groups" % (
            shared.globals.ROOT_URL, email_address))
    groups = []
    if result.status_code == 200:
        unpack = result.json()
        group_list = unpack["groups"]["items"]
        for group in group_list:
            groups.append(group["name"])
    return groups


def sd_orgs():
    """
    Get a list of the organisations for this project. Return a dict
    with the org names as the keys and the index number as the value.

    That makes it easier to work out what value to add to the
    organization custom field.
    """
    sd_id = get_servicedesk_id(shared.globals.PROJECT)
    orgs = {}
    if sd_id != -1:
        result = service_desk_request_get(
            "%s/rest/servicedeskapi/servicedesk/%s/organization" % (
                shared.globals.ROOT_URL, sd_id))
        if result.status_code == 200:
            unpack = result.json()
            org_list = unpack["values"]
            for org in org_list:
                orgs[org["name"]] = int(org["id"])
    return orgs


def add_to_customfield_value(cf_id, value):
    """ Save the specified value to the custom field. """
    data = {
        "update": {
            cf_id: [
                {
                    "add": {
                        "value": value
                    }
                }
            ]
        }
    }
    result = service_desk_request_put(
        "%s/rest/api/2/issue/%s" % (
            shared.globals.ROOT_URL, shared.globals.TICKET),
        json.dumps(data))
    if result.status_code != 204:
        print("Got status code %s in add_to_customfield_value" % result.status_code)
        print(json.dumps(data))


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


def create_request(request_data):
    """ Create a Service Desk request from the provided data. """
    result = service_desk_request_post(
        "%s/rest/servicedeskapi/request" % shared.globals.ROOT_URL,
        json.dumps(request_data))
    if result.status_code != 201:
        print("Got status code %s in create_request" % result.status_code)
        print(result.text)


def resolve_ticket(resolution_state="Done", assign_to_bot=True):
    """Mark the issue as resolved."""
    if assign_to_bot:
        assign_issue_to(shared.globals.CONFIGURATION["bot_name"])

    transition_id = find_transition("Resolved")
    if transition_id != 0:
        update = {
            'transition': {
                'id': transition_id
            },
            'fields': {
                'resolution': {
                    'name': resolution_state
                }
            }
        }
        result = service_desk_request_post(
            "%s/rest/api/2/issue/%s/transitions" %
            (shared.globals.ROOT_URL, shared.globals.TICKET),
            json.dumps(update))
        if result.status_code != 204:
            post_comment(
                "Unable to mark issue as Done. Error code %s and message '%s'"
                % (result.status_code, result.text), False)
            post_comment(
                "Transition ID was %s and resolution name was %s" % (
                    transition_id, resolution_state), False)


def assign_issue_to(person):
    """Assign the issue to the specified email address."""
    update = {'name': person}
    result = service_desk_request_put(
        "%s/rest/api/2/issue/%s/assignee" %
        (shared.globals.ROOT_URL, shared.globals.TICKET),
        json.dumps(update))
    if result.status_code != 204:
        post_comment(
            "[~philip.colmer@linaro.org] Unable to assign issue to '%s'. "
            "Error code %s and message '%s'" %
            (person, result.status_code, result.text), False)


def transition_request_to(name):
    """Transition the issue to the specified transition name."""
    lower_name = name.lower()
    current_state = get_current_status()
    if current_state.lower() == lower_name:
        # Nothing to do.
        return
    transition_id = find_transition(lower_name)
    if transition_id != 0:
        update = {'transition': {'id': transition_id}}
        result = service_desk_request_post(
            "%s/rest/api/2/issue/%s/transitions" %
            (shared.globals.ROOT_URL, shared.globals.TICKET),
            json.dumps(update))
        if result.status_code != 204:
            post_comment(
                "Transition '%s' failed with error code %s and message '%s'"
                % (name, result.status_code, result.text), False)


def find_transition(transition_name):
    """ Find a transition to get to the desired state and return the matching ID. """
    url = "%s/rest/api/2/issue/%s/transitions" % (
        shared.globals.ROOT_URL, shared.globals.TICKET)
    lower_name = transition_name.lower()
    result = service_desk_request_get(url)
    if result.status_code != 200:
        post_comment(
            "Unable to get transitions for issue. Error code %s and message '%s'" %
            (result.status_code, result.text),
            False)
        return 0
    j = result.json()
    for transition in j['transitions']:
        if transition['to']['name'].lower() == lower_name:
            return transition['id']

    msg = (
        "Unable to find transition to get to state '%s' for issue %s\r\n" %
        (transition_name, shared.globals.TICKET))
    msg += "Current status is %s\r\n" % get_current_status()
    msg += result.text
    post_comment(msg, False)
    return 0


def get_current_status():
    """ Return the name of the ticket's current status. """
    url = "%s/rest/api/2/issue/%s?fields=status" % (
        shared.globals.ROOT_URL, shared.globals.TICKET)
    result = service_desk_request_get(url)
    j = result.json()
    return j["fields"]["status"]["name"]


def central_comment_handler(
        supported_public_keywords,
        supported_private_keywords,
        transition_if_resolved=None):
    """
    For a given set of keywords, figure out if they match or not based on
    the last comment posted.
    """
    comment = get_latest_comment()
    keyword = get_keyword_from_comment(comment)

    # If the ticket is resolved, trigger the reopen transition if the comment
    # wasn't posted by the bot code. Note that the required transition is
    # specified by the caller so that the shared code doesn't need to have
    # any special knowledge of the workflow.
    if (get_current_status() == "Resolved" and
            comment['author']['name'] != shared.globals.CONFIGURATION["bot_name"] and
            transition_if_resolved is not None):
        transition_request_to(transition_if_resolved)

    if not(comment['public']) and keyword in supported_private_keywords:
        return (comment, keyword)
    if comment['public'] and keyword in supported_public_keywords:
        return (comment, keyword)

    return (comment, None)


def get_keyword_from_comment(comment):
    """Extract the keyword from the comment."""
    if comment is None:
        return None

    # Keywords are always single words so we just take the first word and
    # return it in lower-case.
    # More complicated than using just split because we don't want punctuation.
    return "".join((char if char.isalpha() else " ") for
                   char in comment['body']).split()[0].lower()


def get_latest_comment():
    """Get the latest comment from Service Desk (not JIRA)."""
    # Although JIRA sends the full issue body when a comment is added, it is
    # JIRA not Service Desk that does this, so we don't get the public
    # visibility setting. That is important when we want to trigger certain
    # keywords posted privately as comments to an issue, so we ask ServiceDesk
    # to send us the comments instead.
    start = 0
    while True:
        result = service_desk_request_get(
            "%s/rest/servicedeskapi/request/%s/comment?start=%s" % (
                shared.globals.ROOT_URL, shared.globals.TICKET, start))
        if result.status_code != 200:
            return None
        j = result.json()
        # If we're on the last page of comments, return the last comment!
        if j['isLastPage']:
            return j['values'][-1]
        # Get the next batch of comments
        start += j['size']


def deassign_ticket_if_appropriate(last_comment, transition_to=None):
    """
    If the current current ticket is assigned to IT Support Bot, deassign
    it but only if the latest comment wasn't from the bot itself.

    This normally happens when someone publicly comments on a ticket that
    the bot has processed. Deassigning it allows IT to see the reply.
    However, if the current state is "Needs approval", we leave it alone
    because otherwise the approval process breaks.
    """
    if get_current_status() == "Needs approval":
        return

    if last_comment["author"]["name"] == shared.globals.CONFIGURATION["bot_name"]:
        return

    assignee = shared.globals.TICKET_DATA["issue"]["fields"]["assignee"]
    if assignee is not None and assignee["name"] == shared.globals.CONFIGURATION["bot_name"]:
        assign_issue_to(None)
        if transition_to is not None:
            transition_request_to(transition_to)


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
