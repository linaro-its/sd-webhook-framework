""" Manages and initialises globals used across the code. """

import json
import os
import sys

import vault_auth
from json_minify import json_minify
from requests.auth import HTTPBasicAuth

CONFIGURATION = None

TICKET_DATA = None

SD_AUTH = None
ROOT_URL = None
TICKET = None
PROJECT = None
REPORTER = None

# pylint: disable=global-statement

class SharedGlobalsError(Exception):
    """ Base exception class for the library. """

class MalformedIssueError(SharedGlobalsError):
    """ Malformed issue exception. """

class MissingCredentials(SharedGlobalsError):
    """ Missing credentials exception. """

class OverlappingCredentials(SharedGlobalsError):
    """ Overlapping credentials exception. """

class MissingCFConfig(SharedGlobalsError):
    """ Some part of the CF config is missing. """

def initialise_ticket_data(ticket_data):
    """ Initialise the ticket data global. """
    global TICKET_DATA
    TICKET_DATA = ticket_data


def initialise_shared_sd():
    """ Initialise the code. """
    global ROOT_URL, TICKET, PROJECT, REPORTER
    # Get the ticket details from the data and save it
    if TICKET_DATA is None or "issue" not in TICKET_DATA:
        raise MalformedIssueError("Missing 'issue' in data")
    if "self" not in TICKET_DATA["issue"]:
        raise MalformedIssueError("Missing 'self' in issue")
    if "key" not in TICKET_DATA["issue"]:
        raise MalformedIssueError("Missing 'key' in issue")
    if "fields" not in TICKET_DATA["issue"]:
        raise MalformedIssueError("Missing 'fields' in issue")
    if "project" not in TICKET_DATA["issue"]["fields"]:
        raise MalformedIssueError("Missing 'project' in fields")
    if "key" not in TICKET_DATA["issue"]["fields"]["project"]:
        raise MalformedIssueError("Missing 'key' in project")
    if ("reporter" not in TICKET_DATA["issue"]["fields"] or
        "emailAddress" not in TICKET_DATA["issue"]["fields"]["reporter"]):
        raise MalformedIssueError("Missing reporter details in project")
    issue_url = TICKET_DATA["issue"]["self"].split("/", 3)
    ROOT_URL = "%s//%s" % (issue_url[0], issue_url[2])
    TICKET = TICKET_DATA["issue"]["key"]
    PROJECT = TICKET_DATA["issue"]["fields"]["project"]["key"]
    REPORTER = TICKET_DATA["issue"]["fields"]["reporter"]["emailAddress"]


def validate_cf_config():
    """ Raise exceptions if the configuration has problems. """
    if "cf_use_plugin_api" not in CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_plugin_api' in config")
    if "cf_use_cloud_api" not in CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_cloud_api' in config")
    if "cf_cachefile" not in CONFIGURATION:
        # Default to using the cache file in the repo.
        basedir = os.path.dirname(os.path.dirname(__file__))
        CONFIGURATION["cf_cachefile"] = "%s/cf_cachefile" % basedir


def validate_vault_tag(tag, required):
    """ Check if the tag is present when it needs to be. """
    if tag in CONFIGURATION:
        if not required:
            raise OverlappingCredentials(
                "Can't have '%s' when a password has been specified "
                "in the configuration file" % tag
            )
    else:
        if required:
            raise MissingCredentials(
                "Missing '%s' in configuration file" % tag)


def validate_vault_config(vault_user_tag, required):
    """ Check the various vault config combinations. """
    validate_vault_tag(vault_user_tag, required)
    validate_vault_tag("vault_iam_role", required)
    validate_vault_tag("vault_server_url", required)


def validate_user_password_config(user_tag, password_tag, vault_user_tag):
    """ Check the user/password configuration is valid. """
    if user_tag not in CONFIGURATION:
        raise MissingCredentials(
            "Missing '%s' in configuration file" % user_tag)
    if password_tag not in CONFIGURATION:
        # Make sure that all of the Vault values are there
        validate_vault_config(vault_user_tag, True)
    else:
        # We're using a password to authenticate with. Just as a sanity check,
        # make sure that the Vault user tag is not there. We don't care about
        # the IAM role or server URL because they could be needed by one of the
        # other auth sections in the config.
        validate_vault_tag(vault_user_tag, False)


