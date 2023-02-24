#!/usr/bin/python3
""" Test the shared Service Desk library. """

import json
import mock
import pytest
import responses

from requests.auth import HTTPBasicAuth

import shared.shared_sd as shared_sd
import shared.globals


@responses.activate
def test_get_servicedesk_id_1():
    """ Check the code correctly determines a project's ID. """
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/servicedesk",
        json={
            "values": [
                {
                    "projectKey": "ITS",
                    "id": 3
                }
            ]
        },
        status=200
    )
    result = shared_sd.get_servicedesk_id("ITS")
    assert result == 3


@responses.activate
def test_get_servicedesk_id_2():
    """ Test behaviour when the project ID cannot be matched. """
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/servicedesk",
        json={
            "values": [
                {
                    "projectKey": "ITS",
                    "id": 3
                }
            ]
        },
        status=200
    )
    result = shared_sd.get_servicedesk_id("FOO")
    assert result == -1


@responses.activate
def test_get_servicedesk_id_3():
    """ Test behaviour when the credentials are invalid. """
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/servicedesk",
        json={},
        status=404
    )
    result = shared_sd.get_servicedesk_id("ITS")
    assert result == -1


@responses.activate
def test_post_comment():
    """ Test post_comment function. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "1"
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/request/1/comment",
        status=201
    )
    shared_sd.post_comment("Comment", True)


@responses.activate
def test_post_comment_failure():
    """ Test behaviour when error back from POST. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "1"
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/request/1/comment",
        status=404
    )
    shared_sd.post_comment("Comment", True)


@responses.activate
def test_sd_request_get():
    """ Test calls to service_desk_request_get. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    responses.add(
        responses.GET,
        "https://mock-server/rest/api/foobar",
        json={'error': 'not found'},
        status=404
    )
    resp = shared_sd.service_desk_request_get(
        "https://mock-server/rest/api/foobar")
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == (
        "https://mock-server/rest/api/foobar")
    # Make sure that the added headers are there
    assert "content-type" in responses.calls[0].request.headers
    assert responses.calls[0].request.headers[
        "content-type"] == "application/json"
    assert "X-ExperimentalApi" in responses.calls[0].request.headers
    assert responses.calls[0].request.headers[
        "X-ExperimentalApi"] == "true"
    assert responses.calls[0].response.text == '{"error": "not found"}'
    assert resp.json() == {"error": "not found"}


@responses.activate
def test_sd_request_post():
    """ Test calls to service_desk_request_post. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    responses.add(
        responses.POST,
        "https://mock-server/rest/api/foobar",
        status=202
    )
    resp = shared_sd.service_desk_request_post(
        "https://mock-server/rest/api/foobar",
        "data"
    )
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == (
        "https://mock-server/rest/api/foobar")
    # Make sure that the added headers are there
    assert "content-type" in responses.calls[0].request.headers
    assert responses.calls[0].request.headers[
        "content-type"] == "application/json"
    assert "X-ExperimentalApi" in responses.calls[0].request.headers
    assert responses.calls[0].request.headers[
        "X-ExperimentalApi"] == "true"
    assert resp.status_code == 202


@responses.activate
def test_sd_request_put():
    """ Test calls to service_desk_request_put. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    responses.add(
        responses.PUT,
        "https://mock-server/rest/api/foobar",
        status=200
    )
    resp = shared_sd.service_desk_request_put(
        "https://mock-server/rest/api/foobar",
        "data"
    )
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == (
        "https://mock-server/rest/api/foobar")
    # Make sure that the added headers are there
    assert "content-type" in responses.calls[0].request.headers
    assert responses.calls[0].request.headers[
        "content-type"] == "application/json"
    assert "X-ExperimentalApi" in responses.calls[0].request.headers
    assert responses.calls[0].request.headers[
        "X-ExperimentalApi"] == "true"
    assert resp.status_code == 200


@mock.patch(
    'shared.shared_sd.get_servicedesk_id',
    return_value=-1,
    autospec=True
)
def test_save_as_attachment_bad_project(mock_get_servicedesk_id):
    """ Test handling of a bad project when saving attachment. """
    result = shared_sd.save_text_as_attachment(
        "filename",
        "content",
        "comment",
        False
    )
    assert mock_get_servicedesk_id.called is True
    assert result == -1


@mock.patch(
    'shared.shared_sd.get_servicedesk_id',
    return_value=3,
    autospec=True
)
@responses.activate
def test_save_as_attachment_bad_status(mock_get_servicedesk_id):
    """ Test handling of a bad status when saving attachment. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/servicedesk/3"
        "/attachTemporaryFile",
        status=404
    )
    result = shared_sd.save_text_as_attachment(
        "filename",
        "content",
        "comment",
        False
    )
    assert mock_get_servicedesk_id.called is True
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == (
        "https://mock-server/rest/servicedeskapi/servicedesk/3"
        "/attachTemporaryFile")
    assert result == 404


@mock.patch(
    'shared.shared_sd.get_servicedesk_id',
    return_value=3,
    autospec=True
)
@responses.activate
def test_save_as_attachment_good_status(mock_get_servicedesk_id):
    """ Test handling of saving attachment. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "ITS-1"
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/servicedesk/3"
        "/attachTemporaryFile",
        json={
            "temporaryAttachments": [
                {
                    "temporaryAttachmentId": 42
                }
            ]
        },
        status=201
    )
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/request/ITS-1/attachment",
        status=200
    )
    result = shared_sd.save_text_as_attachment(
        "filename",
        "content",
        "comment",
        False
    )
    assert mock_get_servicedesk_id.called is True
    assert len(responses.calls) == 2
    assert responses.calls[0].request.url == (
        "https://mock-server/rest/servicedeskapi/servicedesk/3"
        "/attachTemporaryFile")
    assert responses.calls[1].request.url == (
        "https://mock-server/rest/servicedeskapi/request/ITS-1/attachment")
    assert result == 200


@mock.patch(
    'shared.shared_sd.get_servicedesk_id',
    return_value=3,
    autospec=True
)
@responses.activate
def test_save_as_attachment_good_and_bad_status(mock_get_servicedesk_id):
    """ Test handling of saving attachment. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "ITS-1"
    shared.globals.PROJECT = "MOCK"
    shared.globals.CONFIGURATION = {
        'bot_name': 'mockbot'
    }
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/servicedesk/3"
        "/attachTemporaryFile",
        json={
            "temporaryAttachments": [
                {
                    "temporaryAttachmentId": 42
                }
            ]
        },
        status=201
    )
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/request/ITS-1/attachment",
        status=404
    )
    result = shared_sd.save_text_as_attachment(
        "filename",
        "content",
        "comment",
        False
    )
    assert mock_get_servicedesk_id.called is True
    assert len(responses.calls) == 2
    assert responses.calls[0].request.url == (
        "https://mock-server/rest/servicedeskapi/servicedesk/3"
        "/attachTemporaryFile")
    assert responses.calls[1].request.url == (
        "https://mock-server/rest/servicedeskapi/request/ITS-1/attachment")
    assert result == 404


