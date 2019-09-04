#!/usr/bin/python3
"""
A minimal file to get from WSGI to our code.

The Graham Dumpleton Docker images put this under /app
and then run it. We need to volume-mount from the host
to a fixed point in the container and that is what we
reference in sys.path.insert.
"""
import sys
sys.path.insert(0, "/srv/sd-webhook-framework")
# Ignore the various pylint errors ...
# pylint: disable=no-name-in-module
# pylint: disable=import-self
# pylint: disable=wrong-import-position
# pylint: disable=unused-import
from app import APP as application
