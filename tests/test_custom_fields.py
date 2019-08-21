#!/usr/bin/python3
""" Test shared/custom_fields. """

import json
from requests.auth import HTTPBasicAuth

import mock
from mock import mock_open, patch
import responses

import shared.globals
import shared.custom_fields as custom_fields


def dummy_config_initialise():
    """ Provide some dummy config. """
    shared.globals.CONFIGURATION = {}


@responses.activate
def test_get_cf_id_from_plugin():
    """ Test using the plugin to get a custom field ID. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
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
    result = custom_fields.get_customfield_id_from_plugin("foo")
    assert result is None
    result = custom_fields.get_customfield_id_from_plugin("Customer Request Type")
    assert result == 10100


@responses.activate
def test_denied_cf_id_from_plugin():
    """ Test handling of access denied from the plugin. """
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
    responses.add(
        responses.GET,
        "https://mock-server/rest/jiracustomfieldeditorplugin/1/admin/"
        "customfields",
        json={
            "message": "Access denied"
        },
        status=403
    )
    result = custom_fields.get_customfield_id_from_plugin("foo")
    assert result is None


@mock.patch(
    'shared.custom_fields.os.path.isfile',
    return_value=False,
    autospec=True
)
def test_get_3(mock_os_path_isfile):
    """ Test behaviour with cache file config. """
    shared.globals.CONFIGURATION = {
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
    shared.globals.CONFIGURATION = {
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
    shared.globals.CONFIGURATION = {
        "cf_use_plugin_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.CF_CACHE = None
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server"
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