@mock.patch(
    'shared.custom_fields.get',
    return_value=None
)
def test_ticket_request_type_1(mock_get_cf_id):
    """ Test handling of failure to determine custom field. """
    with pytest.raises(shared_sd.CustomFieldLookupFailure):
        shared_sd.ticket_request_type(None)
    assert mock_get_cf_id.called is True


@mock.patch(
    'shared.custom_fields.get',
    return_value=10100
)
def test_ticket_request_type_2(mock_get_cf_id):
    """ Test handling of malformed issue. """
    data = {
        "fields": {}
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.ticket_request_type(data)
    assert mock_get_cf_id.called is True


@mock.patch(
    'shared.custom_fields.get',
    return_value=10100
)
def test_ticket_request_type_3(mock_get_cf_id):
    """ Test handling of custom fields in request type. """
    data =  {
        "fields": {
            10100: {
                "requestType": {
                    "id": "206",
                }
            }
        }
    }
    # Stop pylint complaining we don't use the argument.
    _ = mock_get_cf_id
    result = shared_sd.ticket_request_type(data)
    assert result == "206"


@mock.patch(
    'shared.custom_fields.get',
    return_value=10100
)
def test_ticket_request_type_4(mock_get_cf_id):
    """ Test handling of custom fields in request type. """
    data =  {
        "fields": {
            10100: None
            }
        }
    # Stop pylint complaining we don't use the argument.
    _ = mock_get_cf_id
    result = shared_sd.ticket_request_type(data)
    assert result == None


def test_usable_ticket_data():
    """ Test various scenarios to see if the ticket data is usable. """
    result = shared_sd.usable_ticket_data({})
    assert result is False

    data = {
        "webhookEvent": "foo"
    }
    result = shared_sd.usable_ticket_data(data)
    assert result is False

    data = {
        "webhookEvent": "jira:issue_updated"
    }
    result = shared_sd.usable_ticket_data(data)
    # Should still be false because not enough data
    assert result is False

    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "foo"
    }
    result = shared_sd.usable_ticket_data(data)
    assert result is False

    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_assigned"
    }
    result = shared_sd.usable_ticket_data(data)
    assert result is True

    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic"
    }
    result = shared_sd.usable_ticket_data(data)
    assert result is True


def test_trigger_is_assignment():
    """ Test the code that determines if trigger is ticket assignment. """
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_assigned",
        "changelog": {
            "items": [
                {
                    "field": "assignee",
                    "fieldtype": "jira",
                    "from": "from",
                    "to": "to"
                }
            ]
        }
    }
    match, t_to = shared_sd.trigger_is_assignment(data)
    assert match is True
    assert t_to == "to"


def test_trigger_is_transition():
    """ Test the code that determines if trigger is transition. """
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic",
        "changelog": {
            "items": [
                {
                    "field": "status",
                    "fieldtype": "jira",
                    "from": "from",
                    "fromString": "fromString",
                    "to": "to",
                    "toString": "toString"
                }
            ]
        }
    }
    match, t_to = shared_sd.trigger_is_transition(data)
    assert match is True
    assert t_to == "toString"


def test_look_for_trigger_1():
    """ Test the code that determines the cause of the trigger. """
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic"
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.look_for_trigger(None, data, None)
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic",
        "changelog": {}
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.look_for_trigger(None, data, None)
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic",
        "changelog": {
            "items": [
                {
                    "field": "test",
                    "fieldtype": "jira",
                    "from": "from",
                    "fromString": "fromString",
                    "to": "to",
                    "toString": "toString"
                }
            ]
        }
    }
    match, t_to = shared_sd.look_for_trigger("test", data, "to")
    assert match is True
    assert t_to == "to"
    match, t_to = shared_sd.look_for_trigger("fail", data, None)
    assert match is False
    assert t_to is None


def test_look_for_trigger_2(capsys):
    """ Test the code that determines the cause of the trigger. """
    #  This code is for testing when a nonusable ticket data is passed.
    data = {
        "No_webhookEvent": "jira:issue_updated",
    }
    shared_sd.look_for_trigger("test", data, "to")
    captured = capsys.readouterr()
    assert captured.out == "No webhookEvent field in ticket data\nNo usable ticket data for Jira trigger\n"


def test_automation_triggered_comment_1():
    """ Test the code that determines if the automation wrote the last comment. """
    result = shared_sd.automation_triggered_comment({})
    assert result is False

    shared.globals.CONFIGURATION = {
        "bot_name": "test_bot"
    }
    data = {
        "comment": {
            "author": {
                "emailAddress": shared.globals.CONFIGURATION["bot_name"]
            }
        },
        "fields": {
            "comment": {
                "comments": [
                    {
                        "body": "test comment",
                        "author": {
                            "emailAddress": shared.globals.CONFIGURATION["bot_name"]
                        }
                    }
                ]
            }
        }
    }
    result = shared_sd.automation_triggered_comment(data)
    assert result is True


def test_automation_triggered_comment_2():
    """ Test the code that determines if the automation wrote the last comment. """
    shared.globals.CONFIGURATION = {
        "bot_name": "test_bot"
    }
    data = {
        "fields": {
            "comment": {
                "comments": [
                    {
                        "body": "test comment",
                        "author": {
                            "emailAddress": shared.globals.CONFIGURATION["bot_name"]
                        }
                    }
                ]
            }
        }
    }
    result = shared_sd.automation_triggered_comment(data)
    assert result is True


