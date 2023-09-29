#!/usr/bin/python3
"""
Handles all of the interaction with Service Desk and Jira.

Note that Basic authentication is used instead of OAuth. The latter
requires an element of user interaction in order to generate the OAuth
authentication token. There are Python libraries available that support
OAuth1 (Flask-Dance even supports Jira directly) but it is beyond the
scope of this project to support anything other than Basic authentication.
"""


import json
import urllib
import urllib.parse
from datetime import datetime
from typing import Union

import requests

import shared.custom_fields as custom_fields
import shared.globals
import shared.shared_ldap as shared_ldap

GDPR_ERROR = (
    "'accountId' must be the only user identifying query parameter in GDPR strict mode."
)
TRANSITION_API = "%s/rest/api/2/issue/%s/transitions"


class SharedSDError(Exception):
    """Base exception class for the library."""


class MalformedIssueError(SharedSDError):
    """Malformed issue exception."""


class CustomFieldLookupFailure(SharedSDError):
    """Custom field lookup failure exception."""


def get_servicedesk_projects():
    """Return all Service Desk projects."""
    result = service_desk_request_get(
        f"{shared.globals.ROOT_URL}/rest/servicedeskapi/servicedesk"
    )
    if result.status_code == 200:
        return result.json()
    return None


def get_servicedesk_id(sd_project_key):
    """Return the Service Desk ID for a given project key."""
    projects = get_servicedesk_projects()
    if projects is not None:
        values = projects["values"]
        for value in values:
            if value["projectKey"] == sd_project_key:
                return value["id"]
    return -1


def get_servicedesk_request_types(project_id):
    """Return all of the request types for a given Service Desk project."""
    result = service_desk_request_get(
        f"{shared.globals.ROOT_URL}/rest/servicedeskapi/servicedesk/{project_id}/requesttype"
    )
    if result.status_code == 200:
        return result.json()
    return None


def get_request_type_id(name, sdid):
    """Return the ID for the specified request type in the specified project."""
    request_types = get_servicedesk_request_types(sdid)
    if request_types is not None:
        for value in request_types["values"]:
            if value["name"] == name:
                return value["id"]
    return -1


def save_text_as_attachment(filename, content, comment, public):
    """Save the specified text as a file on the current ticket."""
    headers = {
        "Authorization": f"Basic {shared.globals.SD_AUTH}",
        "X-Atlassian-Token": "no-check",
        "X-ExperimentalApi": "true",
    }
    files = {"file": (filename, content, "text/plain")}
    sd_id = get_servicedesk_id(shared.globals.PROJECT)
    if sd_id != -1:
        result = requests.post(
            f"{shared.globals.ROOT_URL}/rest/servicedeskapi/"
            f"servicedesk/{sd_id}/attachTemporaryFile",
            headers=headers,
            files=files,
            timeout=30
        )
        if result.status_code == 201:
            json_result = result.json()
            create = {
                "temporaryAttachmentIds": [
                    json_result["temporaryAttachments"][0]["temporaryAttachmentId"]
                ],
                "public": public,
                "additionalComment": {"body": comment},
            }
            result = service_desk_request_post(
                f"{shared.globals.ROOT_URL}/rest/servicedeskapi"
                f"/request/{shared.globals.TICKET}/attachment",
                create,
            )
            if result.status_code == 404:
                account = shared.globals.CONFIGURATION["bot_name"]
                print(
                    f"WARNING! It doesn't look like {account} has "
                    f"permission to add attachments to {shared.globals.PROJECT}"
                )
        # Return the status code either from creating the attachment or
        # attaching the temporary file.
        return result.status_code
    # Indicate we couldn't find the project for this ticket ... which shouldn't happen!
    return -1


def ticket_issue_type(ticket_data):
    """Return the issue type for the provided ticket data."""
    return ticket_data["fields"]["issuetype"]["name"]


