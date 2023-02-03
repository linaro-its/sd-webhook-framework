#!/usr/bin/python3
""" Test the shared google library. """
import shared.shared_google as shared_google
import shared.globals
import mock

def mock_json_blob_test(json_blob, scopes):
    assert json_blob == "{\'password\":\"secret\'}"
    assert scopes == [
    'https://www.googleapis.com/auth/admin.directory.user.security',
    'https://www.googleapis.com/auth/admin.directory.user',
    'https://www.googleapis.com/auth/admin.directory.user.alias',
    'https://www.googleapis.com/auth/admin.directory.group.readonly',
    'https://www.googleapis.com/auth/admin.datatransfer',
    'https://www.googleapis.com/auth/spreadsheets'
]

@mock.patch(
    'shared.shared_google.service_account.Credentials.from_service_account_info',
    side_effect = mock_json_blob_test,
    autospec=True
)
@mock.patch('shared.shared_google.shared.globals.get_google_credentials',
return_value = "{\'password\":\"secret\'}",
autospec=True
)
def test_get_credentials(mi1, mi2):
    """Test to get_credentials"""

    shared_google.get_credentials()
    assert mi1.called is True
    assert mi2.called is True


def test_check_group_alias_1():
    """Test check_group_alias"""
    # Check when 'google_enabled' is False or None.
    shared.globals.CONFIGURATION = {}
    result = shared_google.check_group_alias("mock@mock.com")
    assert result is None


# def test_check_group_alias_2(mi1):
#     """Test check_group_alias"""
#     # Check when 'google_enabled' is True.
#     shared.globals.CONFIGURATION = {
#         "google_enabled": True,
#         "vault_google_name": "foo"
#     }
#     shared_google.check_group_alias("mock@mock.com")
#     assert mi1.called is True