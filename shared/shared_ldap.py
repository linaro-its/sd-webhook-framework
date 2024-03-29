#!/usr/bin/python3
"""
Handles all interactions between the automation and LDAP.

The credentials used by this code must be sufficient for all of
the functions required, e.g. creating accounts.
"""

# pylint: disable=no-member, broad-except

from ldap3 import (BASE, DSA, LEVEL, MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE,
                   SUBTREE, Connection, Server)
from unidecode import unidecode

import shared.globals
from shared import shared_google

MAILING_OU = ",ou=mailing,"
CN_PATH = "cn=%s,%s"


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
        return f"{str1}{separator}{str2}"


def cleanup_if_gmail(email_address):
    """
    Sanity check for gmail.com addresses. Google ignores full-stops in the
    first part of the email address so "fredbloggs@gmail.com" is identical
    to "fred.bloggs@gmail.com" as far as syncing is concerned so we cannot
    allow duplicates to be created.
    """
    parts = email_address.split('@')
    if parts[1] == "gmail.com":
        email_address = f"{parts[0].replace('.', '')}@{parts[1]}"
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
        search_filter=f"({ldap_filter}={safe_filter_param})",
        search_scope=SUBTREE
    )


def delete_object(entry_dn):
    """ Delete the specified object from LDAP """
    with get_ldap_connection() as conn:
        conn.delete(entry_dn)


def find_from_attribute(attribute, value):
    """
    Try to find a LDAP object where the specified attribute has the
    specified value.
    """
    with get_ldap_connection() as conn:
        if search_filter(conn, attribute, value):
            return conn.entries[0].entry_dn
    return None


def find_from_email(email_address):
    """
    Try to find an LDAP object from the email address provided.
    """
    return find_from_attribute("mail", email_address)


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
                search_filter=f"(uid={search_uid})",
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
                f"ou=accounts,{base_dn()}",
                search_filter=f"(mail={domain})",
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


def get_next_id_number(obj_class, id_attr):
    """ Searches the specified class to find the highest ID in use. """
    id_number = 0
    with get_ldap_connection() as conn:
        search_parameters = {
            'search_base': base_dn(),
            'search_filter': f'(objectclass={obj_class})',
            'attributes': [id_attr]
        }
        while True:
            conn.search(**search_parameters)
            for entry in conn.entries:
                this_id = int(entry[id_attr].value)
                if this_id > id_number:
                    id_number = this_id
            cookie = get_result_cookie(conn.result)
            if cookie:
                search_parameters['paged_cookie'] = cookie
            else:
                break
    return id_number+1


def get_next_uid_number():
    """ Searches the accounts to find the highest one in use. """
    return get_next_id_number("posixAccount", "uidNumber")


def get_next_gid_number():
    """ Searches the security groups to find the highest one in use. """
    return get_next_id_number("posixGroup", "gidNumber")


def create_account(first_name, family_name, email_address, password=None):
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
        "homeDirectory": f"/home/{uid}",
        "sn": family_name.encode("utf-8"),
        "mail": email_address,
        "loginShell": "/bin/bash",
        "uidNumber": str(get_next_uid_number())
    }
    if first_name is not None:
        add_record["givenName"] = first_name.encode('utf-8')
    if password is not None:
        add_record["userPassword"] = password
    with get_ldap_connection() as conn:
        if conn.add(
                f"uid={uid},{org_unit}",
                attributes=add_record):
            return f"uid={uid},{org_unit}"
    # Failed to create the account
    return None


def create_group(name, description, display_name, address, owners):
    """
    Create security & mailing groups in LDAP. This is somewhat
    Linaro-specific because of the classes used and the fact that
    there are both types of group.

    To that end, each type of group is only created if the relevant
    OU is specified in the configuration.
    """
    add_record = {
        'objectClass': ['extensibleObject', 'posixGroup', 'top'],
        'cn': name,
        'description': description,
        'displayName': display_name,
        'mail': address,
        'owner': owners,
        'gidNumber': str(get_next_gid_number())
    }
    # Figure out where to create this object
    path = shared.globals.config("ldap_security_groups")
    if path is not None:
        path = f"{path},{BASE_DN}"
        with get_ldap_connection() as conn:
            if not conn.add(
                CN_PATH % (name, path),
                attributes=add_record):
                return add_record

    # Now create the mailing group
    add_record.pop('gidNumber')
    add_record.pop('objectClass')
    add_record['objectClass'] = ['extensibleObject', 'groupOfUniqueNames']
    add_record['uniqueMember'] = ['']

    path = shared.globals.config("ldap_mailing_groups")
    if path is not None:
        path = f"{path},{BASE_DN}"
        with get_ldap_connection() as conn:
            if not conn.add(
                CN_PATH % (name, path),
                attributes=add_record):
                return add_record

    return None

