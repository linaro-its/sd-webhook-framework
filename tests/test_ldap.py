#!/usr/bin/python3
""" Test the shared LDAP library. """

import mock
import pytest

from ldap3 import MODIFY_ADD, MODIFY_DELETE
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
    def __init__(self) -> None:
        self._value = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v


class MockLDAP3Entry: # pylint: disable=too-few-public-methods
    """ Mock up the Entry class. """
    def __init__(self) -> None:
        self._entry_dn = None
        self._uidNumber = MockLDAP3Value()

    @property
    def entry_dn(self):
        return self._entry_dn

    @entry_dn.setter
    def entry_dn(self, v):
        self._entry_dn = v

    @property
    def uidNumber(self):
        return self._uidNumber

    @uidNumber.setter
    def uidNumber(self, v):
        self._uidNumber = v

    def __getitem__(self, i):
        if i == "entry_dn":
            return self._entry_dn
        if i == "uidNumber":
            return self._uidNumber
        raise Exception(f"Attribute {i} not found")


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
        assert ldap_dn == "uid=fred.flintstone,base_dn"
        assert attributes is not None
        assert attributes["cn"] == "fred.flintstone@widget.org"
        assert attributes["homeDirectory"] == "/home/fred.flintstone"
        assert attributes["sn"] == b"Flintstone"
        assert attributes["mail"] == "fred.flintstone@widget.org"
        assert attributes["givenName"] == b"Fred"
        assert attributes["uidNumber"] == "10002"
        return self.add_result

    def modify(self, ldap_dn, change):
        """
        Mock the modify function. Return the change so that the test code can
        validate we've been called correctly.
        """
        _ = self
        _ = ldap_dn
        return change

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


def test_string_combo():
    """ Test string_combo. """
    assert shared_ldap.string_combo("string1", None, ".") == "string1"
    assert shared_ldap.string_combo("string1", "", ".") == "string1"
    assert shared_ldap.string_combo(None, "string2", ".") == "string2"
    assert shared_ldap.string_combo("", "string2", ".") == "string2"
    assert shared_ldap.string_combo("string1", "string2", ".") == "string1.string2"


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
    shared.globals.CONFIGURATION = {}
    assert shared_ldap.find_best_ou_for_email("fred@flintstone") == \
        "base_dn"
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
    shared.globals.CONFIGURATION = {}
    shared_ldap.CONNECTION.add_result = True
    shared_ldap.create_account("Fred", "Flintstone", "fred.flintstone@widget.org")
    # Create user acoount with passowrd.
    shared_ldap.create_account("Fred", "Flintstone", "fred.flintstone@widget.org", "password")
    # Fake a failure to create the account to ensure that all of the
    # create_account code is tested.
    shared_ldap.CONNECTION.add_result = False
    shared_ldap.create_account("Fred", "Flintstone", "fred.flintstone@widget.org")
    assert mi1.called is True
    assert mi2.called is True


def test_parameterised_add_to_group():
    """ Test parameterised_add_to_group. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = True
    assert shared_ldap.parameterised_add_to_group(
        "fake-group",
        "ldap_security_groups",
        "memberUid",
        "fred.flintstone") is True
    shared_ldap.CONNECTION.fake_search_result = False
    expected_results = {
        "memberUid": [(MODIFY_ADD, ["fred.flintstone"])]
    }
    assert shared_ldap.parameterised_add_to_group(
        "fake-group",
        "ldap_security_groups",
        "memberUid",
        "fred.flintstone") == expected_results


def mock_parameterised_add_to_group_sec_test(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_add_to_group to test
    adding to a security group.
    """
    assert group_name == "mock_test_group_name"
    assert group_location_tag == "ldap_security_groups"
    assert member_attribute == "memberUid"
    assert member_value == "fred.flintstone"


