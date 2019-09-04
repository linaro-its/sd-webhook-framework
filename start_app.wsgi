#!/usr/bin/python3
"""
A minimal file to get from WSGI to our code.
"""
# Ignore the various pylint errors ...
# pylint: disable=no-name-in-module
# pylint: disable=import-self
# pylint: disable=wrong-import-position
# pylint: disable=unused-import
from app import APP as application
