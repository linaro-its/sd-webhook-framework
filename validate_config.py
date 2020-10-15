import shared.globals
import sys

try:
    shared.globals.initialise_config()
except Exception as exc:
    print(str(exc))
    sys.exit(1)