@mock.patch(
    "shared.shared_ldap.parameterised_add_to_group",
    side_effect=mock_parameterised_add_to_group_sec_test,
    autospec=True
)
def test_add_to_security_group(mi1):
    """ Test add_to_security_group. """
    shared_ldap.add_to_security_group(
        "mock_test_group_name",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True


def mock_parameterised_add_to_group_mail_test(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_add_to_group to test
    adding to a mailing group.
    """
    assert group_name == "mock_test_group_name"
    assert group_location_tag == "ldap_mailing_groups"
    assert member_attribute == "uniqueMember"
    assert member_value == "uid=fred.flintstone,ou=accounts,base_dn"


@mock.patch(
    "shared.shared_ldap.parameterised_add_to_group",
    side_effect=mock_parameterised_add_to_group_mail_test,
    autospec=True
)
def test_add_to_mailing_group(mi1):
    """ Test add_to_mailing_group. """
    shared_ldap.add_to_mailing_group(
        "mock_test_group_name",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.add_to_security_group",
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.add_to_mailing_group",
    autospec=True
)
def test_add_to_group_1(mi1, mi2):
    """ Test add_to_group when add_dn starts with uid= """
    shared_ldap.add_to_group("group_name", "uid=fred.flintstone,ou=accounts,base_dn")
    assert mi1.called is True
    assert mi2.called is True


@mock.patch(
    "shared.shared_ldap.add_to_mailing_group",
    autospec=True
)
def test_add_to_group_2(mi1):
    """ Test add_to_group when add_dn starts with cn= """
    shared_ldap.add_to_group("group_name", "cn=foo.bar,ou=accounts,base_dn")
    assert mi1.called is True


def mock_parameterised_member_of_group_test(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_member_of_group to test it being
    called appropriately.
    """
    assert group_name == "mock-group"
    assert group_location_tag == "ldap_mailing_groups"
    assert member_attribute == "uniqueMember"
    assert member_value == "uid=fred.flintstone,ou=accounts,base_dn"
    return True


@mock.patch(
    "shared.shared_ldap.parameterised_member_of_group",
    side_effect=mock_parameterised_member_of_group_test,
    autospec=True
)
def test_is_dn_in_group_1(mi1):
    """ Test is_dn_in_group
    when the user is already in the group. """
    result = shared_ldap.is_dn_in_group("mock-group", "uid=fred.flintstone,ou=accounts,base_dn")
    assert result is True
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    return_value=None,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.parameterised_member_of_group",
    return_value=None,
    autospec=True
)
def test_is_dn_in_group_2(mi1, mi2):
    """ Test is_dn_in_group
    when the user is not in the group
    we are checking. Also, not a
    member of the nested group. """
    result = shared_ldap.is_dn_in_group(
        "mock-group",
        "uid=fred.flintstone,ou=accounts,base_dn",
        True
    )
    assert mi1.called is True
    assert mi2.called is True
    assert result is False


class MockUniqueMember_1:
    """
    A Mock class for unique member values.
    """
    values = ["uid=alf.flintstone,ou=accounts,base_dn"]

class MockResultObject_1:
    """
    A Mock class for matching
    object result. 
    """
    uniqueMember = MockUniqueMember_1()


def mock_find_matching_objects_test_1(
        ldap_filter,
        attributes,
        base=None):
    """
    A Mock test function for find_matching_objects. 
    """
    _ = ldap_filter
    _ = attributes
    _ = base
    result =  []
    result.append(MockResultObject_1())
    return result


@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    side_effect=mock_find_matching_objects_test_1,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.parameterised_member_of_group",
    return_value=None,
    autospec=True
)
def test_is_dn_in_group_3(mi1, mi2):
    """ Test is_dn_in_group
    when the user is not in the group
    we are checking. But, the user is a member of
    any nested group. """
    result = shared_ldap.is_dn_in_group(
        "mock-group",
        "uid=fred.flintstone,ou=accounts,base_dn",
        True
    )
    assert mi1.called is True
    assert mi2.called is True
    assert result is False


class MockUniqueMember_2:
    """
    A Mock class for unique member values.
    """
    values = ["cn=mock-group1,ou=groups,base_dn"]

class MockResultObject_2:
    """
    A Mock class for matching
    object result. 
    """
    uniqueMember = MockUniqueMember_2()


def mock_find_matching_objects_test_2(
        ldap_filter,
        attributes,
        base=None):
    """
    A Mock test function for find_matching_objects. 
    """
    _ = ldap_filter
    _ = attributes
    _ = base
    result =  []
    result.append(MockResultObject_2())
    return result


@mock.patch(
    "shared.shared_ldap.extract_id_from_dn",
    return_value="mock-group1",
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    side_effect=mock_find_matching_objects_test_2,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.parameterised_member_of_group",
    return_value=None,
    autospec=True
)
def test_is_dn_in_group_4(mi1, mi2, mi3):
    """ Test is_dn_in_group
    when the user is not in the group
    we are checking. But, the user is a member of
    any nested group. """
    result = shared_ldap.is_dn_in_group(
        "mock-group",
        "uid=fred.flintstone,ou=accounts,base_dn",
        True
    )
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True


def mock_add_owner_to_mailing_group(
        group_name,
        add_dn):
    """
    A Mock function for add_owner_to_security_group.
    """
    assert group_name == "mock_group"
    assert add_dn == "uid=fred.flintstone,ou=accounts,base_dn"


