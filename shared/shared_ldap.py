#!/usr/bin/python3
"""
Handles all interactions between the automation and LDAP.

The credentials used by this code must be sufficient for all of
the functions required, e.g. creating accounts.
"""

from ldap3 import Server, Connection, SUBTREE, LEVEL, DSA
from unidecode import unidecode
import shared.globals


class NotEnabledError(Exception):
    """ LDAP not enabled exception. """


CONNECTION = None
BASE_DN = None


def get_ldap_connection():
    """ Return the shared LDAP connection, initialising first if required. """
    global CONNECTION  # pylint: disable=global-statement
    if CONNECTION is None:
        if ("ldap_enabled" not in shared.globals.CONFIGURATION or
                not shared.globals.CONFIGURATION["ldap_enabled"]):
            raise NotEnabledError()
        user, password = shared.globals.get_ldap_credentials()
        server = Server(
            shared.globals.CONFIGURATION["ldap_server"],
            get_info=DSA
        )
        CONNECTION = Connection(
            server,
            user=user,
            password=password,
            auto_bind=True
        )
    return CONNECTION


def base_dn():
    """ Return the base DN for this configuration. """
    global BASE_DN  # pylint: disable=global-statement
    if BASE_DN is None:
        if ("ldap_base_dn" in shared.globals.CONFIGURATION and
                shared.globals.CONFIGURATION["ldap_base_dn"] != ""):
            BASE_DN = shared.globals.CONFIGURATION["ldap_base_dn"]
        else:
            with get_ldap_connection() as conn:
                bases = conn.server.info.naming_contexts
                BASE_DN = bases[0]
    return BASE_DN


def cleanup_if_gmail(email_address):
    """
    Sanity check for gmail.com addresses. Google ignores full-stops in the
    first part of the email address so "fredbloggs@gmail.com" is identical
    to "fred.bloggs@gmail.com" as far as syncing is concerned so we cannot
    allow duplicates to be created.
    """
    parts = email_address.split('@')
    if parts[1] == "gmail.com":
        email_address = "%s@%s" % (parts[0].replace('.', ''), parts[1])
    return email_address


def search_filter(ldap_conn, ldap_filter, filter_param):
    """ Perform a parameterised filter search. """
    return ldap_conn.search(
        base_dn(),
        search_filter="(%s=%s)" % (ldap_filter, filter_param),
        search_scope=SUBTREE
    )


def find_from_email(email_address):
    """
    Try to find an LDAP object from the email address provided.
    """
    # Use the naming contexts from the server as the base for the search.
    # with get_ldap_connection() as conn:
    with get_ldap_connection() as conn:
        for ldap_filter in ("mail", "passwordSelfResetBackupMail"):
            if search_filter(conn, ldap_filter, email_address):
                return conn.entries[0].entry_dn
    return None


def calculate_uid(firstname, lastname):
    """
    For a given firstname and lastname, work out a UID that doesn't already
    exist in LDAP.
    """
    if firstname is None:
        uid = lastname.lower()
    else:
        uid = firstname.lower() + "." + lastname.lower()

    # Remove bad characters
    uid = unidecode(uid)
    uid = uid.replace("'", "")
    uid = uid.replace(" ", "")

    with get_ldap_connection() as conn:
        return get_best_uid(conn, uid)


def get_best_uid(connection, uid):
    """
    Search existing accounts to see if we need to bump the uid with
    an increasing numerical suffix.
    """
    got_uid = False
    index = 0
    while not got_uid:
        search_uid = uid
        if index != 0:
            search_uid += str(index)
        if connection.search(
                base_dn(),
                search_filter="(uid=%s)" % search_uid,
                search_scope=SUBTREE):
            index += 1
        else:
            uid = search_uid
            got_uid = True
    return uid


def find_best_ou_for_email(email_address):
    """
    For a given email address, provide the best matching OU on LDAP.

    ... This is quite Linaro-specific :)
    """
    domain = email_address.split("@")[1]
    with get_ldap_connection() as conn:
        if conn.search(
                "ou=accounts,%s" % base_dn(),
                search_filter="(mail=%s)" % domain,
                search_scope=LEVEL):
            return conn.entries[0].entry_dn
    return "ou=the-rest,ou=accounts,dc=linaro,dc=org"


def get_result_cookie(result):
    """ Safely retrieve the paging cookie from the search results. """
    if ('controls' in result and
            '1.2.840.113556.1.4.319' in result['controls'] and
            'value' in result['controls']['1.2.840.113556.1.4.319'] and
            'cookie' in result['controls']['1.2.840.113556.1.4.319']['value']['cookie']):
        return result['controls']['1.2.840.113556.1.4.319']['value']['cookie']
    return None


def get_next_uid_number():
    """ Searches the accounts to find the highest one in use. """
    uid_number = 0
    with get_ldap_connection() as conn:
        search_parameters = {
            'search_base': base_dn(),
            'search_filter': '(objectclass=posixAccount)',
            'attributes': ['uidNumber']
        }
        while True:
            conn.search(**search_parameters)
            for entry in conn.entries:
                this_uid = int(entry.uidNumber.value)
                if this_uid > uid_number:
                    uid_number = this_uid
            cookie = get_result_cookie(conn.result)
            if cookie:
                search_parameters['paged_cookie'] = cookie
            else:
                break
    return uid_number+1


def create_account(first_name, family_name, email_address):
    """
    Create an account for the specified person.

    ... Linaro specific because of the object classes used.
    """
    org_unit = find_best_ou_for_email(email_address)
    uid = calculate_uid(first_name, family_name)
    add_record = {
        "objectClass": [
            'person',
            'organizationalPerson',
            'inetOrgPerson',
            'ldapPublicKey',
            'passwordSelfReset',
            'posixAccount'
        ],
        "cn": email_address,
        "gidNumber": "10000",
        "homeDirectory": "/home/%s" % uid,
        "sn": family_name.encode("utf-8"),
        "mail": email_address,
        "loginShell": "/bin/bash"
    }
    if first_name is not None:
        add_record["givenName"] = first_name.encode('utf-8')
    add_record["uidNumber"] = str(get_next_uid_number())
    with get_ldap_connection() as conn:
        if conn.add(
                "uid=%s,%s" % (uid, org_unit),
                attributes=add_record):
            return "uid=%s,%s" % (uid, org_unit)
    # Failed to create the account
    return None