def is_user_in_group(group_name, user_email, recurse=False):
    """ Is the user in the group? """
    user_dn = find_from_email(user_email)
    return is_dn_in_group(group_name, user_dn, recurse)


def is_dn_in_group(group_name, user_dn, recurse=False):
    """
    Simplify checking if someone is in a group. This also avoids
    the needs for handlers to know about the group_location_tag.

    We only do this for DNs because that is what handlers get back
    from find_from_email.

    We optionally recurse through nested groups.
    """
    result = parameterised_member_of_group(
        group_name,
        "ldap_mailing_groups",
        "uniqueMember",
        user_dn)
    if result or not recurse:
        return result
    #
    # See if there are any groups nested in this group. The use of
    # the uniqueMember filter ensures we only get the mailing list.
    group_details = find_matching_objects(
        f"(&(cn={group_name})(uniqueMember=*))",
        ["uniqueMember"])
    if group_details is None:
        # Shouldn't happen as we know the group exists
        return False
    for member in group_details[0].uniqueMember.values:
        if member[:3] == "cn=":
            group_cn = extract_id_from_dn(member)
            if is_dn_in_group(group_cn, user_dn):
                return True
    return False


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
            search_filter=f"({member_attribute}={member_value})",
            search_scope=BASE)


def parameterised_build_group_dn(
        group_name,
        group_location_tag):
    """ Calculate the DN for the group depending on the location. """
    return CN_PATH % (
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
        print(f"Adding {member_value} as a {member_attribute} attribute to {grp_dn}")
        result = conn.modify(grp_dn, change)
        if not result:
            print("Group modification failed")
            print(conn.result)
        return result


def extract_id_from_dn(distinguished_name):
    """ Return the CN or the UID from the DN """
    # Given a DN of, say, cn=everyone,ou=mailing,ou=groups,dc=linaro,dc=org
    # split("=", 1)[1] returns everything after the first =
    # split(",", 1)[0] returns everything before the first ,
    return distinguished_name.split("=", 1)[1].split(",", 1)[0]


def add_to_security_group(group_name, add_dn):
    """ Add the user to the specified security group. """
    # Start by extracting the uid from the DN.
    uid = extract_id_from_dn(add_dn)
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


def add_owner_to_security_group(group_name, add_dn):
    """ Add the DN as an owner to the specified security group. """
    return parameterised_add_to_group(
        group_name,
        "ldap_security_groups",
        "owner",
        add_dn
    )


def add_owner_to_mailing_group(group_name, add_dn):
    """ Add the DN as an owner to the specified mailing group. """
    return parameterised_add_to_group(
        group_name,
        "ldap_mailing_groups",
        "owner",
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


def add_owner_to_group(group_name, add_dn):
    """ Add owner to specified group """
    part_1 = add_owner_to_security_group(group_name, add_dn)
    part_2 = add_owner_to_mailing_group(group_name, add_dn)
    return part_1 and part_2


def parameterised_remove_from_group(
        group_name,
        group_location_tag,
        member_attribute,
        member_value):
    """
    A generalised "remove from group" function that can be used for both
    security and mailing groups by adjusting the parameters passed.
    """
    with get_ldap_connection() as conn:
        # Not in the group already?
        if not parameterised_member_of_group(
                group_name,
                group_location_tag,
                member_attribute,
                member_value):
            return True

        # Yes so remove them
        change = {
            member_attribute: [(MODIFY_DELETE, [member_value])]
        }
        # Calculate the DN.
        grp_dn = parameterised_build_group_dn(group_name, group_location_tag)
        print(f"Removing {member_value} as a {member_attribute} attribute from {grp_dn}")
        result = conn.modify(grp_dn, change)
        if not result:
            print("Group modification failed")
            print(conn.result)
        return result


def remove_from_security_group(group_name, object_dn):
    """ Remove the user from the specified security group. """
    # Start by extracting the uid from the DN.
    uid = extract_id_from_dn(object_dn)
    return parameterised_remove_from_group(
        group_name,
        "ldap_security_groups",
        "memberUid",
        uid
    )


def remove_from_mailing_group(group_name, object_dn):
    """ Remove the DN from the specified mailing group. """
    return parameterised_remove_from_group(
        group_name,
        "ldap_mailing_groups",
        "uniqueMember",
        object_dn
    )


def remove_owner_from_security_group(group_name, object_dn):
    """ Remove the DN from the specified security group's owners. """
    return parameterised_remove_from_group(
        group_name,
        "ldap_security_groups",
        "owner",
        object_dn
    )


def remove_owner_from_mailing_group(group_name, object_dn):
    """ Remove the DN from the specified mailing group's owners. """
    return parameterised_remove_from_group(
        group_name,
        "ldap_mailing_groups",
        "owner",
        object_dn
    )


def remove_from_group(group_name, object_dn):
    """
    Remove the specified DN from the specified group.

    Linaro's LDAP implementation uses two different types of group:
    * posixGroup for security groups
    * groupOfUniqueNames for mailing groups

    The latter can nest other groups, so if "add_dn" starts with cn=
    instead of uid=, that is a group and not an account, so it just
    gets removed from the mailing group.
    """
    if object_dn.split("=", 1)[0] == "uid":
        part_1 = remove_from_security_group(group_name, object_dn)
    else:
        part_1 = True
    part_2 = remove_from_mailing_group(group_name, object_dn)
    return part_1 and part_2


def remove_owner_from_group(group_name, object_dn):
    """ Remove owner from specified group """
    part_1 = remove_owner_from_security_group(group_name, object_dn)
    part_2 = remove_owner_from_mailing_group(group_name, object_dn)
    return part_1 and part_2


def get_object(object_dn, attributes):
    """ Retrieve the specified object from LDAP. """
    with get_ldap_connection() as conn:
        if conn.search(
                object_dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=attributes):
            return conn.entries[0]
    return None


def find_matching_objects(ldap_filter, attributes, base=None):
    """ Return any objects matching the search filter."""
    # Set base here rather than in the function definition to avoid
    # base_dn() being called when Python loads the library.
    if base is None:
        base = base_dn()
    with get_ldap_connection() as conn:
        if conn.search(
                base,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=attributes):
            return conn.entries
    return None


def replace_attribute_value(object_dn, attribute_name, new_value):
    """ Replace the value for the specified attribute. """
    if new_value is None:
        change = {
            attribute_name: [(MODIFY_REPLACE, [])]
        }
    else:
        change = {
            attribute_name: [(MODIFY_REPLACE, [new_value])]
        }
    with get_ldap_connection() as conn:
        conn.modify(
            object_dn,
            change
        )


def move_object(current_dn, new_ou):
    """ Move the specified object into the new OU. """
    with get_ldap_connection() as conn:
        if not conn.modify_dn(
                current_dn,
                current_dn.split(",", 1)[0],
                new_superior=new_ou):
            return conn.result
    return None


def find_group(name, attributes):
    """
    Try to find a group with the given email address or, failing that, the name.
    Returns the canonical email address for the found group and the requested attributes.
    """
    if "@" not in name:
        # We don't have an email address so try to get one
        result = find_matching_objects(
            f"(&(objectClass=groupOfUniqueNames)(cn={name}))",
            ["mail"]
        )
        if result is None:
            result = []
        if len(result) != 1:
            return (name, result)
        # A group may have more than one email address. Using "values"
        # always ensures we get a list back, making [0] safe.
        mail_entry = result[0].mail.values
        if mail_entry != []:
            name = mail_entry[0]

    # Now get the values for the specified attributes for
    # this group.
    result = find_matching_objects(
        f"(&(objectClass=groupOfUniqueNames)(mail={name}))",
        attributes
    )
    if result is None:
        result = []

    # Let's try and be super smart and see if this is an alias for a group :)
    if result == [] and shared.globals.CONFIGURATION["google_enabled"]:
        google = shared_google.check_group_alias(name)
        if google is not None:
            return find_group(google, attributes)

    return (name, result)


def reporter_is_group_owner(owner_list):
    """Check whether or not the reporter is an owner of the group."""
    # Start by getting the full DN for the reporter.
    reporter_dn = find_from_email(shared.globals.REPORTER)
    if reporter_dn is None:
        # Shouldn't happen ...
        return False

    is_owner = False
    for owner in owner_list:
        if MAILING_OU in owner:
            grp_name = owner.split(',', 1)[0].split('=')[1]
            if is_dn_in_group(grp_name, reporter_dn, True):
                is_owner = True
        elif owner == reporter_dn:
            is_owner = True
    return is_owner


def flatten_list(starting_list):
    """ Expand groups to individuals to end up with a single list of names. """
    enabled = shared.globals.config("ldap_enabled")
    if enabled is None or not enabled:
        return starting_list

    result = []
    for item in starting_list:
        if item != "":
            process_list_member(item, result)
    return result


def process_list_member(item, result):
    """ Process an individual list member when flattening. """
    if MAILING_OU in item:
        name = extract_id_from_dn(item)
        recurse = get_group_membership(name)
        for member in recurse:
            if member not in result:
                result.append(member)
    elif item not in result:
        result.append(item)


def get_group_membership(group_name):
    """ Recursively build list of everyone in the specified group. """
    _, result = find_group(group_name, ["uniqueMember"])
    members = []
    for member in result[0].uniqueMember.values:
        if MAILING_OU in member:
            members += get_group_membership(member)
        else:
            members.append(member)
    return members


def find_single_object_from_email(email_address):
    """
    Try to find a single object in LDAP that matches the provided
    email address. Return None if no match or more than 1 match.
    """
    result = find_matching_objects(
        f"(&(objectClass=groupOfUniqueNames)(mail={email_address}))",
        ["cn"])
    if result is not None and len(result) == 1:
        return result[0].entry_dn

    result = find_matching_objects(
        f"(&(objectClass=posixAccount)(mail={cleanup_if_gmail(email_address)}))",
        ["cn"])
    if result is not None and len(result) == 1:
        return result[0].entry_dn

    # Linaro uses the aRecord attribute to record email aliases so look
    # there as well ...
    result = find_matching_objects(
        f"(&(objectClass=posixAccount)(aRecord={cleanup_if_gmail(email_address)}))",
        ["cn"])
    if result is not None and len(result) == 1:
        return result[0].entry_dn

    # If still no match, try again without the GMail cleanup just in case
    # a GMail account was added without the cleanup.
    result = find_matching_objects(
        f"(&(objectClass=posixAccount)(mail={email_address}))",
        ["cn"])
    if result is not None and len(result) == 1:
        return result[0].entry_dn

    return None


def get_manager_from_dn(distinguished_name):
    """ Get the manager DN from the staff DN """
    result = get_object(distinguished_name, ["manager"])
    if result is not None and result.manager.value is not None:
        mgr_email = get_object(result.manager.value, ["mail"])
        if mgr_email is not None and mgr_email.mail.values != []:
            return mgr_email.mail.values[0]
    return None


def get_email_address(user_dn):
    """For the given user_dn, provide the email address from LDAP."""
    result = get_object(user_dn, ["mail"])
    if result is not None:
        return result.mail.value
    print(f"Either can't find {user_dn} or no mail attribute.")
    return None


def add_member_to_group(group_cn, member_dn):
    """ Add the specified LDAP entity to the group as appropriate """
    # Only add people (uid=*) to the security group. Add both users and groups
    # to the mail group.
    print(f"Being asked to add {member_dn} to {group_cn}")
    if member_dn.split("=", 1)[0] == "uid":
        add_to_security_group(group_cn, member_dn)
    print("Adding to mail group")
    add_to_mailing_group(group_cn, member_dn)