def mock_add_owner_to_security_group(
        group_name,
        add_dn):
    """
    A Mock function for add_owner_to_security_group.
    """
    assert group_name == "mock_group"
    assert add_dn == "uid=fred.flintstone,ou=accounts,base_dn"

@mock.patch(
    "shared.shared_ldap.add_owner_to_mailing_group",
    side_effct=mock_add_owner_to_mailing_group,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.add_owner_to_security_group",
    side_effect=mock_add_owner_to_security_group,
    autospec=True
)
def test_add_owner_to_group_1(mi1, mi2):
    """ Test add_owner_to_group. """
    shared_ldap.add_owner_to_group(
        "mock_group", "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert mi2.called is True


def mock_is_dn_in_group(
        group_name,
        user_dn,
        recurse=False):
    """
    A Mock function for is_dn_in_group.
    """
    assert group_name == "mock_group"
    assert user_dn == "uid=fred.flintstone,ou=accounts,base_dn"
    return True


@mock.patch(
    "shared.shared_ldap.is_dn_in_group",
    side_effect=mock_is_dn_in_group,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.find_from_email",
    return_value="uid=fred.flintstone,ou=accounts,base_dn",
    autospec=True
)
def test_is_user_in_group_1(mi1, mi2):
    """ Test is_user_in_group when 
    the LDAP object exists. """
    result = shared_ldap.is_user_in_group("mock_group", "fred.flintstone@widget.org")
    assert mi1.called is True
    assert mi2.called is True
    assert result is True


def mock_parameterised_add_to_group_sec(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_add_to_group to test
    adding an owner to a security group.
    """
    assert group_name == "mock_group"
    assert group_location_tag == "ldap_security_groups"
    assert member_attribute == "owner"
    assert member_value == "uid=fred.flintstone,ou=accounts,base_dn"


@mock.patch(
    "shared.shared_ldap.parameterised_add_to_group",
    side_effect=mock_parameterised_add_to_group_sec,
    autospec=True
)
def test_add_owner_to_security_group_1(mi1):
    """Test add_owner_to_security_group. """
    shared_ldap.add_owner_to_security_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.parameterised_add_to_group",
    return_value=True,
    autospec=True
)
def test_add_owner_to_security_group_2(mi1):
    """Test add_owner_to_security_group if
    DN is already an owner. """
    result = shared_ldap.add_owner_to_security_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert result is True


def mock_parameterised_add_to_group_mail(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_add_to_group to test
    adding an owner to a mailing group.
    """
    assert group_name == "mock_group"
    assert group_location_tag == "ldap_mailing_groups"
    assert member_attribute == "owner"
    assert member_value == "uid=fred.flintstone,ou=accounts,base_dn"


@mock.patch(
    "shared.shared_ldap.parameterised_add_to_group",
    side_effect=mock_parameterised_add_to_group_mail,
    autospec=True
)
def test_add_owner_to_mailing_group_1(mi1):
    """Test add_owner_to_mailing_group. """
    shared_ldap.add_owner_to_mailing_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.parameterised_add_to_group",
    return_value=True,
    autospec=True
)
def test_add_owner_to_mailing_group_2(mi1):
    """Test add_owner_to_mailing_group
    if DN is already an owner. """
    result = shared_ldap.add_owner_to_mailing_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert result is True


def mock_parameterised_remove_from_group_sec(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_remove_from_group to test
    removing a user from a security group.
    """
    assert group_name == "mock_group"
    assert group_location_tag == "ldap_security_groups"
    assert member_attribute == "memberUid"
    assert member_value == "fred.flintstone"


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    side_effect=mock_parameterised_remove_from_group_sec,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.extract_id_from_dn",
    return_value="fred.flintstone",
    autospec=True
)
def test_remove_from_security_group_1(mi1, mi2):
    """Test remove_from_security_group. """
    shared_ldap.remove_from_security_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert mi2.called is True


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    return_value=True,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.extract_id_from_dn",
    return_value="fred.flintstone",
    autospec=True
)
def test_remove_from_security_group_2(mi1, mi2):
    """Test remove_from_security_group
    when user is not a member of the security group. """
    result = shared_ldap.remove_from_security_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert mi2.called is True
    assert result is True


def mock_parameterised_remove_from_group_mail(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_add_to_group to test
    removing a user from mailing group.
    """
    assert group_name == "mock_group"
    assert group_location_tag == "ldap_mailing_groups"
    assert member_attribute == "uniqueMember"
    assert member_value == "uid=fred.flintstone,ou=accounts,base_dn"


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    side_effect=mock_parameterised_remove_from_group_mail,
    autospec=True
)
def test_remove_from_mailing_group_1(mi1):
    """Test remove_from_mailing_group. """
    shared_ldap.remove_from_mailing_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    return_value=True,
    autospec=True
)
def test_remove_from_mailing_group_2(mi1):
    """Test remove_from_mailing_group
    when user is not a member of the mailing group."""
    result = shared_ldap.remove_from_mailing_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert result is True


