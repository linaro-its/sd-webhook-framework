#!/usr/bin/python3
"""
Handles all interactions between the automation and LDAP.

The credentials used by this code must be sufficient for all of
the functions required, e.g. creating accounts.
"""

from ldap3 import Server, Connection, SUBTREE, LEVEL, BASE, DSA, MODIFY_ADD
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
        enabled = shared.globals.config("ldap_enabled")
        if enabled is None or not enabled:
            raise NotEnabledError()
        user, password = shared.globals.get_ldap_credentials()
        server = Server(
            shared.globals.config("ldap_server"),
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
        BASE_DN = shared.globals.config("ldap_base_dn")
        if BASE_DN is None or BASE_DN == "":
            with get_ldap_connection() as conn:
                bases = conn.server.info.naming_contexts
                BASE_DN = bases[0]
    return BASE_DN


def string_combo(str1, str2, separator):
    """
    Return a joined string with a separator, or just one of the strings if
    the other is empty or None.
    """
    if str1 is None or str1 == "":
        return str2
    elif str2 is None or str2 == "":
        return str1
    else:
        return "%s%s%s" % (str1, separator, str2)


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
    """
    Perform a parameterised filter search. If there are any
    brackets in the filter_param, we "escape" them so that
    LDAP doesn't have a hissy fit.
    """
    safe_filter_param = filter_param.replace("(", "\\28")
    safe_filter_param = safe_filter_param.replace(")", "\\29")
    return ldap_conn.search(
        base_dn(),
        search_filter="(%s=%s)" % (ldap_filter, safe_filter_param),
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
    uid = string_combo(firstname, lastname, ".").lower()

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
    default_ou = shared.globals.config("ldap_default_account_ou")
    return string_combo(
        default_ou,
        base_dn(),
        ","
    )


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


def is_dn_in_group(group_name, user_dn):
    """
    Simplify checking if someone is in a group. This also avoids
    the needs for handlers to know about the group_location_tag.

    We only do this for DNs because that is what handlers get back
    from find_from_email.
    """
    return parameterised_member_of_group(
        group_name,
        "ldap_mailing_groups",
        "uniqueMember",
        user_dn)


def parameterised_member_of_group(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    Determine if the member_value is in the group.
    """
    grp_dn = parameterised_build_group_dn(group_name, group_location_tag)
    with get_ldap_connection() as conn:
        return conn.search(
            grp_dn,
            search_filter="(%s=%s)" % (member_attribute, member_value),
            search_scope=BASE)


def parameterised_build_group_dn(
        group_name,
        group_location_tag):
    """ Calculate the DN for the group depending on the location. """
    return "cn=%s,%s" % (
        group_name,
        string_combo(
            shared.globals.config(group_location_tag),
            base_dn(),
            ","
        ))


def parameterised_add_to_group(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A generalised "add to group" function that can be used for both
    security and mailing groups by adjusting the parameters passed.
    """
    with get_ldap_connection() as conn:
        # In the group already?
        if parameterised_member_of_group(
                group_name,
                group_location_tag,
                member_attribute,
                member_value):
            return True

        # No, so add them.
        change = {
            member_attribute: [(MODIFY_ADD, [member_value])]
        }
        # Calculate the DN.
        grp_dn = parameterised_build_group_dn(group_name, group_location_tag)
        print("Adding %s as a %s attribute to %s" % (member_value, member_attribute, grp_dn))
        result = conn.modify(grp_dn, change)
        if not result:
            print(conn.result)
        return result


def add_to_security_group(group_name, add_dn):
    """ Add the user to the specified security group. """
    # Start by extracting the uid from the DN.
    uid = add_dn.split("=", 1)[1].split(",", 1)[0]
    return parameterised_add_to_group(
        group_name,
        "ldap_security_groups",
        "memberUid",
        uid
    )


def add_to_mailing_group(group_name, add_dn):
    """ Add the DN to the specified mailing group. """
    return parameterised_add_to_group(
        group_name,
        "ldap_mailing_groups",
        "uniqueMember",
        add_dn
    )


def add_to_group(group_name, add_dn):
    """
    Add the specified DN to the specified group.

    Linaro's LDAP implementation uses two different types of group:
    * posixGroup for security groups
    * groupOfUniqueNames for mailing groups

    The latter can nest other groups, so if "add_dn" starts with cn=
    instead of uid=, that is a group and not an account, so it just
    gets added to the mailing group.
    """
    if add_dn.split("=", 1)[0] == "uid":
        part_1 = add_to_security_group(group_name, add_dn)
    else:
        part_1 = True
    part_2 = add_to_mailing_group(group_name, add_dn)
    return part_1 and part_2
