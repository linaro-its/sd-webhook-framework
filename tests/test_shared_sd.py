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


def test_look_for_trigger():
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


def test_automation_triggered_comment():
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
                "name": shared.globals.CONFIGURATION["bot_name"]
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
def test_assign_issue_to(mi1):
    """ Test assign_issue_to. """
    shared.globals.ROOT_URL = "https://mock-server"
    shared.globals.TICKET = "mock-ticket"
    shared.globals.CONFIGURATION = {
        "bot_name": "mock_bot"
    }
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
def test_get_current_status():
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
def test_get_latest_comment():
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