def validate_auth_config():
    """ Raise exceptions if the configuration has problems. """
    validate_user_password_config("bot_name", "bot_password", "vault_bot_name")
    if "ldap_enabled" in CONFIGURATION and CONFIGURATION["ldap_enabled"]:
        validate_user_password_config("ldap_user", "ldap_password", "vault_ldap_name")
    if "mail_host" in CONFIGURATION and "mail_user" in CONFIGURATION:
        # Only check mail auth if we have a server and a user defined.
        validate_user_password_config("mail_user", "mail_password", "vault_mail_name")


def initialise_config():
    """ Read the JSON configuration file into a global JSON blob. """
    global CONFIGURATION
    # All of the webhook code is in a sub-directory so we
    # expect to find the configuration file one level up.
    basedir = os.path.dirname(os.path.dirname(__file__))
    config_file = os.path.join(basedir, "configuration.jsonc")
    print("Reading config from %s" % config_file, file=sys.stderr)
    with open(config_file) as handle:
        CONFIGURATION = json.loads(json_minify(handle.read()))
    validate_cf_config()
    validate_auth_config()


def get_google_credentials():
    """ Retrieve the Google JSON blob """
    global CONFIGURATION
    if "google_json_file" not in CONFIGURATION:
        secret = vault_auth.get_secret(
            CONFIGURATION["vault_google_name"],
            iam_role=CONFIGURATION["vault_iam_role"],
            url=CONFIGURATION["vault_server_url"]
        )
        return secret["data"]["pw"]
    return json.load(open(CONFIGURATION["google_json_file"]))


def get_ldap_credentials():
    """ Retrieve the credentials required by the LDAP code """
    global CONFIGURATION
    if "ldap_password" not in CONFIGURATION:
        secret = vault_auth.get_secret(
            CONFIGURATION["vault_ldap_name"],
            iam_role=CONFIGURATION["vault_iam_role"],
            url=CONFIGURATION["vault_server_url"]
        )
        # This assumes that the password will be stored in the "pw" key.
        return CONFIGURATION["ldap_user"], secret["data"]["pw"]
    return CONFIGURATION["ldap_user"],\
        CONFIGURATION["ldap_password"]


def get_sd_credentials():
    """ Retrieve the credentials required by SD_AUTH """
    global CONFIGURATION
    if "bot_password" not in CONFIGURATION:
        secret = vault_auth.get_secret(
            CONFIGURATION["vault_bot_name"],
            iam_role=CONFIGURATION["vault_iam_role"],
            url=CONFIGURATION["vault_server_url"]
        )
        # This assumes that the password will be stored in the "pw" key.
        return CONFIGURATION["bot_name"], secret["data"]["pw"]
    return CONFIGURATION["bot_name"],\
        CONFIGURATION["bot_password"]


def get_email_credentials():
    """ Retrieve the credentials required when sending email """
    global CONFIGURATION
    if "mail_user" not in CONFIGURATION:
        return None, None
    # We already known (from validate_auth_config) that we can only have
    # either password or vault settings so act accordingly.
    if "vault_mail_name" in CONFIGURATION:
        secret = vault_auth.get_secret(
            CONFIGURATION["vault_mail_name"],
            iam_role=CONFIGURATION["vault_iam_role"],
            url=CONFIGURATION["vault_server_url"]
        )
        # This assumes that the password will be stored in the "pw" key.
        return CONFIGURATION["mail_user"], secret["data"]["pw"]
    return CONFIGURATION["mail_user"], CONFIGURATION["mail_password"]


def initialise_sd_auth():
    """ Initialise the SD_AUTH global. """
    global SD_AUTH
    name, password = get_sd_credentials()
    SD_AUTH = HTTPBasicAuth(name, password)


def config(key):
    """
    Provide a safe way of retrieving a key from the configuration.
    """
    if (CONFIGURATION is not None and
            key in CONFIGURATION):
        return CONFIGURATION[key]
    return None
