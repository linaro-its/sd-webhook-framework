""" Manages and initialises globals used across the code. """

import os
import json
from json_minify import json_minify
from requests.auth import HTTPBasicAuth
import vault_auth

CONFIGURATION = None

TICKET_DATA = None

SD_AUTH = None
ROOT_URL = None
TICKET = None
PROJECT = None

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

def initialise_ticket_data(request_data):
    """ Initialise the ticket data global """
    global TICKET_DATA
    TICKET_DATA = json.loads(request_data)


def initialise_shared_sd():
    """ Initialise the code. """
    global ROOT_URL, TICKET, PROJECT
    # Get the ticket details from the data and save it
    if "issue" not in TICKET_DATA:
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
    issue_url = TICKET_DATA["issue"]["self"].split("/", 3)
    ROOT_URL = "%s//%s" % (issue_url[0], issue_url[2])
    TICKET = TICKET_DATA["issue"]["key"]
    PROJECT = TICKET_DATA["issue"]["fields"]["project"]["key"]


def validate_cf_config():
    """ Raise exceptions if the configuration has problems. """
    if "cf_use_plugin_api" not in CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_plugin_api' in config")
    if "cf_use_cloud_api" not in CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_cloud_api' in config")
    if "cf_cachefile" not in CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_cachefile' in config")


def validate_vault_tag(tag, required):
    """ Check if the tag is present when it needs to be. """
    if tag in CONFIGURATION:
        if not required:
            raise OverlappingCredentials(
                "Can't have 'bot_password' and '%s'" % tag)
    else:
        if required:
            raise MissingCredentials(
                "Missing '%s' in configuration file" % tag)


def validate_vault_config(required):
    """ Check the various vault config combinations. """
    validate_vault_tag("vault_bot_name", required)
    validate_vault_tag("vault_iam_role", required)
    validate_vault_tag("vault_server_url", required)


def validate_auth_config():
    """ Raise exceptions if the configuration has problems. """
    if "bot_name" not in CONFIGURATION:
        raise MissingCredentials(
            "Missing 'bot_name' in configuration file")
    if "bot_password" not in CONFIGURATION:
        # Make sure that the Vault values are there
        validate_vault_config(True)
    else:
        # We're using a password to authenticate with. Just as a sanity check,
        # make sure that the Vault values are NOT there.
        validate_vault_config(False)


def initialise_config():
    """ Read the JSON configuration file into a global JSON blob. """
    global CONFIGURATION
    # All of the webhook code is in a sub-directory so we
    # expect to find the configuration file one level up.
    basedir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(basedir, "configuration.jsonc")) as handle:
        CONFIGURATION = json.loads(json_minify(handle.read()))
    validate_cf_config()
    validate_auth_config()


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

def initialise_sd_auth():
    """ Initialise the SD_AUTH global. """
    global SD_AUTH
    name, password = get_sd_credentials()
    SD_AUTH = HTTPBasicAuth(name, password)
