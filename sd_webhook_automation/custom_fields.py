# Maintain a cache of custom field names to custom field IDs.
#
# Note that the custom fields added by Service Desk will have varying IDs from
# instance to instance, hence this file.
#
# Two approaches:
# 1. Edit custom_fields.json to define the lookup table or
# 2. Install the free Customfield Editor Plugin which provides a REST API for
#    the code to use to retrieve the mapping. However, this is only available
#    for self-hosted server installations.
#    https://marketplace.atlassian.com/apps/1212096/customfield-editor-plugin
#
# Note that the plugin requires credentials that have Jira admin rights in
# order to be able to enumerate all of the custom fields on the system.
#
# It looks like there is an API to support field retrieval in Cloud:
# https://developer.atlassian.com/cloud/jira/platform/rest/#api/2/field
# Need to get an account and expand this code ...
#
# If the plugin is used, the file is still updated as a cache since it avoids
# a round-trip to the server and the overhead of converting the answer into
# the dictionary we want.

import os
import json
import shared_sd
import config


class CustomFieldsError(Exception):
    pass


class MissingCFConfig(CustomFieldsError):
    pass


cf_cache = None


def get(name):
    global cf_cache
    if config.configuration is None:
        config.initialise()
    if "cf_use_plugin_api" not in config.configuration:
        raise MissingCFConfig("Can't find 'cf_use_plugin_api' in config")
    if "cf_cachefile" not in config.configuration:
        raise MissingCFConfig("Can't find 'cf_cachefile' in config")
    if cf_cache is None:
        # Load the cache from the file
        if os.path.isfile(config.configuration["cf_cachefile"]):
            with open(config.configuration["cf_cachefile"], "r") as f:
                cf_cache = json.load(f)
        else:
            cf_cache = {}
    if name not in cf_cache:
        # Are we using the REST API?
        if config.configuration["cf_use_plugin_api"]:
            # Fetch the custom field from the plugin
            value = shared_sd.get_customfield_id_from_plugin(name)
            # Only save it away if it is a value
            if value is not None:
                cf_cache[name] = value
                # And resave to file
                with open(config.configuration["cf_cachefile"], "w") as f:
                    json.dump(cf_cache, f)
        elif config.configuration["cf_use_cloud_api"]:
            # TODO: extend for Cloud API
            raise NotImplementedError

    # Check again as we may have updated the cache
    if name in cf_cache:
        return cf_cache[name]
    else:
        return None