def mock_parameterised_remove_from_group_sg(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_add_to_group to test
    removing an owner from a security group.
    """
    assert group_name == "mock_group"
    assert group_location_tag == "ldap_security_groups"
    assert member_attribute == "owner"
    assert member_value == "uid=fred.flintstone,ou=accounts,base_dn"


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    side_effect=mock_parameterised_remove_from_group_sg,
    autospec=True
)
def test_remove_owner_from_security_group_1(mi1):
    """Test remove_owner_from_security_group. """
    shared_ldap.remove_owner_from_security_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    return_value=True,
    autospec=True
)
def test_remove_owner_from_security_group_2(mi1):
    """Test remove_owner_from_security_group
    when user is the owner of the security group. """
    result = shared_ldap.remove_owner_from_security_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert result is True


def mock_parameterised_remove_from_group_mg(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A mock parameterised_add_to_group to test
    removing an owner from a mailing group.
    """
    assert group_name == "mock_group"
    assert group_location_tag == "ldap_mailing_groups"
    assert member_attribute == "owner"
    assert member_value == "uid=fred.flintstone,ou=accounts,base_dn"


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    side_effect=mock_parameterised_remove_from_group_mg,
    autospec=True
)
def test_remove_owner_from_mailing_group_1(mi1):
    """Test remove_owner_from_mailing_group. """
    shared_ldap.remove_owner_from_mailing_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.parameterised_remove_from_group",
    return_value=True,
    autospec=True
)
def test_remove_owner_from_mailing_group_2(mi1):
    """Test remove_owner_from_mailing_group
    when user is the owner of the security group."""
    result = shared_ldap.remove_owner_from_mailing_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert result is True


def mock_remove_from_security_group_1(
        group_name,
        object_dn):
    """
    A mock function for remove_from_security_group.
    """
    assert group_name == "mock_group"
    assert object_dn == "uid=fred.flintstone,ou=accounts,base_dn"


def mock_remove_from_mailing_group_1(
        group_name,
        object_dn):
    """
    A mock function for remove_from_mailing_group.
    """
    assert group_name == "mock_group"
    assert object_dn == "uid=fred.flintstone,ou=accounts,base_dn"

@mock.patch(
    "shared.shared_ldap.remove_from_mailing_group",
    side_effect = mock_remove_from_mailing_group_1,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.remove_from_security_group",
    side_effect = mock_remove_from_security_group_1,
    autospec=True
)
def test_remove_from_group_1(mi1, mi2):
    """
    Test remove_from_group if the DN starts with uid=
    """
    shared_ldap.remove_from_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert mi2.called is True


def mock_remove_from_mailing_group_2(
        group_name,
        object_dn):
    """
    A mock function for remove_from_mailing_group.
    """
    assert group_name == "mock_mail_group"
    assert object_dn == "cn=mock_mail_group,ou=groups,base_dn"


@mock.patch(
    "shared.shared_ldap.remove_from_mailing_group",
    side_effect = mock_remove_from_mailing_group_2,
    autospec=True
)
def test_remove_from_group_2(mi1):
    """
    Test remove_from_group if the DN starts with cn=
    """
    shared_ldap.remove_from_group(
        "mock_mail_group",
        "cn=mock_mail_group,ou=groups,base_dn"
    )
    assert mi1.called is True


@mock.patch(
    "shared.shared_ldap.remove_from_mailing_group",
    return_value=True,
    autospec=True
)

def test_remove_from_group_3(mi1):
    """
    Test remove_from_group when DN is not a 
    member of both security and mailing group.
    """
    result = shared_ldap.remove_from_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert result is True


@mock.patch(
    "shared.shared_ldap.remove_owner_from_mailing_group",
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.remove_owner_from_security_group",
    autospec=True
)
def test_remove_owner_from_group_1(mi1, mi2):
    """Test remove_owner_from_group. """
    shared_ldap.remove_owner_from_group(
        "mock_group",
        "uid=fred.flintstone,ou=accounts,base_dn"
    )
    assert mi1.called is True
    assert mi2.called is True


