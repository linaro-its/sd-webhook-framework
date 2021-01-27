#!/usr/bin/python3
"""
Handles all interactions between the automation and Google.

To avoid the need to initialise the authentication, a service
account must be used.

https://developers.google.com/identity/protocols/oauth2/service-account
"""

from google.oauth2 import service_account
import googleapiclient
from googleapiclient.discovery import build

import shared.globals

SCOPES = [
    'https://www.googleapis.com/auth/admin.directory.user.security',
    'https://www.googleapis.com/auth/admin.directory.user',
    'https://www.googleapis.com/auth/admin.directory.user.alias',
    'https://www.googleapis.com/auth/admin.directory.group.readonly',
    'https://www.googleapis.com/auth/admin.datatransfer',
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_credentials():
    """ Build the Google credentials. """
    json_blob = shared.globals.get_google_credentials()
    return service_account.Credentials.from_service_account_info(
        json_blob, scopes=SCOPES)

def check_group_alias(email):
    """ See if we can find a group on Google with the specified email address. """
    if shared.globals.config("google_enabled") in (None, False):
        return None

    delegated_creds = get_credentials().with_subject(shared.globals.CONFIGURATION["google_admin"])
    try:
        # We don't cache the discovery because it generates warnings.
        # https://stackoverflow.com/a/44518587/1233830
        with build(
                'admin',
                'directory_v1',
                credentials=delegated_creds,
                cache_discovery=False) as service:
            response = service.groups().get(groupKey=email).execute()
            if "aliases" in response:
                # There are aliases on this group. We only care if there are
                # aliases because the caller will already have checked LDAP,
                # so groups without aliases will match on the LDAP test.
                return response["email"]
    except googleapiclient.errors.HttpError:
        pass
    return None