@mock.patch(
    'shared.shared_sd.print'
)
@mock.patch(
    'shared.shared_sd.save_text_as_attachment',
    autospec=True
)
def test_save_ticket_data_as_attachment_1(
        mock_save_text_as_attachment, mock_print):
    """ Test the debug code that saves the ticket data as an attachment. """
    shared_sd.save_ticket_data_as_attachment({})
    assert mock_print.called is False
    assert mock_save_text_as_attachment.called is True


@mock.patch(
    'shared.shared_sd.print'
)
@mock.patch(
    'shared.shared_sd.save_text_as_attachment',
    autospec=True
)
def test_save_ticket_data_as_attachment_2(
        mock_save_text_as_attachment, mock_print):
    """ Test the debug code that saves the ticket data as an attachment. """
    data = {
        "comment": {
            "author": {
                "emailAddress": shared.globals.CONFIGURATION["bot_name"]
            }
        }
    }
    shared_sd.save_ticket_data_as_attachment(data)
    assert mock_print.called is True
    assert mock_save_text_as_attachment.called is False

def test_get_field():
    """ Test get_field. """
    assert shared_sd.get_field({}, "fred") is None
    ticket_data = {
        "fields": {
            "123": "My value"
        }
    }
    result = shared_sd.get_field(ticket_data, "123")
    assert result == "My value"


def test_reporter_email_address():
    """ Test reporter_email_address. """
    assert shared_sd.reporter_email_address({}) is None
    ticket_data = {
        "fields": {
            "reporter": {
                "emailAddress": "My value"
            }
        }
    }
    result = shared_sd.reporter_email_address(ticket_data)
    assert result == "My value"


@responses.activate
def test_get_request_type_id():
    """ Test get_request_type_id. """
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/servicedesk/MOCK/requesttype",
        json={
            "values": [
                {
                    "name": "MOCK_RT",
                    "id": 3
                }
            ]
        },
        status=200
    )
    result = shared_sd.get_request_type_id("MOCK_RT", "MOCK")
    assert result == 3


@responses.activate
def test_get_request_type_id_2():
    """ Test get_request_type_id. """
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/servicedesk/MOCK/requesttype",
        json={
            "values": [
                {
                    "name": "MOCK_RT",
                    "id": 3
                }
            ]
        },
        status=200
    )
    result = shared_sd.get_request_type_id("MOCK_FAIL", "MOCK")
    assert result == -1


@responses.activate
def test_create_request():
    """ Test create_request. """
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.POST,
        "https://mock-server/rest/servicedeskapi/request",
        json={'error': 'not found'},
        status=404
    )
    shared_sd.create_request({})

@mock.patch(
    'shared.shared_sd.assign_issue_to',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.find_transition',
    return_value=2,
    autospec=True
)
@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True
)
@responses.activate
def test_resolve_ticket(mi1, mi2, mi3):
    """ Test resolve_ticket. """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    shared.globals.CONFIGURATION = {
        "bot_name": "mock_bot"
    }
    responses.add(
        responses.POST,
        "https://mock-server/rest/api/2/issue/mock-ticket/transitions",
        json={'error': 'not found'},
        status=404
    )
    shared_sd.resolve_ticket()
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True


@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True
)
@responses.activate
def test_assign_issue_to_1(mi1):
    """ Test assign_issue_to when the response
    status code is non 204 """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.PUT,
        "https://mock-server/rest/api/2/issue/mock-ticket/assignee",
        json={'error': 'not found'},
        status=404
    )
    shared_sd.assign_issue_to("mock-user")
    assert mi1.called is True


@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True
)    
@mock.patch(
    'shared.shared_sd.assign_issue_to_account_id',
    autospec=True
)
@responses.activate
def test_assign_issue_to_2(mi1, mi2):
    """ Test assign_issue_to when the response
    ststus code is 400 AND the error message
    contains the GDPR error"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.PUT,
        "https://mock-server/rest/api/2/issue/mock-ticket/assignee",
        json={
            "errorMessages": [
                ("'accountId' must be the only user"
                " identifying query parameter in GDPR strict mode."
                )
            ]
        },
        status=400,
        content_type='application/json'
    )
    shared_sd.assign_issue_to("mock-user")
    assert mi1.called is True
    assert mi2.called is True


@responses.activate
def test_assign_issue_to_3():
    """ Test assign_issue_to when the response
    status code is 204 """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.PUT,
        "https://mock-server/rest/api/2/issue/mock-ticket/assignee",
        status=204,
    )
    shared_sd.assign_issue_to("mock-user")


@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True
)
@responses.activate
def test_find_transition_failure(mi1):
    """ Test find_transition. """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.GET,
        "https://mock-server/rest/api/2/issue/mock-ticket/transitions",
        json={'error': 'not found'},
        status=404
    )
    shared_sd.find_transition("Foo")
    assert mi1.called is True


@responses.activate
def test_find_transition_success():
    """ Test find_transition. """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.GET,
        "https://mock-server/rest/api/2/issue/mock-ticket/transitions",
        json={
            'transitions': [
                {
                    "id": "mock_transition_id",
                    "to": {
                        "name": "mock_transition_name"
                    }
                }
            ]
        },
        status=200
    )
    assert shared_sd.find_transition("Mock_Transition_Name") == "mock_transition_id"


@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.get_current_status',
    return_value="Mock result",
    autospec=True
)
@responses.activate
def test_find_transition_failure2(mi1, mi2):
    """ Test find_transition. """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.GET,
        "https://mock-server/rest/api/2/issue/mock-ticket/transitions",
        json={
            'transitions': [
                {
                    "id": "mock_transition_id",
                    "to": {
                        "name": "mock_transition_name"
                    }
                }
            ]
        },
        status=200
    )
    assert shared_sd.find_transition("ThisOneDoesntExist") == 0
    assert mi1.called is True
    assert mi2.called is True


@responses.activate
def test_get_current_status_1():
    """ Test get_current_status. """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.GET,
        "https://mock-server/rest/api/2/issue/mock-ticket?fields=status",
        json={
            "fields": {
                "status": {
                    "name": "mock-current-status"
                }
            }
        },
        status=200
    )
    assert shared_sd.get_current_status() == "mock-current-status"


@responses.activate
def test_get_current_status_2():
    """ Test get_current_status when return code is non 200."""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.GET,
        "https://mock-server/rest/api/2/issue/mock-ticket?fields=status",
        json={},
        status=400
    )
    assert shared_sd.get_current_status() == None


@mock.patch(
    'shared.shared_sd.get_current_status',
    return_value='mock_current_status',
    autospec=True
)
def test_transition_request_to(mi1):
    """ Test transition_request_to """
    # Simple case first - already there
    shared_sd.transition_request_to("MOCK_CURRENT_STATUS")
    assert mi1.called is True


@mock.patch(
    'shared.shared_sd.get_current_status',
    return_value='mock_undesired_status',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.find_transition',
    return_value=1,
    autospec=True
)
@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True
)
@responses.activate
def test_transition_request_to2(mi1, mi2, mi3):
    """ A second test of transition_request_to """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.POST,
        "https://mock-server/rest/api/2/issue/mock-ticket/transitions",
        status=404
    )
    shared_sd.transition_request_to("mock_current_status")
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True

def test_get_keyword_from_comment():
    """ Test get_keyword_from_comment """
    assert shared_sd.get_keyword_from_comment(None) is None
    comment = {
        "body": "RETRY."
    }
    assert shared_sd.get_keyword_from_comment(comment) == "retry"
    comment = {
        "body": "Retry this operation"
    }
    assert shared_sd.get_keyword_from_comment(comment) == "retry"

@responses.activate
def test_get_latest_comment_1():
    """ Test get_latest_comment """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/request/mock-ticket/comment?start=0",
        status=404
    )
    first_blob = {
        "isLastPage": False,
        "values": [
            "one",
            "two"
        ],
        "size": 2
    }
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/request/mock-ticket/comment?start=0",
        body=json.dumps(first_blob),
        status=200,
        content_type='application/json'
    )
    second_blob = {
        "isLastPage": True,
        "values": [
            "three",
            "four"
        ],
        "size": 2
    }
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/request/mock-ticket/comment?start=2",
        body=json.dumps(second_blob),
        status=200,
        content_type='application/json'
    )

    assert shared_sd.get_latest_comment() is None
    assert shared_sd.get_latest_comment() == "four"


@responses.activate
def test_get_latest_comment_2():
    """ Test get_latest_comment 
    when values are empty"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    first_blob = {
        "isLastPage": True,
        "values": [],
        "size": 2
    }
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/request/mock-ticket/comment?start=0",
        body=json.dumps(first_blob),
        status=200,
        content_type='application/json'
    )
    result = shared_sd.get_latest_comment()
    assert result == None