def test_flatten_list_1():
    """Test flatten_list when ldap_enabled is False. """
    shared.globals.CONFIGURATION = {
        "ldap_enabled": False
    }
    starting_list = [
        "cn=mock_group,ou=mailing,base_dn"
    ]
    result = shared_ldap.flatten_list(starting_list)
    assert result == ['cn=mock_group,ou=mailing,base_dn']


def test_flatten_list_2():
    """Test flatten_list when ldap_enabled is None. """
    shared.globals.CONFIGURATION = {
        "ldap_enabled": None
    }
    starting_list = [
        "cn=mock_group,ou=mailing,base_dn"
    ]
    result = shared_ldap.flatten_list(starting_list)
    assert result == ['cn=mock_group,ou=mailing,base_dn']


def test_flatten_list_3():
    """Test flatten_list when starting_list is empty. """
    shared.globals.CONFIGURATION = {
        "ldap_enabled": True
    }
    starting_list = []
    result = shared_ldap.flatten_list(starting_list)
    assert result == []


@mock.patch(
    "shared.shared_ldap.process_list_member",
    autospec=True,
)
def test_flatten_list_4(mi1):
    """Test flatten_list when ldap_enabled is True
    and starting_list is not empty.
    """
    shared.globals.CONFIGURATION = {
        "ldap_enabled": True
    }
    starting_list = [
        "cn=mock_group1,ou=mailing,base_dn",
        "cn=mock_group2,ou=mailing,base_dn"
    ]
    result = shared_ldap.flatten_list(starting_list)
    assert mi1.called is True


def test_process_list_member_1():
    """ Test process_list_member
    when MAILING_OU is not in the item. """
    result = []
    item = "cn=mock_group1,ou=security,base_dn"
    shared_ldap.process_list_member(item, result)
    assert result == ["cn=mock_group1,ou=security,base_dn"]


def test_process_list_member_2():
    """ Test process_list_member
    when MAILING_OU is not in the item
    and result is not empty. """
    expected_result=[
        "uid=fred.flintstone,ou=accounts,base_dn",
        "cn=mock_group1,ou=security,base_dn"
    ]
    result = ["uid=fred.flintstone,ou=accounts,base_dn"]
    item = "cn=mock_group1,ou=security,base_dn"
    shared_ldap.process_list_member(item, result)
    assert result == expected_result


@mock.patch(
    "shared.shared_ldap.get_group_membership",
    return_value=["uid=fred.flintstone,ou=accounts,base_dn"],
    autospec=True,
)
@mock.patch(
    "shared.shared_ldap.extract_id_from_dn",
    return_value="mock_group1",
    autospec=True
)
def test_process_list_member_3(mi1, mi2):
    """ Test process_list_member
    when MAILING_OU is in the item
    and if the group member doesn't
    exist in the result list. """
    expected_result=["uid=fred.flintstone,ou=accounts,base_dn"]
    result = []
    item = "cn=mock_group1,ou=mailing,base_dn"
    shared_ldap.process_list_member(item, result)
    assert mi1.called is True
    assert mi2.called is True
    assert result == expected_result


@mock.patch(
    "shared.shared_ldap.get_group_membership",
    return_value=["uid=fred.flintstone,ou=accounts,base_dn"],
    autospec=True,
)
@mock.patch(
    "shared.shared_ldap.extract_id_from_dn",
    return_value="mock_group1",
    autospec=True
)
def test_process_list_member_4(mi1, mi2):
    """ Test process_list_member
    when MAILING_OU is in the item
    and if the group member already
    exists in the result list. """
    expected_result=["uid=fred.flintstone,ou=accounts,base_dn"]
    result = ["uid=fred.flintstone,ou=accounts,base_dn"]
    item = "cn=mock_group1,ou=mailing,base_dn"
    shared_ldap.process_list_member(item, result)
    assert mi1.called is True
    assert mi2.called is True
    assert result == expected_result


@mock.patch(
    "shared.shared_ldap.find_from_email",
    return_value=None,
    autospec=True
)
def test_reporter_is_group_owner_1(mi1):
    """Test reporter_is_group_owner
    when reporter DN doesn't exist. """
    shared.globals.TICKET_DATA = {
        "fields": {
            "reporter": {
                "emailAddress": "fred.flintstone@widget.org"
            }
        }
    }
    owner = ["uid=fred.flintstone,ou=accounts,base_dn"]
    result = shared_ldap.reporter_is_group_owner(owner)
    assert mi1.called is True
    assert result is False


