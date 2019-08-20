"""
Read the JSON configuration file into a global JSON blob.
"""


import os
import json
from json_minify import json_minify


CONFIGURATION = None


def initialise():
    """ Read the JSON configuration file into a global JSON blob. """
    global CONFIGURATION  # pylint: disable=global-statement
    # All of the webhook code is in a sub-directory so we
    # expect to find the configuration file one level up.
    basedir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(basedir, "configuration.jsonc")) as handle:
        CONFIGURATION = json.loads(json_minify(handle.read()))
