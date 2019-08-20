#!/usr/bin/python3
""" Test sd_webhook_automation/custom_fields. """

import os
import sys
import json
from requests.auth import HTTPBasicAuth

import mock
from mock import mock_open, patch
import pytest
import responses

import shared.config as config
import shared.shared_sd as shared_sd
import shared.custom_fields as custom_fields


def dummy_config_initialise():
    """ Provide some dummy config. """
    config.CONFIGURATION = {}


@mock.patch(
    'shared.custom_fields.config.initialise',
    side_effect=dummy_config_initialise,
    autospec=True
)
def test_get_1(mock_config_initialise):
    """ Test getting a value from the config. """
    config.CONFIGURATION = None
    with pytest.raises(custom_fields.MissingCFConfig):
        custom_fields.get("foo")
    assert mock_config_initialise.called is True


def test_get_2():
    """ Test more config retrieval. """
    config.CONFIGURATION = {}
    with pytest.raises(custom_fields.MissingCFConfig):
        custom_fields.get("foo")
    config.CONFIGURATION = {
        "cf_use_plugin_api": False
    }
    with pytest.raises(custom_fields.MissingCFConfig):
        custom_fields.get("foo")
    config.CONFIGURATION = {
        "cf_use_plugin_api": False,
        "cf_use_cloud_api": False
    }
    with pytest.raises(custom_fields.MissingCFConfig):
        custom_fields.get("foo")


@mock.patch(
    'shared.custom_fields.os.path.isfile',
    return_value=False,
    autospec=True
)
def test_get_cloud_exception(mock_os_path_isfile):
    """ Test that we get an exception when trying to use the cloud service. """
    config.CONFIGURATION = {
        "cf_use_plugin_api": False,
        "cf_use_cloud_api": True,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    # Stop pylint complaining that we don't use the argument
    _ = mock_os_path_isfile
    with pytest.raises(NotImplementedError):
        custom_fields.get("foo")


@mock.patch(
    'shared.custom_fields.os.path.isfile',
    return_value=False,
    autospec=True
)
def test_get_3(mock_os_path_isfile):
    """ Test behaviour with cache file config. """
    config.CONFIGURATION = {
        "cf_use_plugin_api": False,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.CF_CACHE = None
    custom_fields.get("foo")
    assert mock_os_path_isfile.called is True
    assert custom_fields.CF_CACHE == {}


MOCK_CF_CACHE = {
    "Approvers": 10800
}


@mock.patch(
    'shared.custom_fields.os.path.isfile',
    return_value=True,
    autospec=True
)
def test_get_4(mock_os_path_isfile):
    """ Test retrieval from a cache file. """
    config.CONFIGURATION = {
        "cf_use_plugin_api": False,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.CF_CACHE = None
    with patch(
                'builtins.open',
                mock_open(
                    read_data=json.dumps(MOCK_CF_CACHE)
                ),
                create=True
        ) as mock_patch:
        result = custom_fields.get("Approvers")
        assert mock_os_path_isfile.called is True
        mock_patch.assert_called_once_with("/tmp/cf_cachefile", "r")
        assert result == 10800


@mock.patch(
    'shared.custom_fields.os.path.isfile',
    return_value=True,
    autospec=True
)
@responses.activate
def test_get_5(mock_os_path_isfile):
    """ Check that the cache file gets updated. """
    config.CONFIGURATION = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.CF_CACHE = None
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
    with patch(
                'builtins.open',
                mock_open(
                    read_data=json.dumps(MOCK_CF_CACHE)
                ),
                create=True
        ) as mock_patch:
        with patch('shared.custom_fields.json.dump') as m_json:
            result = custom_fields.get("Customer Request Type")
            assert mock_os_path_isfile.called is True
            mock_patch.assert_any_call("/tmp/cf_cachefile", "r")
            mock_patch.assert_any_call("/tmp/cf_cachefile", "w")
            # Check that the right data was written out
            # https://stackoverflow.com/questions/33650568/
            #     mock-open-function-used-in-a-class-method
            m_json.assert_called_with(
                custom_fields.CF_CACHE,
                mock_patch.return_value.__enter__.return_value
            )
            assert result == 10100