def ticket_request_type(ticket_data):
    """Return the request type for the provided ticket data."""
    # The request type is stored in the Customer Request Type CF.
    crt_cf = custom_fields.get("Customer Request Type")
    if crt_cf is None:
        crt_cf = custom_fields.get("Request Type")
    if crt_cf is None:
        raise CustomFieldLookupFailure("Failed to find the request type information")
    if crt_cf not in ticket_data["fields"]:
        raise MalformedIssueError(f"Failed to find '{crt_cf}' in issue fields")
    print(f"Mapped request type to {crt_cf}")
    if ticket_data["fields"][crt_cf] is None:
        # Probably a Jira issue not a SD issue
        return None
    return ticket_data["fields"][crt_cf]["requestType"]["id"]


def save_ticket_data_as_attachment(ticket_data):
    """Save the ticket data as an attachment - used for debugging."""
    # Only do this if the data came from a Jira event or,
    # if it was triggered by a SD event, make sure that it wasn't a comment
    # created by this account ... otherwise we get into an event storm as
    # saving the attachment then triggers another event which triggers
    # saving the attachment ...
    if automation_triggered_comment(ticket_data):
        print(json.dumps(ticket_data))
    else:
        filename = datetime.now().strftime("%e%b-%H%M")
        save_text_as_attachment(
            f"{filename}.json",
            json.dumps(ticket_data),
            "Request payload for ticket creation",
            False,
        )


def automation_triggered_comment(ticket_data):
    """Try to determine if we (the automation) triggered the last comment."""
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
    """Did a change of assignee trigger this event?"""
    return look_for_trigger("assignee", ticket_data, "to")


def trigger_is_transition(ticket_data):
    """Did a transition trigger this event?"""
    return look_for_trigger("status", ticket_data, "toString")


# Jira will trigger the jira:issue_updated webhook for any change to an issue,
# including comments.
def look_for_trigger(trigger_type, ticket_data, to_tag):
    """Try to find the specified trigger type in the ticket data."""
    # Make sure that we've got ticket data for an assignment or a transition.
    if usable_ticket_data(ticket_data):
        # Walk through the changelog to see if there was a state transition. If
        # there was, return the relevant data to help the webhook automation
        # code.
        if "changelog" not in ticket_data:
            raise MalformedIssueError("Failed to find changelog")
        if "items" not in ticket_data["changelog"]:
            raise MalformedIssueError("Failed to find changelog items")
        for item in ticket_data["changelog"]["items"]:
            if item["field"] == trigger_type and item["fieldtype"] == "jira":
                return True, item[to_tag]
    else:
        print("No usable ticket data for Jira trigger")
    return False, None


def usable_ticket_data(ticket_data):
    """Does the ticket data contain usable info?"""
    if "webhookEvent" not in ticket_data:
        print("No webhookEvent field in ticket data")
        return False
    if ticket_data["webhookEvent"] != "jira:issue_updated":
        event = ticket_data["webhookEvent"]
        print(f"{event} is not the event we're looking for")
        return False
    if "issue_event_type_name" not in ticket_data:
        print("No issue_event_type_name in ticket data")
        return False
    ietn = ticket_data["issue_event_type_name"]
    if ietn not in ("issue_assigned", "issue_generic"):
        print(f"{ietn} is not the type name we're looking for")
        return False
    # It should be valid from hereon in
    return True


def get_field(ticket_data, field_name):
    """Return the required custom field if it is in the data."""
    if "fields" in ticket_data and field_name in ticket_data["fields"]:
        return ticket_data["fields"][field_name]
    return None


def get_user_field(user_blob, field_name):
    """
    Get the specified field back from the user blob data. Cloud
    doesn't populate a lot of this data, though, meaning we then
    have to query the self URL to get it.
    """
    if user_blob is None:
        print("get_user_field: passed None as user blob")
        return
    if field_name not in user_blob:
        print(f"get_user_field: requested field {field_name} is not in the blob")
        print(json.dumps(user_blob))
        return None
    value = user_blob[field_name]
    if value is not None:
        return value
    result = service_desk_request_get(user_blob["self"])
    if result.status_code != 200:
        ub_self = user_blob["self"]
        print(
            f"Got status {result.status_code} when querying {ub_self} for user field {field_name}"
        )
        return None
    data = result.json()
    if field_name in data:
        return data[field_name]
    print(f"get_user_field: '{field_name}' not in the self data")
    print(json.dumps(data))
    return None


def user_is_bot(user_blob):
    """Check if the user mentioned in the blob is the configured bot."""
    return (
        get_user_field(user_blob, "emailAddress")
        == shared.globals.CONFIGURATION["bot_name"]
    )


