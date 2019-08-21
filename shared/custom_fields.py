"""
Maintain a cache of custom field names to custom field IDs.

Note that the custom fields added by Service Desk will have varying IDs from
instance to instance, hence this file.

Two approaches:
1. Edit custom_fields.json to define the lookup table or
2. Install the free Customfield Editor Plugin which provides a REST API for
   the code to use to retrieve the mapping. However, this is only available
   for self-hosted server installations.
   https://marketplace.atlassian.com/apps/1212096/customfield-editor-plugin

Note that the plugin requires credentials that have Jira admin rights in
order to be able to enumerate all of the custom fields on the system.

It looks like there is an API to support field retrieval in Cloud:
https://developer.atlassian.com/cloud/jira/platform/rest/#api/2/field
Need to get an account and expand this code ...

If the plugin is used, the file is still updated as a cache since it avoids
a round-trip to the server and the overhead of converting the answer into
the dictionary we want.
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


def get_customfield_id_from_plugin(field_name):
    """ Using the CF Editor plugin, return the ID for a given CF name. """
    result = service_desk_request_get(
        "%s/rest/jiracustomfieldeditorplugin/1/admin/customfields" % shared.globals.ROOT_URL
    )
    if result.status_code == 200:
        fields = result.json()
        for field in fields:
            if field["fieldName"] == field_name:
                return field["fieldId"]
    else:
        print("Got status %s when requesting custom field %s" % (
            result.status_code, field_name))
        # Try to get the human readable error message
        fields = result.json()
        if "message" in fields:
            print(fields["message"])
    return None


def fetch_cf_value(name):
    """ If the specified name is not in the cache, look it up to get the ID. """
    if name not in CF_CACHE:
        # Are we using the REST API?
        if shared.globals.CONFIGURATION["cf_use_plugin_api"]:
            # Fetch the custom field from the plugin
            value = get_customfield_id_from_plugin(name)
            # Only save it away if it is a value
            if value is not None:
                CF_CACHE[name] = value
                # And resave to file
                with open(shared.globals.CONFIGURATION["cf_cachefile"], "w") as handle:
                    json.dump(CF_CACHE, handle)
        elif shared.globals.CONFIGURATION["cf_use_cloud_api"]:
            # pylint: disable=fixme
            # TODO: extend for Cloud API
            raise NotImplementedError


def get(name):
    """ Get the ID for the given custom field name. """
    global CF_CACHE  # pylint: disable=global-statement
    initialise_cf_cache()
    fetch_cf_value(name)
    if name in CF_CACHE:
        return CF_CACHE[name]
    return None
