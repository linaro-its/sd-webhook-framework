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
import urllib
from datetime import datetime

import requests

import shared.custom_fields as custom_fields
import shared.globals
import shared.shared_ldap as shared_ldap

GDPR_ERROR = "'accountId' must be the only user identifying query parameter in GDPR strict mode."
TRANSITION_API = "%s/rest/api/2/issue/%s/transitions"

class SharedSDError(Exception):
    """ Base exception class for the library. """

class MalformedIssueError(SharedSDError):
    """ Malformed issue exception. """

class CustomFieldLookupFailure(SharedSDError):
    """ Custom field lookup failure exception. """


def get_servicedesk_projects():
    """ Return all Service Desk projects. """
    result = service_desk_request_get(
        "%s/rest/servicedeskapi/servicedesk" % shared.globals.ROOT_URL)
    if result.status_code == 200:
        return result.json()
    return None


def get_servicedesk_id(sd_project_key):
    """ Return the Service Desk ID for a given project key. """
    projects = get_servicedesk_projects()
    if projects is not None:
        values = projects["values"]
        for value in values:
            if value["projectKey"] == sd_project_key:
                return value["id"]
    return -1


def get_servicedesk_request_types(project_id):
    """ Return all of the request types for a given Service Desk project. """
    result = service_desk_request_get(
        "%s/rest/servicedeskapi/servicedesk/%s/requesttype" % (
            shared.globals.ROOT_URL, project_id))
    if result.status_code == 200:
        return result.json()
    return None


def get_request_type_id(name, sdid):
    """ Return the ID for the specified request type in the specified project. """
    request_types = get_servicedesk_request_types(sdid)
    if request_types is not None:
        for value in request_types["values"]:
            if value["name"] == name:
                return value["id"]
    return -1


def save_text_as_attachment(filename, content, comment, public):
    """Save the specified text as a file on the current ticket."""
    headers = {
        'Authorization': 'Basic %s' % shared.globals.SD_AUTH,
        'X-Atlassian-Token': 'no-check',
        'X-ExperimentalApi': 'true'
    }
    files = {'file': (filename, content, 'text/plain')}
    sd_id = get_servicedesk_id(shared.globals.PROJECT)
    if sd_id != -1:
        result = requests.post(
            "%s/rest/servicedeskapi/servicedesk/%s/attachTemporaryFile" % (
                shared.globals.ROOT_URL, sd_id),
            headers=headers, files=files)
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
                create)
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


def ticket_issue_type(ticket_data):
    """ Return the issue type for the provided ticket data. """
    return ticket_data["fields"]["issuetype"]["name"]


def ticket_request_type(ticket_data):
    """ Return the request type for the provided ticket data. """
    # The request type is stored in the Customer Request Type CF.
    crt_cf = custom_fields.get("Customer Request Type")
    if crt_cf is None:
        crt_cf = custom_fields.get("Request Type")
    if crt_cf is None:
        raise CustomFieldLookupFailure(
            "Failed to find the request type information")
    if crt_cf not in ticket_data["fields"]:
        raise MalformedIssueError(
            "Failed to find '%s' in issue fields" % crt_cf)
    if ticket_data["fields"][crt_cf] is None:
        # Probably a Jira issue not a SD issue
        return None
    return ticket_data["fields"][crt_cf]["requestType"]["id"]


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
    comments = None
    if "comment" in ticket_data:
        comments = ticket_data["comment"]
    elif "comment" in ticket_data["fields"]:
        comments = ticket_data["fields"]["comment"]["comments"]
    if comments is not None:
        last_comment = comments[-1]
        return user_is_bot(last_comment["author"])
    return False


def trigger_is_assignment(ticket_data):
    """ Did a change of assignee trigger this event? """
    return look_for_trigger("assignee", ticket_data, "to")


def trigger_is_transition(ticket_data):
    """ Did a transition trigger this event? """
    return look_for_trigger("status", ticket_data, "toString")


# Jira will trigger the jira:issue_updated webhook for any change to an issue,
# including comments.
def look_for_trigger(trigger_type, ticket_data, to_tag):
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
                return True, item[to_tag]
    return False, None


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


def get_field(ticket_data, field_name):
    """ Return the required custom field if it is in the data. """
    if ("fields" in ticket_data and
            field_name in ticket_data["fields"]):
        return ticket_data["fields"][field_name]
    return None


def get_user_field(user_blob, field_name):
    """
    Get the specified field back from the user blob data. Cloud
    doesn't populate a lot of this data, though, meaning we then
    have to query the self URL to get it.
    """
    if field_name not in user_blob:
        print("get_user_field: requested field %s is not in the blob" % field_name)
        return None
    value = user_blob[field_name]
    if value is not None:
        return value
    result = service_desk_request_get(user_blob["self"])
    if result.status_code != 200:
        print("Got status %s when querying %s for user field %s" % (
            result.status_code, user_blob["self"], field_name))
        return None
    data = result.json()
    if field_name in data:
        return data[field_name]
    print("get_user_field: '%s' not in the self data" % field_name)
    print(json.dumps(data))
    return None


