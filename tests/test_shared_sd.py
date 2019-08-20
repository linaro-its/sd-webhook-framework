#!/usr/bin/python3
""" Test the shared Service Desk library. """

import mock
import pytest
import responses

from requests.auth import HTTPBasicAuth

import shared.shared_sd as shared_sd
import shared.config as config


def test_initialise_1():
    """ Test the initialisation. """
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.initialise({})


def test_initialise_2():
    """ Test initialisation with a malformed issue. """
    data = {
        "issue": {}
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.initialise(data)


def test_initialise_3():
    """ Test initialisation with a different malformed issue. """
    data = {
        "issue": {
            "self": "self"
        }
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.initialise(data)


def test_initialise_4():
    """ Test initialisation with a different malformed issue. """
    data = {
        "issue": {
            "self": "self",
            "key": "key"
        }
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.initialise(data)


def test_initialise_5():
    """ Test initialisation with a different malformed issue. """
    data = {
        "issue": {
            "self": "self",
            "key": "key",
            "fields": {}
        }
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.initialise(data)


def test_initialise_6():
    """ Test initialisation with a different malformed issue. """
    data = {
        "issue": {
            "self": "self",
            "key": "key",
            "fields": {
                "project": {}
            }
        }
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.initialise(data)


def test_initialise_valid_data():
    """ Test initialisation with valid issue data. """
    data = {
        "issue": {
            "self": "https://sd-server/rest/api/2/issue/21702",
            "key": "ITS-6895",
            "fields": {
                "project": {
                    "key": "ITS"
                }
            }
        }
    }
    shared_sd.initialise(data)
    assert shared_sd.ROOT_URL == "https://sd-server"
    assert shared_sd.TICKET == "ITS-6895"
    assert shared_sd.PROJECT == "ITS"


def test_simple_credentials():
    """ Test that credential handling works. """
    config.CONFIGURATION = {
        "bot_name": "name",
        "bot_password": "password"
    }
    name, password = shared_sd.sd_auth_credentials()
    assert name == "name"
    assert password == "password"


@mock.patch(
    'shared.shared_sd.vault_auth.get_secret',
    return_value={
        "data": {
            "pw": "vault_password"
        }
    },
    autospec=True
)
def test_vault_credentials(mock_get_secret):
    """ Test credentials against the vault. """
    config.CONFIGURATION = {
        "bot_name": "name",
        "vault_iam_role": "role",
        "vault_server_url": "url"
    }
    name, password = shared_sd.sd_auth_credentials()
    # Make sure that our mock version of get_secret got called
    assert mock_get_secret.called is True
    assert name == "name"
    assert password == "vault_password"


def dummy_config_initialise():
    """ Set up some dummy config. """
    config.CONFIGURATION = {}


@mock.patch(
    'shared.shared_sd.config.initialise',
    side_effect=dummy_config_initialise,
    autospec=True
)
def test_missing_credentials_2(mock_config_initialise):
    """ Test behaviour when credentials are missing. """
    config.CONFIGURATION = None
    with pytest.raises(shared_sd.MissingCredentials):
        shared_sd.sd_auth_credentials()
    assert mock_config_initialise.called is True


def test_missing_credentials_3():
    """ Test behaviour when credentials are missing. """
    config.CONFIGURATION = {
        "bot_name": "name"
    }
    with pytest.raises(shared_sd.MissingCredentials):
        shared_sd.sd_auth_credentials()


def test_missing_credentials_4():
    """ Test behaviour when credentials are missing. """
    config.CONFIGURATION = {
        "bot_name": "name",
        "vault_iam_role": "role"
    }
    with pytest.raises(shared_sd.MissingCredentials):
        shared_sd.sd_auth_credentials()


def test_missing_credentials_5():
    """ Test behaviour when credentials are missing. """
    config.CONFIGURATION = {
        "bot_name": "name",
        "vault_server_url": "url"
    }
    with pytest.raises(shared_sd.MissingCredentials):
        shared_sd.sd_auth_credentials()


def test_overlapping_credentials_1():
    """ Test behaviour when multiple types of credentials are present. """
    config.CONFIGURATION = {
        "bot_name": "name",
        "bot_password": "password",
        "vault_iam_role": "role"
    }
    with pytest.raises(shared_sd.OverlappingCredentials):
        shared_sd.sd_auth_credentials()


def test_overlapping_credentials_2():
    """ Test behaviour when multiple types of credentials are present. """
    config.CONFIGURATION = {
        "bot_name": "name",
        "bot_password": "password",
        "vault_server_url": "url"
    }
    with pytest.raises(shared_sd.OverlappingCredentials):
        shared_sd.sd_auth_credentials()


@mock.patch(
    'shared.shared_sd.sd_auth_credentials',
    return_value=["name", "password"],
    autospec=True
)
def test_get_sd_auth(mock_sd_auth_credentials):
    """ Check that get_sd_auth returns a valid HTTPBasicAuth. """
    shared_sd.SD_AUTH = None
    result = shared_sd.get_sd_auth()
    compare = HTTPBasicAuth("name", "password")
    assert result == compare
    assert mock_sd_auth_credentials.called is True


@responses.activate
def test_get_servicedesk_id_1():
    """ Check the code correctly determines a project's ID. """
    shared_sd.ROOT_URL = "https://mock-server"
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
    shared_sd.ROOT_URL = "https://mock-server"
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
    shared_sd.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/servicedeskapi/servicedesk",
        json={},
        status=404
    )
    result = shared_sd.get_servicedesk_id("ITS")
    assert result == -1


@responses.activate
def test_sd_request_get():
    """ Test calls to service_desk_request_get. """
    shared_sd.SD_AUTH = HTTPBasicAuth("name", "password")
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
    shared_sd.SD_AUTH = HTTPBasicAuth("name", "password")
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
    shared_sd.SD_AUTH = HTTPBasicAuth("name", "password")
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
    shared_sd.SD_AUTH = HTTPBasicAuth("name", "password")
    shared_sd.ROOT_URL = "https://mock-server"
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
    shared_sd.SD_AUTH = HTTPBasicAuth("name", "password")
    shared_sd.ROOT_URL = "https://mock-server"
    shared_sd.TICKET = "ITS-1"
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


@responses.activate
def test_get_cf_id_from_plugin():
    """ Test using the plugin to get a custom field ID. """
    shared_sd.SD_AUTH = HTTPBasicAuth("name", "password")
    shared_sd.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/jiracustomfieldeditorplugin/1/admin/"
        "customfields",
        json=[
            {
                "fieldId": 10100,
                "fieldName": "Customer Request Type",
                "fieldType": "com.atlassian.servicedesk:vp-origin",
                "fieldDescription": (
                    "Holds information about which Service Desk was used "
                    "to create a ticket. This custom field is created "
                    "programmatically and must not be modified.")
            }
        ],
        status=200
    )
    result = shared_sd.get_customfield_id_from_plugin("foo")
    assert result is None
    result = shared_sd.get_customfield_id_from_plugin("Customer Request Type")
    assert result == 10100


@responses.activate
def test_denied_cf_id_from_plugin():
    """ Test handling of access denied from the plugin. """
    shared_sd.SD_AUTH = HTTPBasicAuth("name", "password")
    shared_sd.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/jiracustomfieldeditorplugin/1/admin/"
        "customfields",
        json={
            "message": "Access denied"
        },
        status=403
    )
    result = shared_sd.get_customfield_id_from_plugin("foo")
    assert result is None


@mock.patch(
    'shared.shared_sd.get_customfield_id_from_plugin',
    return_value=None
)
def test_ticket_request_type_1(mock_get_cf_id):
    """ Test handling of failure to determine custom field. """
    with pytest.raises(shared_sd.CustomFieldLookupFailure):
        shared_sd.ticket_request_type(None)
    assert mock_get_cf_id.called is True


@mock.patch(
    'shared.shared_sd.get_customfield_id_from_plugin',
    return_value=10100
)
def test_ticket_request_type_2(mock_get_cf_id):
    """ Test handling of malformed issue. """
    data = {
        "issue": {
            "fields": {}
        }
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.ticket_request_type(data)
    assert mock_get_cf_id.called is True


@mock.patch(
    'shared.shared_sd.get_customfield_id_from_plugin',
    return_value=10100
)
def test_ticket_request_type_3(mock_get_cf_id):
    """ Test handling of custom fields in request type. """
    data = {
        "issue": {
            "fields": {
                "customfield_10100": {
                    "requestType": {
                        "id": "206",
                    }
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
    match, t_from, t_to = shared_sd.trigger_is_assignment(data)
    assert match is True
    assert t_from == "from"
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
                    "to": "to"
                }
            ]
        }
    }
    match, t_from, t_to = shared_sd.trigger_is_transition(data)
    assert match is True
    assert t_from == "from"
    assert t_to == "to"


def test_look_for_trigger():
    """ Test the code that determines the cause of the trigger. """
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic"
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.look_for_trigger(None, data)
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic",
        "changelog": {}
    }
    with pytest.raises(shared_sd.MalformedIssueError):
        shared_sd.look_for_trigger(None, data)
    data = {
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic",
        "changelog": {
            "items": [
                {
                    "field": "test",
                    "fieldtype": "jira",
                    "from": "from",
                    "to": "to"
                }
            ]
        }
    }
    match, t_from, t_to = shared_sd.look_for_trigger("test", data)
    assert match is True
    assert t_from == "from"
    assert t_to == "to"
    match, t_from, t_to = shared_sd.look_for_trigger("fail", data)
    assert match is False
    assert t_from is None
    assert t_to is None


def test_automation_triggered_comment():
    """ Test the code that determines if the automation wrote the last comment. """
    result = shared_sd.automation_triggered_comment({})
    assert result is False

    data = {
        "comment": {
            "author": {
                "name": config.CONFIGURATION["bot_name"]
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
                "name": config.CONFIGURATION["bot_name"]
            }
        }
    }
    shared_sd.save_ticket_data_as_attachment(data)
    assert mock_print.called is True
    assert mock_save_text_as_attachment.called is False