FAKE_COMMENT_1 = {
        "author": {
            "name": "not_mock_bot"
        },
        "public": True
    }

FAKE_COMMENT_2 = {
        "author": {
            "name": "not_mock_bot"
        },
        "public": False
    }

@mock.patch(
    "shared.shared_sd.get_latest_comment",
    return_value=FAKE_COMMENT_1,
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_keyword_from_comment",
    return_value=None,
    autospec=True
)
@mock.patch(
    "shared.shared_sd.transition_request_to",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_current_status",
    return_value="Resolved",
    autospec=True
)
def test_central_comment_handler(mi1, mi2, mi3, mi4):
    """ Test central_comment_handler """
    # Test the resolution handling
    shared.globals.CONFIGURATION = {
        "bot_name": "mock_bot"
    }
    comment, keyword = shared_sd.central_comment_handler(
        ["public"], ["private"], "Waiting for support")
    assert comment == FAKE_COMMENT_1
    assert keyword is None
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert mi4.called is True

@mock.patch(
    "shared.shared_sd.get_current_status",
    return_value="Waiting for support",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_keyword_from_comment",
    return_value="public",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_latest_comment",
    return_value=FAKE_COMMENT_1,
    autospec=True
)
def test_central_comment_handler2(mi1, mi2, mi3):
    """ Test central_comment_handler """
    comment, keyword = shared_sd.central_comment_handler(
        ["public"], ["private"], "Waiting for support")
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert comment == FAKE_COMMENT_1
    assert keyword == "public"

@mock.patch(
    "shared.shared_sd.get_current_status",
    return_value="Waiting for support",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_keyword_from_comment",
    return_value="public",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_latest_comment",
    return_value=FAKE_COMMENT_1,
    autospec=True
)
def test_central_comment_handler2(mi1, mi2, mi3):
    """ Test central_comment_handler """
    comment, keyword = shared_sd.central_comment_handler(
        ["public"], ["private"], "Waiting for support")
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert comment == FAKE_COMMENT_1
    assert keyword == "public"

@mock.patch(
    "shared.shared_sd.get_current_status",
    return_value="Waiting for support",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_keyword_from_comment",
    return_value="public",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_latest_comment",
    return_value=FAKE_COMMENT_1,
    autospec=True
)
def test_central_comment_handler2(mi1, mi2, mi3):
    """ Test central_comment_handler """
    comment, keyword = shared_sd.central_comment_handler(
        ["public"], ["private"], "Waiting for support")
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert comment == FAKE_COMMENT_1
    assert keyword == "public"

@mock.patch(
    "shared.shared_sd.get_current_status",
    return_value="Waiting for support",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_keyword_from_comment",
    return_value="private",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_latest_comment",
    return_value=FAKE_COMMENT_2,
    autospec=True
)
def test_central_comment_handler3(mi1, mi2, mi3):
    """ Test central_comment_handler """
    comment, keyword = shared_sd.central_comment_handler(
        ["public"], ["private"], "Waiting for support")
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert comment == FAKE_COMMENT_2
    assert keyword == "private"


@mock.patch(
    "shared.shared_sd.get_current_status",
    return_value=None,
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_keyword_from_comment",
    return_value="private",
    autospec=True
)
@mock.patch(
    "shared.shared_sd.get_latest_comment",
    return_value=FAKE_COMMENT_2,
    autospec=True
)
def test_central_comment_handler4(mi1, mi2, mi3):
    """ Test central_comment_handler
    when ticket status is None """
    result = shared_sd.central_comment_handler(
        ["public"], ["private"])
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert result == (None, None)