@mock.patch(
    "shared.shared_ldap.find_from_email",
    return_value="uid=fred.flintstone,ou=accounts,base_dn",
    autospec=True
)
def test_reporter_is_group_owner_2(mi1):
    """Test reporter_is_group_owner
    when reporter DN exists AND
    the owner is not a Mailing Group. """
    shared.globals.TICKET_DATA = {
        "fields": {
            "reporter": {
                "emailAddress": "fred.flintstone@widget.org"
            }
        }
    }
    owner = ["uid=fred.flintstone,ou=accounts,base_dn"]
    result = shared_ldap.reporter_is_group_owner(owner)
    assert mi1.called is True
    assert result is True


@mock.patch(
    "shared.shared_ldap.is_dn_in_group",
    return_value=True,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.find_from_email",
    return_value="cn=mock.group,ou=mailing,base_dn",
    autospec=True
)
def test_reporter_is_group_owner_3(mi1, mi2):
    """Test reporter_is_group_owner
    when reporter DN exists AND
    the owner is a Mailing Group. """
    shared.globals.TICKET_DATA = {
        "fields": {
            "reporter": {
                "emailAddress": "mock.group@widget.org"
            }
        }
    }
    owner = ["cn=mock.group,ou=mailing,base_dn"]
    result = shared_ldap.reporter_is_group_owner(owner)
    assert mi1.called is True
    assert mi2.called is True
    assert result is True


@mock.patch(
    "shared.shared_ldap.is_dn_in_group",
    return_value=False,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.find_from_email",
    return_value="cn=mock.group,ou=mailing,base_dn",
    autospec=True
)
def test_reporter_is_group_owner_4(mi1, mi2):
    """Test reporter_is_group_owner
    when reporter DN exists AND
    the owner is an empty Mailing Group. """
    shared.globals.TICKET_DATA = {
        "fields": {
            "reporter": {
                "emailAddress": "mock.group@widget.org"
            }
        }
    }
    owner = ["cn=mock.group,ou=mailing,base_dn"]
    result = shared_ldap.reporter_is_group_owner(owner)
    assert mi1.called is True
    assert mi2.called is True
    assert result is False


@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    return_value=None,
    autospec=True
)
def test_find_group_1(mi1):
    """ Test find_group when group name has
    '@' and 'google_enabled' is False"""
    shared.globals.CONFIGURATION = {
        "google_enabled": False
    }
    group_name = "mock.group@widget.org"
    attribute = ["uniqueMember"]
    result = shared_ldap.find_group(group_name, attribute)
    assert mi1.called is True
    assert result == ('mock.group@widget.org', [])


@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    return_value=None,
    autospec=True
)
def test_find_group_2(mi1):
    """ Test find_group when group name
    doesn't include '@' and can't find any
    matching object. """
    group_name = "mock.group"
    attribute = ["uniqueMember"]
    result = shared_ldap.find_group(group_name, attribute)
    assert mi1.called is True
    assert result == ('mock.group', [])


@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    return_value=[
        "cn=mock.group,ou=mailing,base_dn",
        "cn=mock.group1,ou=mailing,base_dn"
    ],
    autospec=True
)
def test_find_group_3(mi1):
    """ Test find_group when group name
    doesn't include '@' and finds more or less
    than one result in LDAP.  """
    group_name = "mock.group"
    attribute = ["uniqueMember"]
    result = shared_ldap.find_group(group_name, attribute)
    assert mi1.called is True
    assert result == (
        'mock.group',
        [
            'cn=mock.group,ou=mailing,base_dn',
            'cn=mock.group1,ou=mailing,base_dn'
        ]
    )


@mock.patch(
    "shared.shared_ldap.shared_google.check_group_alias",
    return_value=None,
    autospec=True
)
@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    return_value=[],
    autospec=True
)
def test_find_group_5(mi1, mi2):
    """ Test find_group when group name has
    '@' AND 'google_enabled' is True AND
    there is no aliases in Google. """
    shared.globals.CONFIGURATION = {
        "google_enabled": True
    }
    group_name = "mock.group@widget.org"
    attribute = ["uniqueMember"]
    result = shared_ldap.find_group(group_name, attribute)
    assert mi1.called is True
    assert mi2.called is True
    assert result == ('mock.group@widget.org', [])


mock.patch(
    "shared.shared_ldap.get_object",
    return_value=None,
    autospec=True
)
def test_get_manager_from_dn_1():
    """ Test get_manager_from_dn function
    when get_object returns None. """
    dn = "uid=fred.flintstone,ou=accounts,base_dn"
    result = shared_ldap.get_manager_from_dn(dn)
    assert result is None


class MockMailObject_2():
    """ A Mock mail object. """
    values = ["alf.flintstone@widget.org", "alf1.flintstone@widget.org"]


class MockManagerObject_2:
    """ A Mock manager object. """
    value = "uid=alf.flintstone,ou=accounts,base_dn"
    mail = MockMailObject_2()


