#!/usr/bin/python3

import os
import sys

import mock
from mock import mock_open, patch
import pytest
import responses

from requests.auth import HTTPBasicAuth
import json

# Tell Python where to find the webhook automation code.
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))) + "/sd_webhook_automation")
import config  # noqa
import shared_sd  # noqa
import custom_fields  # noqa


def dummy_config_initialise():
    config.configuration = {}


@mock.patch(
    'custom_fields.config.initialise',
    side_effect=dummy_config_initialise,
    autospec=True
)
def test_get_1(mock_config_initialise):
    config.configuration = None
    with pytest.raises(custom_fields.MissingCFConfig):
        custom_fields.get("foo")
    assert mock_config_initialise.called is True


def test_get_2():
    config.configuration = {
        "cf_use_plugin_api": False
    }
    with pytest.raises(custom_fields.MissingCFConfig):
        custom_fields.get("foo")


@mock.patch(
    'custom_fields.os.path.isfile',
    return_value=False,
    autospec=True
)
def test_get_3(mock_os_path_isfile):
    config.configuration = {
        "cf_use_plugin_api": False,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.cf_cache = None
    custom_fields.get("foo")
    assert mock_os_path_isfile.called is True
    assert custom_fields.cf_cache == {}


mock_cf_cache = {
    "Approvers": 10800
}


@mock.patch(
    'custom_fields.os.path.isfile',
    return_value=True,
    autospec=True
)
def test_get_4(mock_os_path_isfile):
    config.configuration = {
        "cf_use_plugin_api": False,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.cf_cache = None
    with patch(
                'builtins.open',
                mock_open(
                    read_data=json.dumps(mock_cf_cache)
                ),
                create=True
            ) as m:
        result = custom_fields.get("Approvers")
        assert mock_os_path_isfile.called is True
        m.assert_called_once_with("/tmp/cf_cachefile", "r")
        assert result == 10800


@mock.patch(
    'custom_fields.os.path.isfile',
    return_value=True,
    autospec=True
)
@responses.activate
def test_get_5(mock_os_path_isfile):
    config.configuration = {
        "cf_use_plugin_api": True,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.cf_cache = None
    shared_sd.sd_auth = HTTPBasicAuth("name", "password")
    shared_sd.root_url = "https://mock-server"
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
    with patch(
                'builtins.open',
                mock_open(
                    read_data=json.dumps(mock_cf_cache)
                ),
                create=True
            ) as m:
        with patch('custom_fields.json.dump') as m_json:
            result = custom_fields.get("Customer Request Type")
            assert mock_os_path_isfile.called is True
            m.assert_any_call("/tmp/cf_cachefile", "r")
            m.assert_any_call("/tmp/cf_cachefile", "w")
            # Check that the right data was written out
            # https://stackoverflow.com/questions/33650568/
            #     mock-open-function-used-in-a-class-method
            m_json.assert_called_with(
                custom_fields.cf_cache,
                m.return_value.__enter__.return_value
            )
            assert result == 10100