@responses.activate
def test_get_servicedesk_request_types_1():
    """Test get_servicedesk_request_types when response code is 200 """
    shared.globals.ROOT_URL = "https://mock-server"
    project_id = "ITS"
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/servicedesk/%s/requesttype" % (
            shared.globals.ROOT_URL, project_id
        ),
        json={
            "values":[
                {
                    "id": "1001",
                    "name": "foo"
                }
            ]
        },
        status=200
    )
    result = shared_sd.get_servicedesk_request_types(project_id)
    assert result["values"][0]["name"] == "foo"


@responses.activate
def test_get_servicedesk_request_types_2():
    """Test get_servicedesk_request_types when response code is not 200 """
    shared.globals.ROOT_URL = "https://mock-server"
    project_id = "ITS"
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/servicedesk/%s/requesttype" % (
            shared.globals.ROOT_URL, project_id
        ),
        json={
            "values":[
                {
                    "id": "1001",
                    "name": "foo"
                }
            ]
        },
        status=400
    )
    result = shared_sd.get_servicedesk_request_types(project_id)
    assert result == None


def test_ticket_issue_type():
    """Test ticket_issue_type"""
    data = {
        "fields": {
            "issuetype": {
                "name": "foo"
            }
        }
    }
    result = shared_sd.ticket_issue_type(data)
    assert result == "foo"


def test_get_user_field_1(capsys):
    """Test get_user_field when user_blob is None"""
    result = shared_sd.get_user_field(None, "foo")
    captured = capsys.readouterr()
    assert captured.out == "get_user_field: passed None as user blob\n"
    assert result == None


def test_get_user_field_2(capsys):
    """Test get_user_field when field_name is not in user_blob"""
    user_blob = {
        "test_field": "bar"
    }
    result = shared_sd.get_user_field(user_blob, "foo")
    captured = capsys.readouterr()
    assert captured.out == 'get_user_field: requested field foo is not in the blob\n{"test_field": "bar"}\n'
    assert result == None


def test_get_user_field_3():
    """Test get_user_field when field_name is in user_blob"""
    user_blob = {
        "self": "https://mock-server/rest/servicedeskapi/request/2000/comment/1000",
        "foo": "test"
    }
    result = shared_sd.get_user_field(user_blob, "foo")
    assert result == "test"


@responses.activate
def test_get_user_field_4(capsys):
    """Test get_user_field when field_name value is None in user_blob
    AND repsonse code is non 200"""
    user_blob = {
        "self": "https://mock-server/rest/servicedeskapi/request/",
        "foo": None
    }
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/request/",
        json={"error": "not found"},
        status=404
    )
    result = shared_sd.get_user_field(user_blob, "foo")
    captured = capsys.readouterr()
    assert captured.out == ("Got status 404 when querying"
        " https://mock-server/rest/servicedeskapi/request/"
        " for user field foo\n")
    assert result == None


@responses.activate
def test_get_user_field_5():
    """Test get_user_field when field_name value is None in user_blob
    AND repsonse code is 200 AND field_name is in the result."""
    user_blob = {
        "self": "https://mock-server/rest/servicedeskapi/request/",
        "foo": None
    }
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/request/",
        json={
            'foo': 'bar'
        },
        status=200
    )
    result = shared_sd.get_user_field(user_blob, "foo")
    assert result == "bar"


@responses.activate
def test_get_user_field_6(capsys):
    """Test get_user_field when field_name value is None in user_blob
    AND repsonse code is 200 AND field_name is not in the result."""
    user_blob = {
        "self": "https://mock-server/rest/servicedeskapi/request/",
        "foo": None
    }
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/request/",
        json={
            "bar": "foo"
        },
        status=200
    )
    result = shared_sd.get_user_field(user_blob, "foo")
    captured = capsys.readouterr()
    assert captured.out == 'get_user_field: \'foo\' not in the self data\n{"bar": "foo"}\n'
    assert result == None


def test_get_assignee_field_1():
    """Test the function when 'fields' not in ticket data"""
    data = {}
    result = shared_sd.get_assignee_field(data, "foo")
    assert result == None


def test_get_assignee_field_2():
    """Test the function when 'assignee in ticket data"""
    data = {
        "fields": {
            "assignee": {
                "name": "some_assignee",
                "field_name": "foo"
            },
        }
    }
    result = shared_sd.get_assignee_field(data, "field_name")
    assert result == "foo"


def test_assignee_email_address_1():
    """Test to get assignee's email address"""
    data = {
        "fields": {
            "assignee": {
                "emailAddress": "test@test.com",
            },
        }
    }
    result = shared_sd.assignee_email_address(data)
    assert result == "test@test.com"


def test_assignee_email_address_2():
    """Check when assignee is not in ticket data"""
    data = {
        "fields": {
            "issuetype": {
                "name": "foo"
            }
        }
    }
    result = shared_sd.assignee_email_address(data)
    assert result == None


@mock.patch(
    'shared.shared_sd.urllib.parse.quote',
    return_value="m%40ck_group",
    autospec=True
)
@responses.activate
def test_get_group_members_1(mi1, capsys):
    """Test get_group_members when reponse code is non 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "%s/rest/api/2/group/member?groupname=%s" % (
        shared.globals.ROOT_URL, "m%40ck_group"),
        json={},
        status=404
    )
    result = shared_sd.get_group_members("m@ck_group")
    captured = capsys.readouterr()
    assert mi1.called is True
    assert captured.out == (
        "get_group_members(m@ck_group)"
        " failed with error code 404\n")
    assert result == []


@mock.patch(
    'shared.shared_sd.urllib.parse.quote',
    return_value="m%40ck_group",
    autospec=True
)
@responses.activate
def test_get_group_members_2(mi1):
    """Test get_group_members when reponse code is 200
    AND 'isLast' is True"""
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "%s/rest/api/2/group/member?groupname=%s" % (
        shared.globals.ROOT_URL, "m%40ck_group"),
        json={
            "values": [
                {
                    "name": "mock_user1"
                },
                {
                    "name": "mock_user2"
                }
            ],
            "isLast": True
        },
        status=200
    )
    result = shared_sd.get_group_members("m@ck_group")
    assert mi1.called is True
    assert result == ['mock_user1', 'mock_user2']


@mock.patch(
    'shared.shared_sd.urllib.parse.quote',
    return_value="m%40ck_group",
    autospec=True
)
@responses.activate
def test_get_group_members_3(mi1):
    """Test get_group_members when reponse code is 200
    AND 'isLast' is False"""
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "%s/rest/api/2/group/member?groupname=%s" % (
        shared.globals.ROOT_URL, "m%40ck_group"),
        json={
            "values": [
                {
                    "name": "mock_user1"
                },
                {
                    "name": "mock_user2"
                }
            ],
            "isLast": False,
            "maxResults": 1
        },
        status=200
    )
    responses.add(
        responses.GET,
        "%s/rest/api/2/group/member?groupname=%s&startAt=1" % (
        shared.globals.ROOT_URL, "m%40ck_group"),
        json={
            "values": [
                {
                    "name": "mock_user3"
                },
                {
                    "name": "mock_user4"
                }
            ],
            "isLast": True,
        },
        status=200
    )
    result = shared_sd.get_group_members("m@ck_group")
    assert mi1.called is True
    assert result == ['mock_user1', 'mock_user2', 'mock_user3', 'mock_user4']


@responses.activate
def test_groups_for_user_1():
    """Test groups_for_user when the response code is 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    email_address = "user@mock.com"
    responses.add(
        responses.GET,
        "%s/rest/api/2/user?username=%s&expand=groups" % (
            shared.globals.ROOT_URL, email_address
        ),
        json={
            "groups":{
                "items": [
                    {
                        "name": "foo"
                    }
                ]
            }

        },
        status=200
    )
    result = shared_sd.groups_for_user(email_address)
    assert result == ["foo"]


