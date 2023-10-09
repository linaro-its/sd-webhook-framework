""" Manages and initialises globals used across the code. """

import base64
import json
import os
import sys

from json_minify import json_minify

import shared.shared_vault as shared_vault
import shared.shared_sd as shared_sd

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

class InvalidCFConfig(SharedGlobalsError):
    """ The CF config is invalid. """

class MalformedJSON(SharedGlobalsError):
    """ The configuration file is not valid JSON. """

def initialise_ticket_data(ticket_data):
    """ Initialise the ticket data global. """
    global TICKET_DATA
    TICKET_DATA = ticket_data


def initialise_shared_sd():
    """ Initialise the code. """
    global ROOT_URL, TICKET, TICKET_DATA, PROJECT, REPORTER
    # Get the ticket details from the data and save it.
    if TICKET_DATA is None:
        raise MalformedIssueError("No data provided")
    # There is a difference between the structure used by Server and Cloud.
    if "issue" in TICKET_DATA:
        TICKET_DATA = TICKET_DATA["issue"]
    if "self" not in TICKET_DATA:
        raise MalformedIssueError("Missing 'self' in issue")
    if "key" not in TICKET_DATA:
        raise MalformedIssueError("Missing 'key' in issue")
    if "fields" not in TICKET_DATA:
        raise MalformedIssueError("Missing 'fields' in issue")
    if "project" not in TICKET_DATA["fields"]:
        raise MalformedIssueError("Missing 'project' in fields")
    if "key" not in TICKET_DATA["fields"]["project"]:
        raise MalformedIssueError("Missing 'key' in project")
    # Need to initialise these here because we might
    # need the Jira values if we call find_account_from_id
    issue_url = TICKET_DATA["self"].split("/", 3)
    ROOT_URL = f"{issue_url[0]}//{issue_url[2]}"
    if ("reporter" not in TICKET_DATA["fields"] or
        "emailAddress" not in TICKET_DATA["fields"]["reporter"]):
        # Jira Cloud doesn't include the email address so try fetching it
        # through the account ID
        reporter = shared_sd.find_account_from_id(TICKET_DATA["fields"]["reporter"]["accountId"])
        if "emailAddress" not in reporter:
            print(json.dumps(TICKET_DATA))
            raise MalformedIssueError("Missing reporter details in project")
        # If we get it, store it in the ticket data in case something else
        # wants it that way instead of using REPORTER
        TICKET_DATA["fields"]["reporter"]["emailAddress"] = reporter["emailAddress"]
    TICKET = TICKET_DATA["key"]
    PROJECT = TICKET_DATA["fields"]["project"]["key"]
    REPORTER = shared_sd.reporter_email_address(TICKET_DATA)


def validate_cf_config():
    """ Raise exceptions if the configuration has problems. """
    if "cf_use_server_api" not in CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_server_api' in config")
    if "cf_use_cloud_api" not in CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_cloud_api' in config")
    if CONFIGURATION["cf_use_server_api"] and CONFIGURATION["cf_use_cloud_api"]:
        raise InvalidCFConfig("Cannot use both server API and cloud API")
    if "cf_cachefile" not in CONFIGURATION:
        # Default to using the cache file in the repo.
        basedir = os.path.dirname(os.path.dirname(__file__))
        CONFIGURATION["cf_cachefile"] = f"{basedir}/cf_cachefile"


def validate_vault_tag(tag, required):
    """ Check if the tag is present when it needs to be. """
    if tag in CONFIGURATION:
        if not required:
            raise OverlappingCredentials(
                f"Can't have '{tag}' when a password has been specified "
                "in the configuration file"
            )
    else:
        if required:
            raise MissingCredentials(
                f"Missing '{tag}' in configuration file")


def validate_vault_config(vault_user_tag, required):
    """ Check the various vault config combinations. """
    validate_vault_tag(vault_user_tag, required)
    validate_vault_tag("vault_iam_role", required)
    validate_vault_tag("vault_server_url", required)


def validate_user_password_config(user_tag, password_tag, vault_user_tag):
    """ Check the user/password configuration is valid. """
    if user_tag not in CONFIGURATION:
        raise MissingCredentials(
            f"Missing '{user_tag}' in configuration file")
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
    filename = os.getenv("config_file", "configuration.jsonc")
    config_file = os.path.join(basedir, filename)
    print(f"Reading config from {config_file}", file=sys.stderr)
    try:
        with open(config_file, encoding="utf-8") as handle:
            CONFIGURATION = json.loads(json_minify(handle.read()))
    except json.decoder.JSONDecodeError as exc:
        raise MalformedJSON("Unable to decode configuration file successfully") from exc
    validate_cf_config()
    validate_auth_config()


def get_google_credentials():
    """ Retrieve the Google JSON blob """
    if "google_json_file" not in CONFIGURATION:
        return json.loads(shared_vault.get_secret(CONFIGURATION["vault_google_name"]))
    return json.load(open(CONFIGURATION["google_json_file"], encoding="utf-8"))


def get_ldap_credentials():
    """ Retrieve the credentials required by the LDAP code """
    if "ldap_password" not in CONFIGURATION:
        return CONFIGURATION["ldap_user"], shared_vault.get_secret(CONFIGURATION["vault_ldap_name"])
    return CONFIGURATION["ldap_user"], CONFIGURATION["ldap_password"]


def get_sd_credentials():
    """ Retrieve the credentials required by SD_AUTH """
    if "bot_password" not in CONFIGURATION:
        # Try API key first
        pwd = shared_vault.get_secret(CONFIGURATION["vault_bot_name"], "api-token")
        if pwd is None:
            pwd = shared_vault.get_secret(CONFIGURATION["vault_bot_name"])
        return CONFIGURATION["bot_name"], pwd
    return CONFIGURATION["bot_name"], CONFIGURATION["bot_password"]


def get_email_credentials():
    """ Retrieve the credentials required when sending email """
    if "mail_user" not in CONFIGURATION:
        return None, None
    # We already known (from validate_auth_config) that we can only have
    # either password or vault settings so act accordingly.
    if "vault_mail_name" in CONFIGURATION:
        return CONFIGURATION["mail_user"], shared_vault.get_secret(CONFIGURATION["vault_mail_name"])
    return CONFIGURATION["mail_user"], CONFIGURATION["mail_password"]


def initialise_sd_auth():
    """ Initialise the SD_AUTH global. """
    global SD_AUTH
    name, password = get_sd_credentials()
    # Construct a string of the form username:password
    combo = f"{name}:{password}"
    # Encode it to Base64
    combo_bytes = combo.encode('ascii')
    base64_bytes = base64.b64encode(combo_bytes)
    SD_AUTH = base64_bytes.decode('ascii')


def config(key):
    """
    Provide a safe way of retrieving a key from the configuration.
    """
    if (CONFIGURATION is not None and
            key in CONFIGURATION):
        return CONFIGURATION[key]
    return None