def get_reporter_field(ticket_data, field_name):
    """Generalised function to get a field back for the reporter."""
    if "fields" in ticket_data and "reporter" in ticket_data["fields"]:
        return get_user_field(ticket_data["fields"]["reporter"], field_name)
    return None


def reporter_email_address(ticket_data):
    """Get the reporter's email address from the ticket data."""
    return get_reporter_field(ticket_data, "emailAddress")


def get_assignee_field(ticket_data, field_name):
    """Generalised function to get a field back for the assignee."""
    if "fields" in ticket_data and "assignee" in ticket_data["fields"]:
        return get_user_field(ticket_data["fields"]["assignee"], field_name)
    return None


def assignee_email_address(ticket_data):
    """Get the assignee's email address from the ticket data."""
    return get_assignee_field(ticket_data, "emailAddress")


def get_group_members(group_name):
    """Get the members of the specified group."""
    enc_group_name = urllib.parse.quote(group_name)
    query_url = f"{shared.globals.ROOT_URL}/rest/api/2/group/member?groupname={enc_group_name}"
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
            result = service_desk_request_get(f"{query_url}&startAt={index}")
            # and loop ...
        else:
            print(
                f"get_group_members({group_name}) failed with error code {result.status_code}"
            )
            break
    return members


def groups_for_user(email_address):
    """Get all of the groups that the user is in."""
    result = service_desk_request_get(
        f"{shared.globals.ROOT_URL}/rest/api/2/user?username={email_address}&expand=groups"
    )
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
            f"{shared.globals.ROOT_URL}/rest/servicedeskapi/servicedesk/{sd_id}/organization"
        )
        if result.status_code == 200:
            unpack = result.json()
            org_list = unpack["values"]
            for org in org_list:
                orgs[org["name"]] = int(org["id"])
    return orgs


def add_to_customfield_value(cf_id, value):
    """Save the specified value to the custom field."""
    data = {"update": {cf_id: [{"add": value}]}}
    result = service_desk_request_put(
        f"{shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}",
        data,
    )
    if result.status_code != 204:
        print(f"Got status code {result.status_code} in add_to_customfield_value")
        print(
            f"Url: {shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}"
        )
        print(result.text)
        print(json.dumps(data))


def post_comment(comment, public_switch):
    """Post a comment to the current issue."""
    print(f"post_comment: ticket {shared.globals.TICKET}")
    print(f"post_comment: {comment}")
    new_comment = {"body": comment, "public": public_switch}
    # Quietly ignore any errors returned. If we can't comment, we can't do
    # much!
    result = service_desk_request_post(
        f"{shared.globals.ROOT_URL}/rest/servicedeskapi/request/{shared.globals.TICKET}/comment",
        new_comment,
    )
    print(f"post_comment: got status code {result.status_code}")
    # Trying to figure out why some comments go missing ...
    if result.status_code != 201:
        print(
            f"post_comment: Url: {shared.globals.ROOT_URL}/rest/servicedeskapi"
            "/request/{shared.globals.TICKET}/comment"
        )
        print(result.text)


def create_request(request_data):
    """Create a Service Desk request from the provided data."""
    result = service_desk_request_post(
        f"{shared.globals.ROOT_URL}/rest/servicedeskapi/request", request_data
    )
    if result.status_code != 201:
        print(f"Got status code {result.status_code} in create_request")
        print(result.text)


def resolve_ticket(resolution_state="Done", assign_to_bot=True):
    """Mark the issue as resolved."""
    if assign_to_bot:
        assign_issue_to(shared.globals.CONFIGURATION["bot_name"])

    transition_id = find_transition("Resolved")
    if transition_id != 0:
        update = {
            "transition": {"id": transition_id},
            "fields": {"resolution": {"name": resolution_state}},
        }
        result = service_desk_request_post(
            TRANSITION_API % (shared.globals.ROOT_URL, shared.globals.TICKET), update
        )
        if result.status_code != 204:
            post_comment(
                f"Unable to mark issue as Done. Error code {result.status_code} "
                f"and message '{result.text}'",
                False,
            )
            post_comment(
                f"Transition ID was {transition_id} and resolution name was {resolution_state}",
                False,
            )