@responses.activate
def test_groups_for_user_2():
    """Test groups_for_user when the response code is non 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    email_address = "user@mock.com"
    responses.add(
        responses.GET,
        "%s/rest/api/2/user?username=%s&expand=groups" % (
            shared.globals.ROOT_URL, email_address
        ),
        json={
            "groups":{
                "items": [
                    {
                        "name": "foo"
                    }
                ]
            }

        },
        status=400
    )
    result = shared_sd.groups_for_user(email_address)
    assert result == []


@mock.patch(
    'shared.shared_sd.get_servicedesk_id',
    return_value=5,
    autospec=True
)
@responses.activate
def test_sd_orgs_1(mi1):
    """Test sd_orgs when response code is 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.PROJECT = 5
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/servicedesk/%s/organization" % (
            shared.globals.ROOT_URL, shared.globals.PROJECT
        ),
        json={
            "values":[
                {
                    "name": "foo",
                    "id": 5
                },
                {
                    "name": "bar",
                    "id": 6
                }
            ]
        },
        status=200
    )
    result = shared_sd.sd_orgs()
    assert mi1.called is True
    assert result == {'foo': 5, 'bar': 6}


@mock.patch(
    'shared.shared_sd.get_servicedesk_id',
    return_value=5,
    autospec=True
)
@responses.activate
def test_sd_orgs_2(mi1):
    """Test sd_orgs when response code is non 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.PROJECT = 5
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/servicedesk/%s/organization" % (
            shared.globals.ROOT_URL, shared.globals.PROJECT
        ),
        json={
            "values":[
                {
                    "name": "foo",
                    "id": 5
                }
            ]
        },
        status=400
    )
    result = shared_sd.sd_orgs()
    assert mi1.called is True
    assert result == {}


@responses.activate
def test_add_to_customfield_value_1(capsys):
    """Test add_to_customfield_value
    when response code is non 204"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    responses.add(
        responses.PUT,
        "%s/rest/api/2/issue/%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET
        ),
        json = {'error': 'not found'},
        status=404
    )
    shared_sd.add_to_customfield_value("foo", "bar")
    captured = capsys.readouterr()
    assert captured.out == (
        'Got status code 404 in add_to_customfield_value\n'
        'Url: https://mock-server/rest/api/2/issue/Test_ticket\n'
        '{"error": "not found"}\n'
        '{"update": {"foo": [{"add": "bar"}]}}\n'
    )
    

@responses.activate
def test_add_to_customfield_value_2():
    """Test add_to_customfield_value
    when the response status code is 204"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    data = {
        "update": {
            "foo": [
                {
                    "add": "bar"
                }
            ]
        }
    }
    responses.add(
        responses.PUT,
        "%s/rest/api/2/issue/%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET
        ),
        json = data,
        status=204
    )
    shared_sd.add_to_customfield_value("foo", "bar")


@mock.patch(
    'shared.shared_sd.get_current_status',
    return_value="Needs approval",
    autospec=True
)
def test_deassign_ticket_if_appropriate_1(mi1):
    """Test deassign_ticket_if_appropriate
    when ticket status is 'Needs approval' """
    last_comment = {
        "author": {
            "emailAddress": "mock_user@mock.com"
        }
    }
    result = shared_sd.deassign_ticket_if_appropriate(last_comment)
    assert mi1.called is True
    assert result == None


@mock.patch(
    'shared.shared_sd.user_is_bot',
    return_value=True,
    autospec=True
)
@mock.patch(
    'shared.shared_sd.get_current_status',
    return_value="Pending",
    autospec=True
)
def test_deassign_ticket_if_appropriate_2(mi1, mi2):
    """Test deassign_ticket_if_appropriate
    when the latest comment is from
    IT Support Bot """
    shared.globals.CONFIGURATION = {
        "bot_name": "bot@mock.com"
    }
    last_comment = {
        "author": {
            "emailAddress": "bot@mock.com"
        }
    }
    result = shared_sd.deassign_ticket_if_appropriate(last_comment)
    assert mi1.called is True
    assert mi2.called is True
    assert result == None


@mock.patch(
    'shared.shared_sd.assign_issue_to',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.user_is_bot',
    side_effect=[None, True],
    autospec=True
)
@mock.patch(
    'shared.shared_sd.get_current_status',
    return_value="Pending",
    autospec=True
)
def test_deassign_ticket_if_appropriate_3(mi1, mi2, mi3):
    """Test deassign_ticket_if_appropriate
    when assignee is IT Suppot Bot AND
    latest comment is from IT Suppot Bot
    AND transition_to is None """
    shared.globals.CONFIGURATION = {
        "bot_name": "bot@mock.com"
    }
    shared.globals.TICKET_DATA = {
        "fields": {
            "assignee": {
                "emailAddress": "bot@mock.com"
            }
        }
    }

    last_comment = {
        "author": {
            "emailAddress": "bot@mock.com"
        }
    }

    shared_sd.deassign_ticket_if_appropriate(last_comment)
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True


@mock.patch(
    'shared.shared_sd.transition_request_to',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.assign_issue_to',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.user_is_bot',
    side_effect=[None, True],
    autospec=True
)
@mock.patch(
    'shared.shared_sd.get_current_status',
    return_value="Pending",
    autospec=True
)
def test_deassign_ticket_if_appropriate_4(mi1, mi2, mi3, mi4):
    """Test deassign_ticket_if_appropriate
    when assignee is IT Suppot Bot AND
    latest comment is not from IT Suppot Bot
    """
    shared.globals.CONFIGURATION = {
        "bot_name": "bot@mock.com"
    }
    shared.globals.TICKET_DATA = {
        "fields": {
            "assignee": {
                "emailAddress": "bot@mock.com"
            }
        }
    }

    last_comment = {
        "author": {
            "emailAddress": "mock1_user@mock.com"
        }
    }

    shared_sd.deassign_ticket_if_appropriate(last_comment, "foo")
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert mi4.called is True


@responses.activate
def test_set_summary_1():
    """Test set_summary"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    shared.globals.TICKET_DATA = {
        "fields": {
            "summary": "test"
        }
    }
    responses.add(
        responses.PUT,
        "%s/rest/api/2/issue/%s" % (
            shared.globals.ROOT_URL, shared.globals.TICKET),
        json={
            "update": {
                "summary": [
                    {
                        "set": "foo"
                    }
                ]
            }
        },
        status=200,
    )

    shared_sd.set_summary("foo")
    assert shared.globals.TICKET_DATA["fields"]["summary"] == "foo"