class MockGetObject_2():
    """ A Mock object for querying manager. """
    manager = MockManagerObject_2()


@mock.patch(
    "shared.shared_ldap.get_object",
    side_effect=[MockGetObject_2, MockManagerObject_2],
    autospec=True
)
def test_get_manager_from_dn_2(mi1):
    """ Test get_manager_from_dn function
    when the staff has a manager attribute.
    """
    dn = "uid=fred.flintstone,ou=accounts,base_dn"
    result = shared_ldap.get_manager_from_dn(dn)
    assert mi1.called is True
    assert result == "alf.flintstone@widget.org"


class MockGetObject_3():
    """ A Mock object for querying manager. """
    manager = None


@mock.patch(
    "shared.shared_ldap.get_object",
    side_effect=[MockGetObject_3],
    autospec=True
)
def test_get_manager_from_dn_3(mi1):
    """ Test get_manager_from_dn function
    when result.manager is None.
    """
    dn = "uid=fred.flintstone,ou=accounts,base_dn"
    result = shared_ldap.get_manager_from_dn(dn)
    assert mi1.called is True
    assert result is None


class MockManagerObject_4:
    """ A Mock manager object. """
    value = None


class MockGetObject_4():
    """ A Mock object for querying manager. """
    manager = MockManagerObject_4()


@mock.patch(
    "shared.shared_ldap.get_object",
    side_effect=[MockGetObject_4, MockManagerObject_4],
    autospec=True
)
def test_get_manager_from_dn_4(mi1):
    """ Test get_manager_from_dn function
    when result.manager.value is None.
    """
    dn = "uid=fred.flintstone,ou=accounts,base_dn"
    result = shared_ldap.get_manager_from_dn(dn)
    assert mi1.called is True
    assert result is None


class MockManagerObject_5:
    """ A Mock manager object. """
    value = "uid=alf.flintstone,ou=accounts,base_dn"
    mail = None


class MockGetObject_5():
    """ A Mock object for querying manager. """
    manager = MockManagerObject_2()


@mock.patch(
    "shared.shared_ldap.get_object",
    side_effect=[MockGetObject_5, MockManagerObject_5],
    autospec=True
)
def test_get_manager_from_dn_5(mi1):
    """ Test get_manager_from_dn function
    when the value of mgr_email.mail is None.
    """
    dn = "uid=fred.flintstone,ou=accounts,base_dn"
    result = shared_ldap.get_manager_from_dn(dn)
    assert mi1.called is True
    assert result is None


class MockMailObject_6():
    """ A Mock mail object. """
    values = []


class MockManagerObject_6:
    """ A Mock manager object. """
    value = "uid=alf.flintstone,ou=accounts,base_dn"
    mail = MockMailObject_6()


class MockGetObject_6():
    """ A Mock object for querying manager. """
    manager = MockManagerObject_6()


@mock.patch(
    "shared.shared_ldap.get_object",
    side_effect=[MockGetObject_6, MockManagerObject_6],
    autospec=True
)
def test_get_manager_from_dn_6(mi1):
    """ Test get_manager_from_dn function
    when mail.values is an empty List.
    """
    dn = "uid=fred.flintstone,ou=accounts,base_dn"
    result = shared_ldap.get_manager_from_dn(dn)
    assert mi1.called is True
    assert result is None


@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    return_value=None,
    autospec=True
)
def test_find_single_object_from_email_1(mi1):
    """Test find_single_object_from_email
    when LDAP returns no matching object. """
    result = shared_ldap.find_single_object_from_email("mock.group@widget.org")
    assert mi1.called is True
    assert result is None


class MockMatchingObject_2:
    """ A Mock matching object. """
    entry_dn = "uid=fred.flintstone,ou=accounts,base_dn"


def mock_find_matching_objects_2(
        ldap_filter,
        attributes,
        base=None):
    """
    A mock function for 'find_matching_objects'
    to return a matched object. 
    """
    _ = ldap_filter
    _ = attributes
    _ = base
    result = []
    result.append(MockMatchingObject_2())
    return result

@mock.patch(
    "shared.shared_ldap.find_matching_objects",
    side_effect=mock_find_matching_objects_2,
    autospec=True
)
def test_find_single_object_from_email_2(mi1):
    """Test find_single_object_from_email
    when LDAP returns a matching object. """
    result = shared_ldap.find_single_object_from_email("fred.flintstone@widget.org")
    assert mi1.called is True
    assert result == "uid=fred.flintstone,ou=accounts,base_dn"


