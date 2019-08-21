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
import shared.shared_sd as shared_sd
import shared.config as config


class CustomFieldsError(Exception):
    """ Base exception class for the Custom Fields code. """


class MissingCFConfig(CustomFieldsError):
    """ Some part of the CF config is missing. """


CF_CACHE = None


def validate_cf_config():
    """ Raise exceptions if the configuration has problems. """
    if config.CONFIGURATION is None:
        config.initialise()
    if "cf_use_plugin_api" not in config.CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_plugin_api' in config")
    if "cf_use_cloud_api" not in config.CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_use_cloud_api' in config")
    if "cf_cachefile" not in config.CONFIGURATION:
        raise MissingCFConfig("Can't find 'cf_cachefile' in config")


def initialise_cf_cache():
    """ Initialise the cache of field names to IDs. """
    global CF_CACHE  # pylint: disable=global-statement
    if CF_CACHE is None:
        # Load the cache from the file
        if os.path.isfile(config.CONFIGURATION["cf_cachefile"]):
            with open(config.CONFIGURATION["cf_cachefile"], "r") as handle:
                CF_CACHE = json.load(handle)
        else:
            CF_CACHE = {}


def fetch_cf_value(name):
    """ If the specified name is not in the cache, look it up to get the ID. """
    if name not in CF_CACHE:
        # Are we using the REST API?
        if config.CONFIGURATION["cf_use_plugin_api"]:
            # Fetch the custom field from the plugin
            value = shared_sd.get_customfield_id_from_plugin(name)
            # Only save it away if it is a value
            if value is not None:
                CF_CACHE[name] = value
                # And resave to file
                with open(config.CONFIGURATION["cf_cachefile"], "w") as handle:
                    json.dump(CF_CACHE, handle)
        elif config.CONFIGURATION["cf_use_cloud_api"]:
            # pylint: disable=fixme
            # TODO: extend for Cloud API
            raise NotImplementedError


def get(name):
    """ Get the ID for the given custom field name. """
    global CF_CACHE  # pylint: disable=global-statement
    validate_cf_config()
    initialise_cf_cache()
    fetch_cf_value(name)
    if name in CF_CACHE:
        return CF_CACHE[name]
    return None
