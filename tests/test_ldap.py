#!/usr/bin/python3
""" Test the shared LDAP library. """

import mock
import pytest

import shared.shared_ldap as shared_ldap
import shared.globals

@mock.patch(
    'shared.globals.get_ldap_credentials',
    return_value=("mock_user", "mock_password"),
    autospec=True
)
@mock.patch(
    'shared.shared_ldap.Connection',
    return_value=123,
    autospec=True
)
def test_get_ldap_connection(mi1, mi2):
    """ Test get_ldap_connection. """
    shared_ldap.CONNECTION = None
    shared.globals.CONFIGURATION = {}
    with pytest.raises(shared_ldap.NotEnabledError):
        shared_ldap.get_ldap_connection()
    shared.globals.CONFIGURATION = {
        "ldap_enabled": False
    }
    with pytest.raises(shared_ldap.NotEnabledError):
        shared_ldap.get_ldap_connection()
    shared.globals.CONFIGURATION = {
        "ldap_enabled": True,
        "ldap_server": "foo"
    }
    result = shared_ldap.get_ldap_connection()
    assert result == 123
    assert mi1.called is True
    assert mi2.called is True


def test_cleanup_if_gmail():
    """ Test cleanup_if_gmail. """
    assert shared_ldap.cleanup_if_gmail(
        "one.two.three@gmail.com") == "onetwothree@gmail.com"


class MockLDAP3Value: # pylint: disable=too-few-public-methods
    """ Mock up a way of storing attribute values. """
    value = None

class MockLDAP3Entry: # pylint: disable=too-few-public-methods
    """ Mock up the Entry class. """
    entry_dn = None
    uidNumber = MockLDAP3Value()

class MockLDAP3Info: # pylint: disable=too-few-public-methods
    """ Mock up the Info class. """
    naming_contexts = [
        "naming_context_1",
        "naming_context_2"
    ]

class MockLDAP3Server: # pylint: disable=too-few-public-methods
    """ Mock up the Server class. """
    info = MockLDAP3Info()

class MockLDAP3Connection: # pylint: disable=too-few-public-methods
    """ Mock up the Connection class. """
    server = MockLDAP3Server()
    fake_search_result = True
    flip_search_result = False
    add_result = True
    entries = []
    result = []

    def __init__(self,
                 server=None,
                 user=None,
                 password=None,
                 auto_bind=None):
        _ = server
        _ = user
        _ = password
        _ = auto_bind
        entry1 = MockLDAP3Entry()
        entry1.entry_dn = "entry_dn_1"
        entry1.uidNumber.value = "10000"
        self.entries.append(entry1)
        entry2 = MockLDAP3Entry()
        entry2.entry_dn = "entry_dn_2"
        entry2.uidNumber.value = "10001"
        self.entries.append(entry2)

    # pylint: disable=too-many-arguments
    def search(self,
               search_base,
               search_filter,
               search_scope=None,
               attributes=None,
               paged_cookie=None):
        """ Fake Connection.search """
        _ = search_base
        _ = search_filter
        _ = search_scope
        _ = attributes
        _ = paged_cookie
        result = self.fake_search_result
        if self.flip_search_result:
            # Switch the search result so that we don't
            # always return the same value. Useful for testing
            # code that loops (like get_best_uid).
            self.fake_search_result = not self.fake_search_result
        return result

    def add(self, ldap_dn, object_class=None, attributes=None, controls=None):
        """ Validate what we're creating against the test values. """
        _ = object_class
        _ = controls
        assert ldap_dn == "uid=fred.flintstone,ou=the-rest,ou=accounts,dc=linaro,dc=org"
        assert attributes["cn"] == "fred.flintstone@widget.org"
        assert attributes["homeDirectory"] == "/home/fred.flintstone"
        assert attributes["sn"] == b"Flintstone"
        assert attributes["mail"] == "fred.flintstone@widget.org"
        assert attributes["givenName"] == b"Fred"
        assert attributes["uidNumber"] == "10002"
        return self.add_result

    # Required to support context manager
    def __enter__(self):
        return self
    def __exit__(self, type, value, traceback): # pylint: disable=redefined-builtin
        pass


def test_base_dn():
    """ Test base_dn. """
    shared_ldap.BASE_DN = None
    shared.globals.CONFIGURATION = {
        "ldap_base_dn": "Test"
    }
    assert shared_ldap.base_dn() == "Test"

    shared_ldap.BASE_DN = None
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared.globals.CONFIGURATION = {}
    assert shared_ldap.base_dn() == "naming_context_1"


