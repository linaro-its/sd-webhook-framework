# Read the JSON configuration file into a global JSON blob.


import os
import json
from json_minify import json_minify


configuration = None


def initialise():
    global configuration
    # All of the webhook code is in a sub-directory so we
    # expect to find the configuration file one level up.
    basedir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(basedir, "configuration.jsonc")) as f:
        configuration = json.loads(json_minify(f.read()))