@mock.patch(
    'shared.shared_sd.is_request_participant',
    return_value=True,
    autospec=True
)
def test_add_request_participant_1(mi1):
    """Test add_request_participant
    when specified email address is
    a request participant on the current issue"""
    result = shared_sd.add_request_participant("mock@mock.com")
    assert mi1.called is True
    assert result == None


@mock.patch(
    'shared.shared_sd.is_request_participant',
    return_value=False,
    autospec=True,
)
@responses.activate
def test_add_request_participant_2(mi1):
    """Test add_request_participant when
    specified email address is not a request participant
    on the current issue AND the response status code is 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    update = {'usernames': ["mock@mock.com"]}
    responses.add(
        responses.POST,
        "%s/rest/servicedeskapi/request/%s/participant" % (
            shared.globals.ROOT_URL, shared.globals.TICKET),
        json = update,
        status = 200,
    )

    shared_sd.add_request_participant("mock@mock.com")
    assert mi1.called is True


@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True,
)
@mock.patch(
    'shared.shared_sd.is_request_participant',
    return_value=False,
    autospec=True,
)
@responses.activate
def test_add_request_participant_3(mi1, mi2):
    """Test add_request_participant when
    specified email address is not a request participant
    on the current issue AND the response status code is non 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    update = {'usernames': ["mock@mock.com"]}
    responses.add(
        responses.POST,
        "%s/rest/servicedeskapi/request/%s/participant" % (
            shared.globals.ROOT_URL, shared.globals.TICKET),
        json = update,
        status = 400,
    )

    shared_sd.add_request_participant("mock@mock.com")
    assert mi1.called is True
    assert mi2.called is True


@responses.activate
def test_is_request_participant_1():
    """Test is_request_participant when response code is non 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    start = 0
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            start
        ),
        json={},
        status=400
    )
    result = shared_sd.is_request_participant("mock@mock.com")
    assert result == False


@responses.activate
def test_is_request_participant_2():
    """Test is_request_participant when response code is 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    start = 0
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            start
        ),
        json={
            "values": [
                {
                    "emailAddress": "mock@mock.com"
                }
            ],
        },
        status=200
    )
    result = shared_sd.is_request_participant("mock@mock.com")
    assert result == True


@responses.activate
def test_is_request_participant_3():
    """Test is_request_participant when response code is 200
    and when isLastPage is True"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    start = 0
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            start
        ),
        json={
            "values": [
                {
                    "emailAddress": "mock@mock.com"
                }
            ],
            "isLastPage": True
        },
        status=200
    )
    result = shared_sd.is_request_participant("mock1@mock.com")
    assert result == False


@responses.activate
def test_is_request_participant_4():
    """Test is_request_participant when response code is 200
    and when isLastPage is False"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    start = 0
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            start
        ),
        json={
            "values": [
                {
                    "emailAddress": "mock@mock.com"
                }
            ],
            "isLastPage": False,
            "size": 1
        },
        status=200
    )

    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            1
        ),
        json={
            "values": [
                {
                    "emailAddress": "mock@mock.com"
                }
            ],
            "isLastPage": True,
        },
        status=200
    )
    result = shared_sd.is_request_participant("mock1@mock.com")
    assert result == False


@responses.activate
def test_get_request_participants_1():
    """Test get_request_participants when response code is non 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    start = 0
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            start
        ),
        json={},
        status=400
    )
    result = shared_sd.get_request_participants()
    assert result == []


@responses.activate
def test_get_request_participants_2():
    """Test get_request_participants when response code is 200
    and isLastPage is True"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    start = 0
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            start
        ),
        json={
            "values": [
                {
                    "emailAddress": "mock@mock.com"
                }
            ],
            "isLastPage": True
        },
        status=200
    )
    result = shared_sd.get_request_participants()
    assert result == ['mock@mock.com']


@responses.activate
def test_get_request_participants_3():
    """Test get_request_participants when response code is 200
    and isLastPage is False"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "Test_ticket"
    start = 0
    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            start
        ),
        json={
            "values": [
                {
                    "emailAddress": "mock@mock.com"
                }
            ],
            "isLastPage": False,
            "size": 1
        },
        status=200
    )

    responses.add(
        responses.GET,
        "%s/rest/servicedeskapi/request/%s/participant?start=%s" % (
            shared.globals.ROOT_URL,
            shared.globals.TICKET,
            1
        ),
        json={
            "values": [
                {
                    "emailAddress": "mock1@mock.com"
                }
            ],
            "isLastPage": True,
        },
        status=200
    )

    result = shared_sd.get_request_participants()
    assert result == ['mock@mock.com', 'mock1@mock.com']


@responses.activate
def test_assign_issue_to_account_id_1():
    """Test assign_issue_to_account_id
    when the response status code is non 200"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.PROJECT = "mock_project"
    data = {"error": "not found"}
    responses.add(
        responses.GET,
        "%s/rest/api/2/user/assignable/multiProjectSearch"
        "?query=%s&projectKeys=%s" % (shared.globals.ROOT_URL,
         "mock_user", shared.globals.PROJECT
        ),
        json=data,
        status=404,
        content_type="application/json"
    )
    result = shared_sd.assign_issue_to_account_id("mock_user")
    assert result.json() == {'error': 'not found'}


