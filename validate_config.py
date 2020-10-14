import json
import os
import sys

from json_minify import json_minify

basedir = os.path.dirname(__file__)
config_file = os.path.join(basedir, "configuration.jsonc")
try:
    with open(config_file) as handle:
        CONFIGURATION = json.loads(json_minify(handle.read()))
except json.decoder.JSONDecodeError:
    print("Configuration file is invalid")
    sys.exit(1)