def test_search_filter():
    """ Test search_filter. """
    shared_ldap.BASE_DN = "base_dn"
    conn = MockLDAP3Connection()
    conn.fake_search_result = False
    assert shared_ldap.search_filter(conn, "one", "two") is False
    conn.fake_search_result = True
    assert shared_ldap.search_filter(conn, "one", "two") is True


def test_find_from_email():
    """ Test find_from_email. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = True
    assert shared_ldap.find_from_email("foo") == "entry_dn_1"
    shared_ldap.CONNECTION.fake_search_result = False
    assert shared_ldap.find_from_email("foo") is None


def test_get_best_uid():
    """ Test get_best_uid. """
    shared_ldap.BASE_DN = "base_dn"
    conn = MockLDAP3Connection()
    conn.fake_search_result = True
    conn.flip_search_result = True
    # By setting the initial search result to True and
    # flip to True, the first call to connection.search
    # will return True then will return False. So, we
    # should end up with a uid of "blah1".
    assert shared_ldap.get_best_uid(conn, "blah") == "blah1"
    # Now, if we set the initial search result to False,
    # the first call to connection.search will return
    # False and so we should get the same uid back that we
    # pass in.
    conn.fake_search_result = False
    conn.flip_search_result = False
    assert shared_ldap.get_best_uid(conn, "blah") == "blah"


def test_calculate_uid():
    """ Test calculate_uid. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = False
    shared_ldap.CONNECTION.flip_search_result = False
    assert shared_ldap.calculate_uid("Fred", "Flintstone") == "fred.flintstone"
    assert shared_ldap.calculate_uid(None, "Enya") == "enya"


def test_find_best_ou():
    """ Test find_best_ou_for_email. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = False
    shared_ldap.CONNECTION.flip_search_result = False
    assert shared_ldap.find_best_ou_for_email("fred@flintstone") == \
        "ou=the-rest,ou=accounts,dc=linaro,dc=org"
    shared_ldap.CONNECTION.fake_search_result = True
    assert shared_ldap.find_best_ou_for_email("fred@flintstone") == \
        "entry_dn_1"


def test_get_result_cookie():
    """ Test get_result_cookie. """
    result = {
        'controls': {
            '1.2.840.113556.1.4.319': {
                'value': {
                    'cookie': 'mock-cookie'
                }
            }
        }
    }
    assert shared_ldap.get_result_cookie(result) == "mock-cookie"
    result = {}
    assert shared_ldap.get_result_cookie(result) is None


COOKIE_COUNT = 0

def mock_get_result_cookie(result):
    """
    A mock version of 'get_result_cookie' so that we return
    a string cookie on the first call and None on subsequent
    calls, to ensure that the calling code doesn't get stuck
    in a loop.
    """
    global COOKIE_COUNT  # pylint: disable=global-statement
    _ = result
    COOKIE_COUNT += 1
    if COOKIE_COUNT > 1:
        return None
    return "mock-cookie"


@mock.patch(
    'shared.shared_ldap.get_result_cookie',
    side_effect=mock_get_result_cookie,
    autospec=True
)
def test_get_next_uid_number(mi1):
    """ Test get_next_uid_number. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    # We use a cookie counter to ensure that:
    # a) all of the code in get_next_uid_number gets tested
    # b) we don't get stuck in the while True loop
    global COOKIE_COUNT  # pylint: disable=global-statement
    COOKIE_COUNT = 0
    assert shared_ldap.get_next_uid_number() == 10002
    assert mi1.called is True


def mock_get_best_uid(connection, uid):
    """
    Mock get_best_uid to just return the uid we're passed.
    Doing this avoids too many (conflicting) calls to the
    search functionality while testing create_account.
    """
    _ = connection
    return uid

@mock.patch(
    'shared.shared_ldap.get_result_cookie',
    side_effect=mock_get_result_cookie,
    autospec=True
)
@mock.patch(
    'shared.shared_ldap.get_best_uid',
    side_effect=mock_get_best_uid,
    autospec=True
)
def test_create_account(mi1, mi2):
    """ Test create_account. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = False
    global COOKIE_COUNT  # pylint: disable=global-statement
    COOKIE_COUNT = 0
    # Intially, we want a successful result ...
    shared_ldap.CONNECTION.add_result = True
    shared_ldap.create_account("Fred", "Flintstone", "fred.flintstone@widget.org")
    # Fake a failure to create the account to ensure that all of the
    # create_account code is tested.
    shared_ldap.CONNECTION.add_result = False
    shared_ldap.create_account("Fred", "Flintstone", "fred.flintstone@widget.org")
    assert mi1.called is True
    assert mi2.called is True