@responses.activate
def test_assign_issue_to_account_id_2():
    """Test assign_issue_to_account_id
    when the response status code is 200
    AND result.json() is an empty list"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.PROJECT = "mock_project"
    responses.add(
        responses.GET,
        "%s/rest/api/2/user/assignable/multiProjectSearch"
        "?query=%s&projectKeys=%s" % (shared.globals.ROOT_URL,
         "mock_user", shared.globals.PROJECT
        ),
        json=[],
        status=200,
    )
    result = shared_sd.assign_issue_to_account_id("mock_user")
    assert result.json() == []


@mock.patch(
    'shared.shared_sd.service_desk_request_put',
    autospec=True
)
@responses.activate
def test_assign_issue_to_account_id_3(mi1):
    """Test assign_issue_to_account_id
    when the response status code is 200
    AND result.json() is a non-empty list"""
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.PROJECT = "mock_project"
    responses.add(
        responses.GET,
        "%s/rest/api/2/user/assignable/multiProjectSearch"
        "?query=%s&projectKeys=%s" % (shared.globals.ROOT_URL,
         "mock_user", shared.globals.PROJECT
        ),
        json=[
            {
                "accountId": "anonymous"
            }
        ],
        status=200,
    )
    shared_sd.assign_issue_to_account_id("mock_user")
    assert mi1.called is True


@mock.patch(
    'shared.shared_sd.shared_ldap.flatten_list',
    return_value=["john.doe@mock.com", "tom.doe@mock.com"],
    autospec=True
)
@responses.activate
def test_assign_approvers_1(mi1):
    """Test assign_approvers when
    add_to_request_participants is False
    AND when response code is 204"""
    approver_list = ["john.doe@mock.com", "tom.doe@mock.com"]
    shared.globals.TICKET = "Test_ticket"
    shared.globals.TICKET_DATA = {
        "self": "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field"
    }
    responses.add(
        responses.PUT,
        "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field",
        json={
            "fields":{
                "test_custom_field": [
                    {
                        "name": "john.doe@mock.com"
                    },
                    {
                        "name": "tom.doe@mock.com"
                    }
                ]
            }
        },
        status=204
    )
    shared_sd.assign_approvers(approver_list, "test_custom_field", False)
    assert mi1.called is True


@mock.patch(
    'shared.shared_sd.post_comment',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.shared_ldap.flatten_list',
    return_value=["john.doe@mock.com", "tom.doe@mock.com"],
    autospec=True
)
@responses.activate
def test_assign_approvers_2(mi1, mi2):
    """Test assign_approvers when
    add_to_request_participants is False
    AND when response code is non 204"""
    approver_list = ["john.doe@mock.com", "tom.doe@mock.com"]
    shared.globals.TICKET = "Test_ticket"
    shared.globals.TICKET_DATA = {
        "self": "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field"
    }
    responses.add(
        responses.PUT,
        "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field",
        json={
            "fields":{
                "test_custom_field": [
                    {
                        "name": "john.doe@mock.com"
                    },
                    {
                        "name": "tom.doe@mock.com"
                    }
                ]
            }
        },
        status=400
    )
    shared_sd.assign_approvers(approver_list, "test_custom_field", False)
    assert mi1.called is True
    assert mi2.called is True


@mock.patch(
    'shared.shared_sd.add_request_participant',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.shared_ldap.flatten_list',
    return_value=["john.doe@mock.com", "tom.doe@mock.com"],
    autospec=True
)
@responses.activate
def test_assign_approvers_3(mi1, mi2):
    """Test assign_approvers when
    add_to_request_participants is True"""
    approver_list = ["approver1@mock.com", "approver2@mock.com"]
    shared.globals.TICKET = "Test_ticket"
    shared.globals.TICKET_DATA = {
        "self": "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field"
    }
    responses.add(
        responses.PUT,
        "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field",
        json={
            "fields":{
                "test_custom_field": [
                    {
                        "name": "john.doe@mock.com"
                    },
                    {
                        "name": "tom.doe@mock.com"
                    }
                ]
            }
        },
        status=204
    )
    shared_sd.assign_approvers(approver_list, "test_custom_field")
    assert mi1.called is True
    assert mi2.called is True


class MockMail:
    """Mock Mail Object"""
    def __init__(self):
        self.value = "tom.doe@mock.com"

class MockLDAPObject:
    """Mock LDAP Object"""
    def __init__(self):
        self.mail = MockMail()


@mock.patch(
    'shared.shared_sd.shared_ldap.get_object',
    return_value=MockLDAPObject(),
    autospec=True
)
@mock.patch(
    'shared.shared_sd.add_request_participant',
    autospec=True
)
@mock.patch(
    'shared.shared_sd.shared_ldap.flatten_list',
    return_value=["john.doe@mock.com", "tom.doe"],
    autospec=True
)
@responses.activate
def test_assign_approvers_4(mi1, mi2, mi3):
    """Test assign_approvers when
    add_to_request_participants is True
    AND when the approvers is a name instead of
    email address """
    approver_list = ["john.doe@mock.com", "tom.doe"]
    shared.globals.TICKET = "Test_ticket"
    shared.globals.TICKET_DATA = {
        "self": "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field"
    }
    responses.add(
        responses.PUT,
        "https://mock-server/rest/servicedeskapi/request/Test_ticket/test_custom_field",
        json={
            "fields":{
                "test_custom_field": [
                    {
                        "name": "john.doe@mock.com"
                    },
                    {
                        "name": "tom.doe@mock.com"
                    }
                ]
            }
        },
        status=204
    )
    shared_sd.assign_approvers(approver_list, "test_custom_field")
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
