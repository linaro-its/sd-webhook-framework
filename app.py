#!/usr/bin/python3
"""
This can be used as a template to start developing a webhook service for
use with Jira Service Desk.

When testing, if not running on the same server as Service Desk, remember
to use:

flask run --host=0.0.0.0
"""

import os
import sys
import importlib

from flask import Flask, request
import shared.globals
import shared.shared_sd as shared_sd


APP = Flask(__name__)


@APP.route('/', methods=['GET'])
def hello_world():
    """ A simple test to confirm that the code is running properly. """
    return "Hello, world!"


@APP.route('/create', methods=['POST'])
def create():
    """ Triggered when a ticket is created. """
    handler = initialise()
    if handler is not None and "CREATE" in handler.CAPABILITIES:
        if handler.SAVE_TICKET_DATA:
            shared_sd.save_ticket_data_as_attachment(shared.globals.TICKET_DATA)
        handler.create(shared.globals.TICKET_DATA)
    return ""


@APP.route('/comment', methods=['POST'])
def comment():
    """ Triggered when a comment is added to a ticket. """
    handler = initialise()
    if handler is not None and "COMMENT" in handler.CAPABILITIES:
        if handler.SAVE_TICKET_DATA:
            shared_sd.save_ticket_data_as_attachment(shared.globals.TICKET_DATA)
        handler.comment(shared.globals.TICKET_DATA)
    return ""


@APP.route('/jira-hook', methods=['POST'])
def jira_hook():
    """ Triggered when Jira itself (not Service Desk) fires a webhook event. """
    handler = initialise()
    if handler is not None:
        # Jira hook can be triggered for any sort of update to a ticket
        # so we need to look at what has changed. In *theory*, it is
        # possible for both assignee and status to change so we need
        # to check and call for both.
        assignee_result, assignee_from, assignee_to = shared_sd.\
            trigger_is_assignment(shared.globals.TICKET_DATA)
        status_result, status_from, status_to = shared_sd.\
            trigger_is_transition(shared.globals.TICKET_DATA)
        if (handler.SAVE_TICKET_DATA and
                (("TRANSITION" in handler.CAPABILITIES and status_result) or
                 ("ASSIGNMENT" in handler.CAPABILITIES and assignee_result))):
            shared_sd.save_ticket_data_as_attachment(shared.globals.TICKET_DATA)
        if "TRANSITION" in handler.CAPABILITIES and status_result:
            handler.transition(status_from, status_to, shared.globals.TICKET_DATA)
        if "ASSIGNMENT" in handler.CAPABILITIES and assignee_result:
            handler.assignment(assignee_from, assignee_to, shared.globals.TICKET_DATA)
    return ""


def initialise():
    """ Initialise code and variables for this event. """
    shared.globals.initialise_config()
    shared.globals.initialise_ticket_data(request.data)
    shared.globals.initialise_shared_sd()
    shared.globals.initialise_sd_auth()
    # Get the request type for this data
    reqtype = "rt%s" % shared_sd.ticket_request_type(shared.globals.TICKET_DATA)
    # See if there is a module for this request type. If there is,
    # import it.
    dir_path = os.path.dirname(os.path.abspath(__file__)) + "/rt_handlers"
    if os.path.isdir(dir_path):
        if dir_path not in sys.path:
            sys.path.insert(0, dir_path)
        if os.path.exists("%s/%s.py" % (dir_path, reqtype)):
            return importlib.import_module(reqtype)
    return None
