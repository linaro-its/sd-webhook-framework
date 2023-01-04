#!/usr/bin/python3
""" Test shared/custom_fields. """

import json
from requests.auth import HTTPBasicAuth

import mock
from mock import mock_open, patch
import pytest
import responses
import requests
from responses import matchers

import shared.globals
import shared.custom_fields as custom_fields


@mock.patch(
    'shared.custom_fields.os.path.isfile',
    return_value=False,
    autospec=True
)
def test_get_3(mock_os_path_isfile):
    """ Test behaviour with cache file config. """
    shared.globals.CONFIGURATION = {
        # "cf_use_plugin_api": False,
        "cf_use_server_api": False,
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
        "cf_use_server_api": False,
        "cf_use_cloud_api": True,
        "cf_cachefile": "/tmp/cf_cachefile"
    }
    custom_fields.CF_CACHE = None
    shared.globals.SD_AUTH = HTTPBasicAuth("name", "password")
    shared.globals.ROOT_URL = "https://mock-server/"
    responses.add(
        responses.GET,
        "%s/rest/api/3/field" % (shared.globals.ROOT_URL),
        json=[
            {
                "id": 10100,
                "name": "Customer Request Type"
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


@responses.activate
def test_service_desk_request_get_1():
    """Testing for servicedesk get request"""
    responses.add(
        responses.GET,
        "https://mock-server/",
        json={
            "error": "not found"
        },
        status = 404
    )
    response = custom_fields.service_desk_request_get("https://mock-server")
    assert response.status_code == 404


@responses.activate
def test_service_desk_request_get_2():
    """ Check GET servicedesk request headers"""
    # https://github.com/getsentry/responses#request-headers-validation
    shared.globals.SD_AUTH = "fred"
    responses.get(
        url="https://mock-server/",
        body="hello world",
        match=[matchers.header_matcher({"Authorization": "Basic fred"})],
    )
    response = custom_fields.service_desk_request_get("https://mock-server/")
    assert response.status_code == 200


@responses.activate
def test_get_customfield_id_from_server_1():
    """ Test code to check custom field id """
    shared.globals.ROOT_URL = "https://mock-server/"
    start_at = 1
    responses.add(
        responses.GET,
        "%s/rest/api/2/customFields?startAt=%s" % (shared.globals.ROOT_URL, start_at),
        json={
            "values" : [
                {
                    "name" : "foo",
                    "id" : 10
                }
            ]
        },
        status = 200
    )
    result = custom_fields.get_customfield_id_from_server("foo")
    assert result == 10


@responses.activate
def test_get_customfield_id_from_server_2():
    """ Test code to check custom field id if doesn't exist """
    shared.globals.ROOT_URL = "https://mock-server/"
    start_at = 1
    responses.add(
        responses.GET,
        "%s/rest/api/2/customFields?startAt=%s" % (shared.globals.ROOT_URL, start_at),
        json={
            "values" : [
                {
                    "name" : "bar",
                    "id" : 10
                }
            ],
            "isLast" : "True"
        },
        status = 200
    )
    result = custom_fields.get_customfield_id_from_server("foo")
    assert result is None


@responses.activate
def test_get_customfield_id_from_cloud_1():
    """Test to get custom field id from cloud"""
    shared.globals.ROOT_URL = "https://mock-server/"
    responses.add(
        responses.GET,
        "%s/rest/api/3/field" % (shared.globals.ROOT_URL),
        json=[
            {
                "name" : "foo",
                "id" : 10
            }
        ],
        status = 200
    )
    result = custom_fields.get_customfield_id_from_cloud("foo")
    assert result == 10


@responses.activate
def test_get_customfield_id_from_cloud_2():
    """Test to check the response if custom field id doesn't exist in cloud"""
    shared.globals.ROOT_URL = "https://mock-server/"
    responses.add(
        responses.GET,
        "%s/rest/api/3/field" % (shared.globals.ROOT_URL),
        json=[
            {
                "name" : "foo",
                "id" : 10
            }
        ],
        status = 200
    )
    result = custom_fields.get_customfield_id_from_cloud("bar")
    assert result is None


@responses.activate
def test_get_customfield_id_from_cloud_3():
    """Check if the response code is 404"""
    shared.globals.ROOT_URL = "https://mock-server/"
    responses.add(
        responses.GET,
        "%s/rest/api/3/field" % (shared.globals.ROOT_URL),
        json={
            "error": "not found"
        },
        status = 404
    )
    response = custom_fields.get_customfield_id_from_cloud("foo")
    assert response is None


@responses.activate
def test_fetch_cf_value_1():
    """ Test to get cf id from cloud api"""
    custom_fields.CF_CACHE = {}
    shared.globals.CONFIGURATION = {
        "cf_use_server_api": False,
        "cf_use_cloud_api": True,
        "cf_cachefile": "nothing"
    }
    shared.globals.ROOT_URL = "https://mock-server/"
    responses.add(
        responses.GET,
        "%s/rest/api/3/field" % (shared.globals.ROOT_URL),
        json=[
            {
                "name" : "foo",
                "id" : 10
            }
        ],
        status = 200
    )
    custom_fields.fetch_cf_value("foo")
    assert custom_fields.CF_CACHE["foo"] == 10


@responses.activate
def test_fetch_cf_value_2():
    """ Test to get cf id from server api"""
    custom_fields.CF_CACHE = {}
    shared.globals.CONFIGURATION = {
        "cf_use_server_api": True,
        "cf_use_cloud_api": False,
        "cf_cachefile": "nothing"
    }
    shared.globals.ROOT_URL = "https://mock-server/"
    start_at = 1
    responses.add(
        responses.GET,
        "%s/rest/api/2/customFields?startAt=%s" % (shared.globals.ROOT_URL, start_at),
        json={
            "values" : [
                {
                    "name" : "foo",
                    "id" : 10
                }
            ]
        },
        status = 200
    )
    custom_fields.fetch_cf_value("foo")
    assert custom_fields.CF_CACHE["foo"] == 10


@responses.activate
def test_fetch_cf_value_3():
    custom_fields.CF_CACHE = {}
    shared.globals.CONFIGURATION = {
        "cf_use_server_api": False,
        "cf_use_cloud_api": True,
        "cf_cachefile": "nothing"
    }
    shared.globals.ROOT_URL = "https://mock-server/"
    responses.add(
        responses.GET,
        "%s/rest/api/3/field" % (shared.globals.ROOT_URL),
        json=[
            {
                "name" : "foo",
                "id" : 10
            }
        ],
        status = 200
    )
    with mock.patch('builtins.open', side_effect=OSError):
        custom_fields.fetch_cf_value("foo")
    assert custom_fields.CF_CACHE["foo"] == 10


@responses.activate
def test_get_1():
    """ Test to check if custom field doesn't exits"""
    custom_fields.CF_CACHE = {}
    shared.globals.CONFIGURATION = {
        "cf_use_server_api": False,
        "cf_use_cloud_api": True,
        "cf_cachefile": "nothing"
    }
    shared.globals.ROOT_URL = "https://mock-server/"
    rsp = responses.get(
        "%s/rest/api/3/field" % (shared.globals.ROOT_URL),
        json=[
            {
                "name" : "foo",
                "id" : 10
            }
        ],
        status = 200
    )
    result = custom_fields.get("bar")
    assert result is None
    assert custom_fields.CF_CACHE == {}
    assert rsp.call_count == 1
