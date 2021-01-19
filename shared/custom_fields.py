"""
Maintain a cache of custom field names to custom field IDs.

Note that the custom fields added by Service Desk will have varying IDs from
instance to instance, hence this file.

Two approaches:
1. Edit custom_fields.json to define the lookup table or
2. Use the Server or Cloud REST API to find the custom field with the
   required name.

For option 2, the cache file is updated since it avoids a round-trip to the
server.

The configured Service Desk account must have sufficient permissions to use
the REST APIs if they are enabled.
"""

import os
import json
import requests
import shared.globals


# Not in "globals" because only this module needs to reference it.
CF_CACHE = None


def initialise_cf_cache():
    """ Initialise the cache of field names to IDs. """
    global CF_CACHE  # pylint: disable=global-statement
    if CF_CACHE is None:
        # Load the cache from the file
        if os.path.isfile(shared.globals.CONFIGURATION["cf_cachefile"]):
            with open(shared.globals.CONFIGURATION["cf_cachefile"], "r") as handle:
                CF_CACHE = json.load(handle)
        else:
            CF_CACHE = {}


def service_desk_request_get(url):
    """Centralised routine to GET from Service Desk."""
    headers = {'content-type': 'application/json', 'X-ExperimentalApi': 'true'}
    return requests.get(url, headers=headers, auth=shared.globals.SD_AUTH)


def get_customfield_id_from_server(field_name):
    """ Use the Server REST API to find the ID for a given CF name. """
    start_at = 1
    is_last = False
    while not is_last:
        result = service_desk_request_get(
            "%s/rest/api/2/customFields?startAt=%s" % (shared.globals.ROOT_URL, start_at))
        data = result.json()
        for field in data["values"]:
            if field["name"] == field_name:
                return field["id"]
        is_last = data["isLast"]
        start_at += 1
    return None


def get_customfield_id_from_cloud(field_name):
    """ Use the Cloud REST API to find the ID for a given CF name. """
    result = service_desk_request_get(
        "%s/rest/api/3/field" % shared.globals.ROOT_URL)
    data = result.json()
    for field in data:
        if field["name"] == field_name:
            return field["id"]
    return None


def fetch_cf_value(name):
    """ If the specified name is not in the cache, look it up to get the ID. """
    value = None
    # Are we using the REST API?
    if shared.globals.CONFIGURATION["cf_use_server_api"]:
        value = get_customfield_id_from_server(name)
    elif shared.globals.CONFIGURATION["cf_use_cloud_api"]:
        value = get_customfield_id_from_cloud(name)
    # Only save it away if it is a value
    if value is not None:
        CF_CACHE[name] = value
        # And resave to file
        with open(shared.globals.CONFIGURATION["cf_cachefile"], "w") as handle:
            json.dump(CF_CACHE, handle)


def get(name):
    """ Get the ID for the given custom field name. """
    global CF_CACHE  # pylint: disable=global-statement
    initialise_cf_cache()
    if name not in CF_CACHE:
        fetch_cf_value(name)
    if name in CF_CACHE:
        return CF_CACHE[name]
    return None