class MockUniquieMemberValues_1:
    """A Mock class for uniqueMember.values. """
    values = [
        "uid=fred.flintstone,ou=accounts,base_dn",
        "uid=alf.flintstone,ou=accounts,base_dn"
    ]


class MockUniquieMember_1:
    """ A mock class for uniqueMember. """
    uniqueMember = MockUniquieMemberValues_1()


def mock_find_group_1(
        name,
        attributes):
    """ A mock function for find_group. """
    _ = name
    _ = attributes
    result = []
    result.append(MockUniquieMember_1())
    return ("mock.group@widget.org", result)

@mock.patch(
    "shared.shared_ldap.find_group",
    side_effect=mock_find_group_1,
    autospec=True
)
def test_get_group_membership_1(mi1):
    """Test get_group_membership
    when the group is not empty. """
    result = shared_ldap.get_group_membership("mock.group@widget.org")
    assert mi1.called is True
    assert result == [
        'uid=fred.flintstone,ou=accounts,base_dn',
        'uid=alf.flintstone,ou=accounts,base_dn'
    ]

class MockUniquieMemberValues_2:
    """A Mock class for uniqueMember.values. """
    values = []


class MockUniquieMember_2:
    """ A mock class for uniqueMember. """
    uniqueMember = MockUniquieMemberValues_2()


def mock_find_group_2(
        name,
        attributes):
    """ A mock function for find_group. """
    _ = name
    _ = attributes
    result = []
    result.append(MockUniquieMember_2())
    return ("mock.group@widget.org", result)

@mock.patch(
    "shared.shared_ldap.find_group",
    side_effect=mock_find_group_2,
    autospec=True
)
def test_get_group_membership_2(mi1):
    """Test get_group_membership
    when the group is empty. """
    result = shared_ldap.get_group_membership("mock.group@widget.org")
    assert mi1.called is True
    assert result == []


def test_parameterised_remove_from_group_1():
    """ Test parameterised_remove_from_group. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = False
    assert shared_ldap.parameterised_remove_from_group(
        "fake-group",
        "ldap_security_groups",
        "memberUid",
        "fred.flintstone") is True
    shared_ldap.CONNECTION.fake_search_result = True
    expected_results = {
        "memberUid": [(MODIFY_DELETE, ["fred.flintstone"])]
    }
    assert shared_ldap.parameterised_remove_from_group(
        "fake-group",
        "ldap_security_groups",
        "memberUid",
        "fred.flintstone") == expected_results


def test_get_object():
    """ Test get_object. """
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = False
    assert shared_ldap.get_object(
        "uid=fred.flintstone,ou=accounts,base_dn",
        "mail"
    ) is None
    shared_ldap.CONNECTION.fake_search_result = True
    shared_ldap.get_object(
        "uid=fred.flintstone,ou=accounts,base_dn",
        "mail"
    )


def test_replace_attribute_value_1():
    """Test replace_attribute_value
    when new value is None."""
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.replace_attribute_value(
        "uid=fred.flintstone,ou=accounts,base_dn",
        "mail",
        None
    )


def test_replace_attribute_value_2():
    """Test replace_attribute_value
    when new value is NOT None."""
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.replace_attribute_value(
        "uid=fred.flintstone,ou=accounts,base_dn",
        "mail",
        "fred.flintstone@gmail.com"
    )


def test_find_matching_objects_1():
    """Test find_matching_objects
    when no matching object exists."""
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = False
    filters = "mock.group@widget.org"
    attribute = ["uniqueMember"]
    result = shared_ldap.find_matching_objects(
        filters,
        attributes=attribute
    )
    assert result is None


def test_find_matching_objects_2():
    """Test find_matching_objects
    when there is a matching object exists."""
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared_ldap.CONNECTION.fake_search_result = True
    filters = "mock.group@widget.org"
    attribute = ["uniqueMember"]
    shared_ldap.find_matching_objects(
        filters,
        attributes=attribute
    )


@mock.patch(
    "shared.shared_ldap.get_next_gid_number",
    return_value="10002",
    autospec=True
)
def test_create_group_1(mi1):
    """Test create_group."""
    shared_ldap.BASE_DN = "base_dn"
    shared_ldap.CONNECTION = MockLDAP3Connection()
    shared.globals.CONFIGURATION = {
        "ldap_security_groups": None,
    }
    group_name = "mock.group"
    description = "Mock Group"
    display_name = "Mock Group"
    address = "mock.group@widget.org"
    owners = ["fred.flintstone@widget.org"]

    shared_ldap.create_group(
        group_name,
        description,
        display_name,
        address,
        owners
    )
    assert mi1.called is True