def user_is_bot(user_blob):
    """ Check if the user mentioned in the blob is the configured bot. """
    return get_user_field(user_blob, "emailAddress") == shared.globals.CONFIGURATION["bot_name"]


def get_reporter_field(ticket_data, field_name):
    """ Generalised function to get a field back for the reporter. """
    if ("fields" in ticket_data and
            "reporter" in ticket_data["fields"]):
        return get_user_field(ticket_data["fields"]["reporter"], field_name)
    return None


def reporter_email_address(ticket_data):
    """ Get the reporter's email address from the ticket data. """
    return get_reporter_field(ticket_data, "emailAddress")


def get_group_members(group_name):
    """ Get the members of the specified group. """
    enc_group_name = urllib.parse.quote(group_name)
    query_url = "%s/rest/api/2/group/member?groupname=%s" % (
        shared.globals.ROOT_URL, enc_group_name)
    result = service_desk_request_get(query_url)
    index = 0
    members = []
    while True:
        if result.status_code == 200:
            unpack = result.json()
            member_list = unpack["values"]
            for member in member_list:
                members.append(member["name"])
            # Do we need to fetch the next block?
            if unpack["isLast"]:
                break
            index += unpack["maxResults"]
            result = service_desk_request_get(
                "%s&startAt=%s" % (query_url, index))
            # and loop ...
        else:
            print("get_group_members(%s) failed with error code %s" % (
                group_name, result.status_code))
            break
    return members


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
                    "add": value
                }
            ]
        }
    }
    result = service_desk_request_put(
        "%s/rest/api/2/issue/%s" % (
            shared.globals.ROOT_URL, shared.globals.TICKET),
        data)
    if result.status_code != 204:
        print("Got status code %s in add_to_customfield_value" % result.status_code)
        print("Url: %s/rest/api/2/issue/%s" % (
            shared.globals.ROOT_URL, shared.globals.TICKET))
        print(result.text)
        print(json.dumps(data))


def post_comment(comment, public_switch):
    """ Post a comment to the current issue. """
    new_comment = {
        "body": comment,
        "public": public_switch
    }
    # Quietly ignore any errors returned. If we can't comment, we can't do
    # much!
    result = service_desk_request_post(
        "%s/rest/servicedeskapi/request/%s/comment" % (
            shared.globals.ROOT_URL, shared.globals.TICKET),
        new_comment
    )
    # Trying to figure out why some comments go missing ...
    if result.status_code != 201:
        print("Got status code %s in post_comment" % result.status_code)
        print("Url: %s/rest/servicedeskapi/request/%s/comment" % (
            shared.globals.ROOT_URL, shared.globals.TICKET))
        print("Comment: %s" % comment)
        print(result.text)


def create_request(request_data):
    """ Create a Service Desk request from the provided data. """
    result = service_desk_request_post(
        "%s/rest/servicedeskapi/request" % shared.globals.ROOT_URL,
        request_data)
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
            TRANSITION_API % (shared.globals.ROOT_URL, shared.globals.TICKET),
            update)
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
        update)
    # On Cloud, this can fail because of GDPR settings so we need to
    # take extra steps if that happens.
    if result.status_code == 400:
        # Check the error message
        error = result.json()
        if "errorMessages" in error and \
            error["errorMessages"][0] == GDPR_ERROR:
            result = assign_issue_to_account_id(person)
    # Either not the right error message or we've just tried using assign issue to account_id
    if result.status_code != 204:
        post_comment(
            "Unable to assign issue to '%s'. Error code %s and message '%s'" %
            (person, result.status_code, result.text), False)


def assign_issue_to_account_id(person):
    """ Convert the person's name to an anonymised account id and then assign issue. """
    result = service_desk_request_get(
        "%s/rest/api/2/user/assignable/multiProjectSearch"
        "?query=%s&projectKeys=%s" % (shared.globals.ROOT_URL, person, shared.globals.PROJECT)
    )
    if result.status_code != 200:
        return result
    # Should return us precisely one user ...
    data = result.json()
    if data == []:
        return result # Not really helpful but the status code isn't 204 so we'll get a comment
    account_id = data[0]["accountId"]
    update = {'accountId': account_id}
    return service_desk_request_put(
        "%s/rest/api/2/issue/%s/assignee" %
        (shared.globals.ROOT_URL, shared.globals.TICKET),
        update)


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
            TRANSITION_API % (shared.globals.ROOT_URL, shared.globals.TICKET),
            update)
        if result.status_code != 204:
            post_comment(
                "Transition '%s' failed with error code %s and message '%s'"
                % (name, result.status_code, result.text), False)


