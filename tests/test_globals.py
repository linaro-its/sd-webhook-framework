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
    shared.globals.initialise_ticket_data({})
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


def test_validate_cf_config():
    """ Test validate_cf_config """
    shared.globals.CONFIGURATION = {
        "cf_use_plugin_api": True
    }
    with pytest.raises(shared.globals.MissingCFConfig):
        shared.globals.validate_cf_config()
    shared.globals.CONFIGURATION = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False
    }
    # This should pass the validation because we now default the
    # cachefile name if it is missing from the config.
    shared.globals.validate_cf_config()


def test_validate_user_password_config():
    """ Test various user/password combos. """
    shared.globals.CONFIGURATION = {}
    with pytest.raises(shared.globals.MissingCredentials):
        shared.globals.validate_user_password_config(
            "bot_name", "bot_password", "vault_bot_name")
    # If we're missing the password tag, we must have the three
    # Vault tags.
    shared.globals.CONFIGURATION = {
        "bot_name": "Fred",
        "vault_bot_name": "Fred"
    }
    with pytest.raises(shared.globals.MissingCredentials):
        shared.globals.validate_user_password_config(
            "bot_name", "bot_password", "vault_bot_name")
    shared.globals.CONFIGURATION = {
        "bot_name": "Fred",
        "vault_bot_name": "Fred",
        "vault_iam_role": "foo"
    }
    with pytest.raises(shared.globals.MissingCredentials):
        shared.globals.validate_user_password_config(
            "bot_name", "bot_password", "vault_bot_name")
    shared.globals.CONFIGURATION = {
        "bot_name": "Fred",
        "vault_bot_name": "Fred",
        "vault_server_url": "foo"
    }
    with pytest.raises(shared.globals.MissingCredentials):
        shared.globals.validate_user_password_config(
            "bot_name", "bot_password", "vault_bot_name")
    # Test for everything present and correct.
    shared.globals.CONFIGURATION = {
        "bot_name": "Fred",
        "vault_bot_name": "Fred",
        "vault_iam_role": "foo",
        "vault_server_url": "foo"
    }
    shared.globals.validate_user_password_config(
        "bot_name", "bot_password", "vault_bot_name")
    # Now test for overlapping errors.
    shared.globals.CONFIGURATION = {
        "bot_name": "Fred",
        "bot_password": "Fred",
        "vault_bot_name": "Fred"
    }
    with pytest.raises(shared.globals.OverlappingCredentials):
        shared.globals.validate_user_password_config(
            "bot_name", "bot_password", "vault_bot_name")
    # But not if the other Vault entries are there.
    shared.globals.CONFIGURATION = {
        "bot_name": "Fred",
        "bot_password": "Fred",
        "vault_iam_role": "foo",
        "vault_server_url": "foo"
    }
    shared.globals.validate_user_password_config(
        "bot_name", "bot_password", "vault_bot_name")


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
    # Test a valid config as we've checked everything else already.
    data = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "bot_name": "Fred",
        "vault_bot_name": "Fred",
        "vault_iam_role": "foo",
        "vault_server_url": "foo",
        "ldap_enabled": "True",
        "ldap_server": "wibble",
        "ldap_user": "Bob",
        "ldap_password": "foo",
        "mail_host": "localhost",
        "mail_user": "Bob",
        "mail_password": "foo"
    }
    with patch("builtins.open", mock_open(
            read_data=json.dumps(data)
        )):
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


@mock.patch(
    'shared.globals.vault_auth.get_secret',
    return_value={
        "data": {
            "pw": "vault_password"
        }
    },
    autospec=True
)
def test_ldap_credentials(mi1):
    """ Test get_ldap_credentials. """
    shared.globals.CONFIGURATION = {
        "ldap_user": "user",
        "ldap_password": "password"
    }
    user, password = shared.globals.get_ldap_credentials()
    assert user == "user"
    assert password == "password"
    shared.globals.CONFIGURATION = {
        "ldap_user": "ldap_user",
        "vault_ldap_name": "vault_ldap_name",
        "vault_iam_role": "role",
        "vault_server_url": "url"
    }
    user, password = shared.globals.get_ldap_credentials()
    assert user == "ldap_user"
    assert password == "vault_password"
    assert mi1.called is True


def test_config():
    """ Test config function. """
    shared.globals.CONFIGURATION = {}
    assert shared.globals.config("foo") is None
    shared.globals.CONFIGURATION = {
        "bar": "wibble"
    }
    assert shared.globals.config("foo") is None
    shared.globals.CONFIGURATION = {
        "foo": "wibble"
    }
    assert shared.globals.config("foo") == "wibble"



@mock.patch(
    'shared.globals.vault_auth.get_secret',
    return_value={
        "data": {
            "pw": "vault_password"
        }
    },
    autospec=True
)
def test_get_email_credentials(mi1):
    """ Test get_email_credentials. """
    shared.globals.CONFIGURATION = {}
    user, password = shared.globals.get_email_credentials()
    assert user is None
    assert password is None

    shared.globals.CONFIGURATION = {
        "mail_user": "mock_user",
        "mail_password": "mock_password"
    }
    user, password = shared.globals.get_email_credentials()
    assert user == "mock_user"
    assert password == "mock_password"

    shared.globals.CONFIGURATION = {
        "mail_user": "mock_user",
        "vault_mail_name": "mock_vault",
        "vault_iam_role": "foo",
        "vault_server_url": "foo"
    }
    user, password = shared.globals.get_email_credentials()
    assert user == "mock_user"
    assert password == "vault_password"
    assert mi1.called is True