def assign_issue_to(person):
    """Assign the issue to the specified email address."""
    print(f"assign_issue_to({person})")
    update = {"name": person}
    result = service_desk_request_put(
        f"{shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}/assignee",
        update,
    )
    # On Cloud, this can fail because of GDPR settings so we need to
    # take extra steps if that happens.
    if result.status_code == 400:
        # Check the error message
        error = result.json()
        if "errorMessages" in error and error["errorMessages"][0] == GDPR_ERROR:
            result = assign_issue_to_account_id(person)
    # Either not the right error message or we've just tried using assign issue to account_id
    if result.status_code != 204:
        post_comment(
            f"Unable to assign issue to '{person}'. Error code "
            f"{result.status_code} and message '{result.text}'",
            False,
        )


def assign_issue_to_account_id(person):
    """Convert the person's name to an anonymised account id and then assign issue."""
    print(f"assign_issue_to_account_id({person})")

    # The original mechanism of using multiProjectSearch to find users that issues
    # could be assigned to wasn't working for the JSD Automation bot. A (temporary)
    # alternative method has been devised - get a list of all of the users assignable
    # for the current issue, iterate to match the email address and then assign it.
    result = service_desk_request_get(
        f"{shared.globals.ROOT_URL}/rest/api/3/user/assignable/search?issueKey={shared.globals.TICKET}"
    )
    if result.status_code != 200:
        return result
    # Iterate ...
    data = result.json()
    for item in data:
        if "emailAddress" in item and item["emailAddress"] == person:
            account_id = item["accountId"]
            update = {"accountId": account_id}
            return service_desk_request_put(
                f"{shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}/assignee",
                update,
            )
    # Failed to match
    return result # Not really helpful but the status code isn't 204 so we'll get a comment

    ### OLD METHOD
    # result = service_desk_request_get(
    #     f"{shared.globals.ROOT_URL}/rest/api/2/user/assignable/multiProjectSearch"
    #     f"?query={person}&projectKeys={shared.globals.PROJECT}"
    # )
    # if result.status_code != 200:
    #     return result
    # # Should return us precisely one user ...
    # data = result.json()
    # print(f"{len(data)} results")
    # if len(data) != 1:
    #     for item in data:
    #         print(item)
    # if data == []:
    #     return result  # Not really helpful but the status code isn't 204 so we'll get a comment
    # account_id = data[0]["accountId"]
    # update = {"accountId": account_id}
    # return service_desk_request_put(
    #     f"{shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}/assignee",
    #     update,
    # )


def transition_request_to(name, check_transition_name=False, check_destination_name=True):
    """Transition the issue to the specified transition name."""
    lower_name = name.lower()
    current_state = get_current_status()
    if current_state is not None and current_state.lower() == lower_name:
        # Nothing to do.
        return
    transition_id = find_transition(lower_name, check_transition_name, check_destination_name)
    if transition_id != 0:
        update = {"transition": {"id": transition_id}}
        result = service_desk_request_post(
            TRANSITION_API % (shared.globals.ROOT_URL, shared.globals.TICKET), update
        )
        if result.status_code != 204:
            post_comment(
                f"Transition '{name}' failed with error code "
                f"{result.status_code} and message '{result.text}'",
                False
            )
        else:
            print(f"{shared.globals.TICKET}: transitioned ticket to {name}")


def find_transition(transition_name, check_transition_name=False, check_destination_name=True):
    """Find a transition to get to the desired state and return the matching ID."""
    url = TRANSITION_API % (shared.globals.ROOT_URL, shared.globals.TICKET)
    lower_name = transition_name.lower()
    result = service_desk_request_get(url)
    if result.status_code != 200:
        post_comment(
            "Unable to get transitions for issue. Error code "
            f"{result.status_code} and message '{result.text}'",
            False,
        )
        return 0
    j = result.json()
    for transition in j["transitions"]:
        if check_destination_name and transition["to"]["name"].lower() == lower_name:
            return transition["id"]
        if check_transition_name and transition["name"].lower() == lower_name:
            return transition["id"]

    msg = "Unable to find transition to get to state "
    msg += f"'{transition_name}' for issue {shared.globals.TICKET}\r\n"
    msg += f"Current status is {get_current_status()}\r\n"
    msg += result.text
    post_comment(msg, False)
    return 0


