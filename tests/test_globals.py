#!/usr/bin/python3
""" Test shared/globals functionality """

import json
from unittest.mock import patch, mock_open
import mock
import pytest
from requests.auth import HTTPBasicAuth
import shared.globals


def test_initialise_data():
    """ Test initialise_ticket_data. """
    shared.globals.TICKET_DATA = None
    data = json.dumps({})
    shared.globals.initialise_ticket_data(data)
    assert shared.globals.TICKET_DATA == {}

def test_initialise_shared_sd():
    """ Test initialise_shared_sd. """
    shared.globals.TICKET_DATA = {}
    with pytest.raises(shared.globals.MalformedIssueError):
        shared.globals.initialise_shared_sd()
    shared.globals.TICKET_DATA = {
        "issue": "foo"
    }
    with pytest.raises(shared.globals.MalformedIssueError):
        shared.globals.initialise_shared_sd()
    shared.globals.TICKET_DATA = {
        "issue": {
            "self": "foo"
        }
    }
    with pytest.raises(shared.globals.MalformedIssueError):
        shared.globals.initialise_shared_sd()
    shared.globals.TICKET_DATA = {
        "issue": {
            "self": "self",
            "key": "key"
        }
    }
    with pytest.raises(shared.globals.MalformedIssueError):
        shared.globals.initialise_shared_sd()
    shared.globals.TICKET_DATA = {
        "issue": {
            "self": "self",
            "key": "key",
            "fields": {}
        }
    }
    with pytest.raises(shared.globals.MalformedIssueError):
        shared.globals.initialise_shared_sd()
    shared.globals.TICKET_DATA = {
        "issue": {
            "self": "self",
            "key": "key",
            "fields": {
                "project": {}
            }
        }
    }
    with pytest.raises(shared.globals.MalformedIssueError):
        shared.globals.initialise_shared_sd()
    shared.globals.TICKET_DATA = {
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
    shared.globals.initialise_shared_sd()
    assert shared.globals.ROOT_URL == "https://sd-server"
    assert shared.globals.TICKET == "ITS-6895"
    assert shared.globals.PROJECT == "ITS"


def test_initialise_config():
    """ Test initialise_config """
    # Check that we get a JSON error on an empty file.
    with patch("builtins.open", mock_open(
            read_data=''
    )):
        with pytest.raises(json.decoder.JSONDecodeError):
            shared.globals.initialise_config()
    # Check that we get the various missing config errors.
    with patch("builtins.open", mock_open(
            read_data='{}\n'
    )):
        with pytest.raises(shared.globals.MissingCFConfig):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True
    }
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.MissingCFConfig):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False
    }
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.MissingCFConfig):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cachefile"
    }
    # All of the CF parts are there so now we're testing the bot parts.
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.MissingCredentials):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cachefile",
        "bot_name": "Fred"
    }
    # We don't have bot_password there so we should get the missing
    # vault errors now.
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.MissingCredentials):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cachefile",
        "bot_name": "Fred",
        "vault_bot_name": "Fred"
    }
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.MissingCredentials):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cachefile",
        "bot_name": "Fred",
        "vault_bot_name": "Fred",
        "vault_iam_role": "iam"
    }
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.MissingCredentials):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cachefile",
        "bot_name": "Fred",
        "bot_password": "password",
        "vault_iam_role": "iam"
    }
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.OverlappingCredentials):
            shared.globals.initialise_config()
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cachefile",
        "bot_name": "Fred",
        "bot_password": "password",
        "vault_server_url": "url"
    }
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
    )):
        with pytest.raises(shared.globals.OverlappingCredentials):
            shared.globals.initialise_config()


def test_simple_credentials():
    """ Test that credential handling works. """
    shared.globals.CONFIGURATION = {
        "bot_name": "name",
        "bot_password": "password"
    }
    name, password = shared.globals.get_sd_credentials()
    assert name == "name"
    assert password == "password"


@mock.patch(
    'shared.globals.vault_auth.get_secret',
    return_value={
        "data": {
            "pw": "vault_password"
        }
    },
    autospec=True
)
def test_vault_credentials(mock_get_secret):
    """ Test credentials against the vault. """
    shared.globals.CONFIGURATION = {
        "bot_name": "name",
        "vault_bot_name": "bot_name",
        "vault_iam_role": "role",
        "vault_server_url": "url"
    }
    name, password = shared.globals.get_sd_credentials()
    # Make sure that our mock version of get_secret got called
    assert mock_get_secret.called is True
    assert name == "name"
    assert password == "vault_password"


@mock.patch(
    'shared.globals.get_sd_credentials',
    return_value=["name", "password"],
    autospec=True
)
def test_get_sd_auth(mock_sd_auth_credentials):
    """ Check that get_sd_auth returns a valid HTTPBasicAuth. """
    shared.globals.SD_AUTH = None
    shared.globals.initialise_sd_auth()
    compare = HTTPBasicAuth("name", "password")
    assert shared.globals.SD_AUTH == compare
    assert mock_sd_auth_credentials.called is True