def find_transition(transition_name):
    """ Find a transition to get to the desired state and return the matching ID. """
    url = TRANSITION_API % (shared.globals.ROOT_URL, shared.globals.TICKET)
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
    if result.status_code != 200:
        print("Unable to get current status. Request status code is ", result.status_code)
        return None
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
    status = get_current_status()
    # If it is None, we're in trouble as we've failed to get the status so bail now
    if status is None:
        return (None, None)

    if (get_current_status() == "Resolved" and
            not user_is_bot(comment["author"]) and
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
            if len(j['values']) == 0:
                return None
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

    if user_is_bot(last_comment["author"]):
        return

    assignee = shared.globals.TICKET_DATA["fields"]["assignee"]
    if assignee is not None and user_is_bot(assignee):
        assign_issue_to(None)
        if transition_to is not None:
            transition_request_to(transition_to)


def assign_approvers(approver_list, custom_field, add_to_request_participants=True):
    """
        Add the list of approvers to the specified custom field,
        making them request participants as well if needed.
    """
    flat_list = shared_ldap.flatten_list(approver_list)
    approvers = {"fields": {custom_field: []}}
    for item in flat_list:
        if item != "":
            # Cope with being sent email addresses already
            if "@" in item:
                item_email = item
            else:
                obj = shared_ldap.get_object(item, ["mail"])
                item_email = obj.mail.value
            if item_email is not None:
                approvers["fields"][custom_field].append(
                    {'name': item_email})
                if add_to_request_participants:
                    # Add them as a request participant so that they get copies of
                    # any comment notifications.
                    add_request_participant(item_email)
    result = service_desk_request_put(
        shared.globals.TICKET_DATA["self"],
        approvers)
    if result.status_code != 204:
        post_comment(
            "Got error %s (%s) when setting the"
            " approvers:\r\n{panel}%s{panel}\r\n" % (
                result.text, result.status_code, approvers), False)


def set_summary(summary):
    """Set the summary of the issue to the specified string."""
    data = '{"update":{"summary":[{"set": "%s"}]}}' % summary
    service_desk_request_put("%s/rest/api/2/issue/%s" % (
        shared.globals.ROOT_URL, shared.globals.TICKET), data)
    # Update our copy of the ticket data to reflect the new summary
    shared.globals.TICKET_DATA["fields"]["summary"] = summary


def add_request_participant(email_address):
    """
    Add the specified email address as a request participant to the current
    issue.
    """
    if is_request_participant(email_address):
        return
    update = {'usernames': [email_address]}
    result = service_desk_request_post(
        "%s/rest/servicedeskapi/request/%s/participant" % (
            shared.globals.ROOT_URL, shared.globals.TICKET), update)
    if result.status_code != 200:
        post_comment(
            "Unable to add %s as request "
            "participant to %s. Error code %s and message '%s'" % (
                email_address, shared.globals.TICKET, result.status_code, result.text),
            False
        )


def is_request_participant(email_address):
    """
    Check if the specified email address is a request participant on the
    current issue.
    """
    start = 0
    while True:
        result = service_desk_request_get(
            "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
                shared.globals.ROOT_URL, shared.globals.TICKET, start))
        if result.status_code != 200:
            return False
        j = result.json()
        for value in j['values']:
            if value['emailAddress'] == email_address:
                return True
        if not j['isLastPage']:
            start += j['size']
        else:
            return False


def get_request_participants():
    """Returns a lit of request participants for the current issue."""
    list_of_participants = []
    start = 0
    while True:
        result = service_desk_request_get(
            "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
                shared.globals.ROOT_URL, shared.globals.TICKET, start))
        if result.status_code != 200:
            return []
        j = result.json()
        for value in j['values']:
            list_of_participants.append(value['emailAddress'])
        if not j['isLastPage']:
            start += j['size']
        else:
            return list_of_participants


def sd_headers():
    """ Return the required headers for Service Desk. """
    return {
        'Authorization': 'Basic %s' % shared.globals.SD_AUTH,
        'content-type': 'application/json',
        'X-ExperimentalApi': 'true'
    }


def service_desk_request_get(url):
    """Centralised routine to GET from Service Desk."""
    headers = sd_headers()
    return requests.get(url, headers=headers)


def service_desk_request_post(url, data):
    """Centralised routine to POST to Service Desk."""
    headers = sd_headers()
    return requests.post(url, headers=headers, json=data)


def service_desk_request_put(url, data):
    """Centralised routine to PUT to Service Desk."""
    headers = sd_headers()
    return requests.put(url, headers=headers, json=data)