def get_current_status():
    """Return the name of the ticket's current status."""
    url = f"{shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}?fields=status"
    result = service_desk_request_get(url)
    if result.status_code != 200:
        print(
            "Unable to get current status. Request status code is ", result.status_code
        )
        return None
    j = result.json()
    return j["fields"]["status"]["name"]


def central_comment_handler(
    supported_public_keywords, supported_private_keywords, transition_if_resolved=None
):
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

    if (
        get_current_status() == "Resolved"
        and comment is not None
        and not user_is_bot(comment["author"])
        and transition_if_resolved is not None
    ):
        transition_request_to(transition_if_resolved)

    if comment is not None and not (comment["public"]) and keyword in supported_private_keywords:
        return (comment, keyword)
    if comment is not None and comment["public"] and keyword in supported_public_keywords:
        return (comment, keyword)

    return (comment, None)


def get_keyword_from_comment(comment):
    """Extract the keyword from the comment."""
    if comment is None:
        return None

    # Keywords are always single words so we just take the first word and
    # return it in lower-case.
    # More complicated than using just split because we don't want punctuation.
    return (
        "".join((char if char.isalpha() else " ") for char in comment["body"])
        .split()[0]
        .lower()
    )


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
            f"{shared.globals.ROOT_URL}/rest/servicedeskapi/request/"
            f"{shared.globals.TICKET}/comment?start={start}"
        )
        if result.status_code != 200:
            return None
        j = result.json()
        # If we're on the last page of comments, return the last comment!
        if j["isLastPage"]:
            if len(j["values"]) == 0:
                return None
            return j["values"][-1]
        # Get the next batch of comments
        start += j["size"]


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
    Set the specified custom field to be the list of approvers,
    making them request participants as well if needed.
    """
    updating_via_webhook = "jsm_customfield_webhook" in shared.globals.CONFIGURATION and \
        custom_field in shared.globals.CONFIGURATION["jsm_customfield_webhook"]
    flat_list = shared_ldap.flatten_list(approver_list)
    if updating_via_webhook:
        approvers = {
            "id": []
        }
    else:
        approvers = {
            "fields": {
                custom_field: []
            }
        }
    for item in flat_list:
        if item != "":
            item_email = None
            # Cope with being sent email addresses already
            if "@" in item:
                item_email = item
            else:
                obj = shared_ldap.get_object(item, ["mail"])
                if obj is not None:
                    item_email = obj.mail.value
            if item_email is not None:
                item_account_id = find_account_id(item_email)
                if item_account_id is not None:
                    print(f"Adding {item_account_id} for {item_email}")
                    if updating_via_webhook:
                        approvers["id"].append(item_account_id)
                    else:
                        approvers["fields"][custom_field].append({"id": item_account_id})
                if add_to_request_participants:
                    # Add them as a request participant so that they get copies of
                    # any comment notifications.
                    add_request_participant(item_email)
    if updating_via_webhook:
        trigger_jsm_customfield_webhook(custom_field, approvers)
    else:
        update_approvers_via_api(approvers)


def trigger_jsm_customfield_webhook(custom_field, approvers):
    """
    Trigger the automation rule that is a webhook to add each person to the specified custom field
    """
    print("trigger_jsm_customfield_webhook")
    webhook_url = shared.globals.CONFIGURATION["jsm_customfield_webhook"][custom_field]
    trigger_url = f"{webhook_url}?issue={shared.globals.TICKET}"
    result = service_desk_request_post(trigger_url, approvers)
    print(result.status_code)
    print(result.text)

def update_approvers_via_api(approvers):
    """Use the Jira API to update the approvers field"""
    print(shared.globals.TICKET_DATA["self"])
    print(f"assign_approvers: {json.dumps(approvers)}")
    result = service_desk_request_put(shared.globals.TICKET_DATA["self"], approvers)
    print(result.status_code)
    print(result.text)
    if result.status_code != 204:
        post_comment(
            f"Got error {result.text} ({result.status_code}) when setting the"
            f" approvers:\r\n{{panel}}{approvers}{{panel}}\r\n",
            False,
        )


def set_summary(summary):
    """Set the summary of the issue to the specified string."""
    data = {"update": {"summary": [{"set": summary}]}}
    result = service_desk_request_put(
        f"{shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}",
        data,
    )
    print(f"set_summary: {result.status_code} {result.text}")
    # Update our copy of the ticket data to reflect the new summary
    shared.globals.TICKET_DATA["fields"]["summary"] = summary


def set_customfield(custom_field, value):
    """Set the specified custom field to the specified value."""
    data = {
        "fields": {
            custom_field: {"value": value}
        }
    }
    print(f"set_customfield: {data}")
    result = service_desk_request_put(
        f"{shared.globals.ROOT_URL}/rest/api/2/issue/{shared.globals.TICKET}",
        data
    )
    print(f"set_customfield: {result.status_code} {result.text}")


def find_account_id(email_address: str) -> Union[str, None]:
    """Look up the email address and return the corresponding account ID or None if not found"""
    result = service_desk_request_get(
        f"{shared.globals.ROOT_URL}/rest/api/2/user/search?query={email_address}"
    )
    if result.status_code != 200:
        return None
    data = result.json()
    if len(data) == 1:
        return data[0]["accountId"]
    return None


def find_account_from_id(account_id: str):
    """Look up the specified account ID and return the corresponding user or None if not found"""
    result = service_desk_request_get(
        f"{shared.globals.ROOT_URL}/rest/api/2/user?accountId={account_id}"
    )
    if result.status_code == 200:
        return result.json()
    return None


def add_request_participant(email_address):
    """
    Add the specified email address as a request participant to the current
    issue.
    """
    if is_request_participant(email_address):
        return
    account_id = find_account_id(email_address)
    if account_id is None:
        post_comment(
            f"Unable to add {email_address} as request participant "
            f"to {shared.globals.TICKET}. User not found.",
            False,
        )
        return
    update = {"accountIds": [account_id]}
    result = service_desk_request_post(
        f"{shared.globals.ROOT_URL}/rest/servicedeskapi/"
        f"request/{shared.globals.TICKET}/participant",
        update,
    )
    if result.status_code != 200:
        post_comment(
            f"Unable to add {email_address} as request "
            f"participant to {shared.globals.TICKET}. "
            f"Error code {result.status_code} and message '{result.text}'",
            False,
        )


def is_request_participant(email_address):
    """
    Check if the specified email address is a request participant on the
    current issue.
    """
    start = 0
    while True:
        result = service_desk_request_get(
            f"{shared.globals.ROOT_URL}/rest/servicedeskapi/request/"
            f"{shared.globals.TICKET}/participant?start={start}"
        )
        if result.status_code != 200:
            return False
        j = result.json()
        for value in j["values"]:
            if value["emailAddress"] == email_address:
                return True
        if not j["isLastPage"]:
            start += j["size"]
        else:
            return False


def get_request_participants():
    """Returns a lit of request participants for the current issue."""
    list_of_participants = []
    start = 0
    while True:
        result = service_desk_request_get(
            f"{shared.globals.ROOT_URL}/rest/servicedeskapi/request/"
            f"{shared.globals.TICKET}/participant?start={start}"
        )
        if result.status_code != 200:
            return []
        j = result.json()
        for value in j["values"]:
            list_of_participants.append(value["emailAddress"])
        if not j["isLastPage"]:
            start += j["size"]
        else:
            return list_of_participants


def sd_headers():
    """Return the required headers for Service Desk."""
    return {
        "Authorization": f"Basic {shared.globals.SD_AUTH}",
        "Content-Type": "application/json",
        "X-ExperimentalApi": "true",
    }


def service_desk_request_get(url):
    """Centralised routine to GET from Service Desk."""
    headers = sd_headers()
    return requests.get(url, headers=headers, timeout=30)


def service_desk_request_post(url, data):
    """Centralised routine to POST to Service Desk."""
    headers = sd_headers()
    return requests.post(url, headers=headers, json=data, timeout=30)


def service_desk_request_put(url, data):
    """Centralised routine to PUT to Service Desk."""
    headers = sd_headers()
    return requests.put(url, headers=headers, json=data, timeout=30)
